"""Device and scheduler handoff hooks, disabled unless the profile opts in."""

import json
from datetime import datetime, timezone
from functools import lru_cache, wraps
from pathlib import Path
from time import sleep

from .state import AccountYield, Handoff, other_device_dialog

ROOT = Path(__file__).resolve().parents[2]


def _profile_name(profile):
    if (not isinstance(profile, str) or profile in {'', '.', '..'}
            or any(char in profile for char in '/\\:')):
        raise ValueError('Invalid account handoff profile name')
    return profile


@lru_cache(maxsize=128)
def _read_settings(root, profile, signature):
    # Cache only this feature's settings; do not retain the full account config.
    path = root / 'config' / f'{profile}.json'
    data = json.loads(path.read_text('utf-8-sig'))
    script = data.get('script', {}) if isinstance(data, dict) else None
    settings = script.get('account_yield', {}) if isinstance(script, dict) else None
    if not isinstance(settings, dict):
        raise ValueError('Invalid script.account_yield configuration')
    enabled = settings.get('enable', False)
    minutes = settings.get('pause_minutes', 20)
    if type(enabled) is not bool:
        raise ValueError('script.account_yield.enable must be a boolean')
    if type(minutes) is not int or not 1 <= minutes <= 240:
        raise ValueError('script.account_yield.pause_minutes must be an integer from 1 to 240')
    return enabled, minutes


def settings(profile, root=None):
    root = Path(root) if root is not None else ROOT
    profile = _profile_name(profile)
    path = root / 'config' / f'{profile}.json'
    if not path.exists():
        state = Handoff(root / 'log/account-yield' / profile / 'state.json').read()
        if state.get('phase') in {'waiting', 'resume_pending'}:
            raise ValueError('Account handoff settings disappeared during an active handoff')
        return False, 20
    stat = path.stat()
    return _read_settings(root, profile, (stat.st_mtime_ns, stat.st_size))


@lru_cache(maxsize=128)
def _controller(root, profile):
    return Handoff(root / 'log/account-yield' / profile / 'state.json',
                   pause_minutes=lambda: settings(profile, root)[1])


def handoff(profile):
    if not settings(profile)[0]:
        return None
    return _controller(ROOT, profile)


def device_gate(device):
    return handoff(device.config.config_name)


def recognize(frame):
    if frame is None or frame.shape != (720, 1280, 3):
        return False
    from module.ocr.models import get_ocr_model

    results = get_ocr_model('ch').detect_and_ocr(frame[160:570, 250:1030])
    rows = []
    for item in results:
        points = item.box
        rows.append((item.ocr_text, item.score, (
            float(points[:, 0].min()) + 250, float(points[:, 1].min()) + 160,
            float(points[:, 0].max()) + 250, float(points[:, 1].max()) + 160,
        )))
    return other_device_dialog(rows)


def observe(device, gate):
    from module.logger import logger

    state = gate.read()
    if state.get('phase') == 'resume_pending':
        # The original logout dialog can remain throughout the pause. Only two
        # fresh main-page observations rearm detection after the one recovery.
        from tasks.GameUi.assets import GameUiAssets

        main = (not recognize(device.image)
                and GameUiAssets.I_CHECK_MAIN.match(device.image)
                and GameUiAssets.I_MAIN_GOTO_SHIKIGAMI_RECORDS.match(device.image))
        count = getattr(device, '_account_yield_main_frames', 0) + 1 if main else 0
        device._account_yield_main_frames = count
        if count >= 2:
            gate.confirm_main()
            device._account_yield_main_frames = 0
            logger.info('Account handoff: main page confirmed, protection rearmed')
        return
    if recognize(device.image):
        state = gate.begin()
        device._account_yield_main_frames = 0
        deadline = datetime.fromtimestamp(state['resume_after'], timezone.utc).astimezone().isoformat()
        logger.info(f'Account handoff: other-device login detected; no input until {deadline}')
        raise AccountYield('Other-device login detected')


def protect(original):
    @wraps(original)
    def operation(self, *args, **kwargs):
        gate = device_gate(self)
        if gate is not None:
            gate.block()
        return original(self, *args, **kwargs)
    return operation


def install_device(cls):
    if getattr(cls, '_account_yield_installed', False):
        return cls
    original = cls.screenshot

    @wraps(original)
    def screenshot(self, *args, **kwargs):
        gate = device_gate(self)
        if gate is None:
            return original(self, *args, **kwargs)
        gate.block()
        from module.exception import GameStuckError

        try:
            result = original(self, *args, **kwargs)
        except GameStuckError:
            # Inspect the actual foreground before stale stuck timers can
            # relaunch the app and displace the other device's session.
            super(cls, self).screenshot()
            observe(self, gate)
            raise
        observe(self, gate)
        return result

    cls.screenshot = screenshot
    for name in ('click', 'long_click', 'swipe', 'swipe_vector', 'drag', 'multi_click',
                 'app_start', 'app_stop', 'emulator_start', 'emulator_stop'):
        if hasattr(cls, name):
            setattr(cls, name, protect(getattr(cls, name)))
    cls._account_yield_installed = True
    return cls


def install_scheduler(cls):
    if getattr(cls, '_account_yield_installed', False):
        return cls
    original_run, original_next, original_wait = cls.run, cls.get_next_task, cls.wait_until

    @wraps(original_run)
    def run(self, *args, **kwargs):
        try:
            return original_run(self, *args, **kwargs)
        except AccountYield:
            from module.logger import logger

            logger.info('Account handoff: task interrupted without marking it complete')
            return True

    @wraps(original_next)
    def next_task(self, *args, **kwargs):
        while True:
            gate = handoff(self.config_name)
            while gate is not None and gate.remaining() > 0:
                sleep(min(10, gate.remaining()))
                gate = handoff(self.config_name)
            if gate is not None:
                gate.release()
                state = gate.read()
                if (state.get('phase') == 'resume_pending'
                        and 'restart_dispatched_at' not in state):
                    self.is_first_task = False
                    state['restart_dispatched_at'] = gate.clock()
                    gate.write(state)
                    return 'Restart'
            try:
                return original_next(self, *args, **kwargs)
            except AccountYield:
                # Also handle enabling the feature during a native idle wait.
                continue

    @wraps(original_wait)
    def wait_until(self, *args, **kwargs):
        gate = handoff(self.config_name)
        if gate is not None:
            gate.block()
        return original_wait(self, *args, **kwargs)

    cls.run, cls.get_next_task, cls.wait_until = run, next_task, wait_until
    cls._account_yield_installed = True
    return cls
