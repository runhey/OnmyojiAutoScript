"""Offline phone-session handoff tests; no real game or account is contacted."""

import json
import math
import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest
from module.account_yield import native
from module.account_yield.state import AccountYield, Handoff, other_device_dialog
from tasks.Script.config_account_yield import AccountYieldSettings


def row(text, score=.99, box=(420, 280, 860, 320)):
    return text, score, box


@pytest.mark.parametrize('message', [
    '您的账号已在其他设备上登录', '您的帐号已经在其它地方登陆', '账号在另一客户端登录',
])
def test_logout_requires_message_and_associated_button(message):
    assert other_device_dialog([row(message), row('确定', box=(600, 410, 680, 445))])
    assert not other_device_dialog([row(message)])


@pytest.mark.parametrize('rows', [
    [row('网络连接断开'), row('重新连接', box=(600, 410, 680, 445))],
    [row('您的账号已在其他设备登录', score=.8), row('确定', box=(600, 410, 680, 445))],
    [row('账号在其他设备登录', box=(300, 65, 800, 95)), row('确定', box=(600, 410, 680, 445))],
    [row('账号在其他设备登录'), row('确定', box=(600, 80, 680, 115))],
])
def test_network_error_chat_and_uncertain_text_do_not_yield(rows):
    assert not other_device_dialog(rows)


@pytest.fixture
def gate(tmp_path):
    clock = [1000.0]
    return Handoff(tmp_path / 'state.json', lambda: clock[0]), clock


def test_persistence_same_dialog_and_live_duration_keep_original_start(tmp_path):
    clock, minutes = [1000.0], [20]
    first = Handoff(tmp_path / 'state.json', lambda: clock[0], lambda: minutes[0])
    assert first.begin()['resume_after'] == 2200
    clock[0] = 1500
    second = Handoff(first.path, lambda: clock[0], lambda: minutes[0])
    assert second.begin()['detected_at'] == 1000
    minutes[0] = 40
    assert second.remaining() == 1900
    minutes[0] = 5
    assert second.remaining() == 0
    assert second.release()
    assert not second.release()
    assert second.begin()['phase'] == 'resume_pending'
    second.confirm_main()
    assert second.begin()['detected_at'] == 1500


@pytest.mark.parametrize('value', [0, 241, True, 20.5, '20'])
def test_invalid_duration_is_rejected_without_saving_state(tmp_path, value):
    gate = Handoff(tmp_path / 'state.json', pause_minutes=value)
    with pytest.raises(ValueError):
        gate.begin()
    assert not gate.path.exists()
    with pytest.raises(ValueError):
        AccountYieldSettings(pause_minutes=value)


@pytest.mark.parametrize('bad_state', [
    [], {'phase': 'unknown'}, {'phase': 'waiting'},
    {'phase': 'waiting', 'detected_at': 1000, 'resume_after': math.nan},
    {'phase': 'waiting', 'detected_at': 1000, 'resume_after': 900},
])
def test_corrupt_state_cannot_bypass_input_protection(gate, bad_state):
    controller, _ = gate
    controller.path.write_text(json.dumps(bad_state))
    with pytest.raises(ValueError):
        controller.block()


@pytest.fixture
def isolated_settings(tmp_path, monkeypatch):
    monkeypatch.setattr(native, 'ROOT', tmp_path)
    native._read_settings.cache_clear()
    native._controller.cache_clear()
    (tmp_path / 'config').mkdir()

    def save(name, enabled=False, minutes=20):
        path = tmp_path / 'config' / (name + '.json')
        path.write_text(json.dumps({'script': {'account_yield': {
            'enable': enabled, 'pause_minutes': minutes,
        }}}))
        stamp = path.stat().st_mtime_ns + 1_000_000_000
        os.utime(path, ns=(stamp, stamp))
        return path

    return save


def test_default_is_disabled_and_each_profile_has_an_independent_deadline(isolated_settings):
    save = isolated_settings
    assert not AccountYieldSettings().enable
    assert native.handoff('unconfigured') is None
    save('first', True, 20)
    save('second', True, 45)
    first, second = native.handoff('first'), native.handoff('second')
    assert first.path != second.path
    first.begin()
    assert not second.read()
    assert first.configured_minutes() == 20
    save('first', True, 40)
    assert first.configured_minutes() == 40
    save('first', False)
    assert native.handoff('first') is None
    assert native.handoff('second').configured_minutes() == 45


def test_missing_settings_during_a_pause_cannot_silently_disable_it(isolated_settings):
    path = isolated_settings('sample', True)
    controller = native.handoff('sample')
    controller.begin()
    path.unlink()
    with pytest.raises(ValueError, match='disappeared'):
        native.handoff('sample')


@pytest.mark.parametrize('name', ['', '..', '../other', 'a/b', 'a\\b', 'C:other'])
def test_profile_names_cannot_escape_the_state_directory(name):
    with pytest.raises(ValueError):
        native.handoff(name)


@pytest.fixture
def logger(monkeypatch):
    monkeypatch.setitem(sys.modules, 'module.logger', SimpleNamespace(
        logger=SimpleNamespace(info=lambda *_: None)))


def test_inputs_remain_blocked_when_control_check_is_disabled(gate, monkeypatch):
    handoff, _ = gate
    handoff.begin()
    monkeypatch.setattr(native, 'device_gate', lambda _: handoff)
    inputs = []
    guarded = native.protect(lambda *a, **kw: inputs.append(kw))
    with pytest.raises(AccountYield):
        guarded(object(), x=600, y=440, control_check=False)
    assert not inputs
    assert not issubclass(AccountYield, Exception)


def test_stale_stuck_timer_observes_logout_before_restarting(gate, monkeypatch, logger):
    handoff, _ = gate
    monkeypatch.setattr(native, 'device_gate', lambda _: handoff)
    monkeypatch.setattr(native, 'recognize', lambda _: True)

    class Stuck(Exception):
        pass

    monkeypatch.setitem(sys.modules, 'module.exception', SimpleNamespace(GameStuckError=Stuck))

    class Capture:
        def screenshot(self):
            self.image = np.zeros((720, 1280, 3), np.uint8)

    class Device(Capture):
        def screenshot(self):
            raise Stuck()

    native.install_device(Device)
    with pytest.raises(AccountYield):
        Device().screenshot()
    assert handoff.read()['phase'] == 'waiting'


def test_scheduler_unwinds_native_idle_wait_and_recovers_once(gate, monkeypatch, logger):
    handoff, clock = gate
    monkeypatch.setattr(native, 'handoff', lambda _: handoff)
    sleeps = []

    def sleep(seconds):
        sleeps.append(seconds)
        clock[0] += seconds

    monkeypatch.setattr(native, 'sleep', sleep)

    class Scheduler:
        config_name = 'sample'
        is_first_task = True

        def run(self, command):
            handoff.begin()
            raise AccountYield()

        def wait_until(self, future):
            raise AssertionError('A long native idle wait must not hide handoff expiry')

        def get_next_task(self):
            if 'restart_dispatched_at' in handoff.read():
                return 'NextTask'
            assert self.run('GotoMain') is True
            self.wait_until(9000)

    native.install_scheduler(Scheduler)
    scheduler = Scheduler()
    assert scheduler.get_next_task() == 'Restart'
    assert sum(sleeps) == 1200 and max(sleeps) <= 10
    assert not scheduler.is_first_task
    assert scheduler.get_next_task() == 'NextTask'


def test_stopping_a_worker_cannot_schedule_relogin(gate, monkeypatch):
    handoff, _ = gate
    handoff.begin()
    monkeypatch.setattr(native, 'handoff', lambda _: handoff)
    monkeypatch.setattr(native, 'sleep', lambda _: (_ for _ in ()).throw(KeyboardInterrupt()))

    class Scheduler:
        config_name = 'sample'
        run = get_next_task = wait_until = lambda *a: 'original'

    native.install_scheduler(Scheduler)
    with pytest.raises(KeyboardInterrupt):
        Scheduler().get_next_task()
    assert handoff.read()['phase'] == 'waiting'
    assert 'restart_dispatched_at' not in handoff.read()


def test_disabled_profile_retains_original_behavior(monkeypatch):
    monkeypatch.setattr(native, 'handoff', lambda _: None)

    class Scheduler:
        config_name = 'sample'
        run = get_next_task = wait_until = lambda *a: 'original'

    native.install_scheduler(Scheduler)
    assert Scheduler().get_next_task() == Scheduler().run('Task') == 'original'


def test_rearm_requires_two_fresh_main_frames(gate, monkeypatch, logger):
    handoff, clock = gate
    handoff.begin()
    clock[0] += 1200
    assert handoff.release()
    monkeypatch.setattr(native, 'recognize', lambda _: False)
    anchors = SimpleNamespace(
        I_CHECK_MAIN=SimpleNamespace(match=lambda _: True),
        I_MAIN_GOTO_SHIKIGAMI_RECORDS=SimpleNamespace(match=lambda _: True))
    monkeypatch.setitem(sys.modules, 'tasks.GameUi.assets', SimpleNamespace(GameUiAssets=anchors))
    device = SimpleNamespace(image=object())
    native.observe(device, handoff)
    assert handoff.read()['phase'] == 'resume_pending'
    native.observe(device, handoff)
    assert handoff.read()['phase'] == 'armed'


@pytest.mark.parametrize('name', [
    'click', 'long_click', 'swipe', 'swipe_vector', 'drag', 'multi_click',
    'app_start', 'app_stop', 'emulator_start', 'emulator_stop',
])
def test_device_and_lifecycle_entry_points_are_blocked(gate, monkeypatch, name):
    handoff, _ = gate
    handoff.begin()
    monkeypatch.setattr(native, 'device_gate', lambda _: handoff)
    calls = []

    class Device:
        def screenshot(self):
            calls.append('capture')

    setattr(Device, name, lambda *a, **kw: calls.append(name))
    assert native.install_device(Device) is Device
    assert native.install_device(Device) is Device
    with pytest.raises(AccountYield):
        getattr(Device(), name)()
    assert not calls


def test_disabling_during_wait_does_not_force_a_restart(gate, monkeypatch):
    handoff, clock = gate
    handoff.begin()
    enabled = [True]
    monkeypatch.setattr(native, 'handoff', lambda _: handoff if enabled[0] else None)

    def tick(seconds):
        clock[0] += seconds
        enabled[0] = False

    monkeypatch.setattr(native, 'sleep', tick)

    class Scheduler:
        config_name = 'sample'
        run = get_next_task = wait_until = lambda *a: 'original'

    native.install_scheduler(Scheduler)
    assert Scheduler().get_next_task() == 'original'
    assert clock[0] == 1010
    assert 'restart_dispatched_at' not in handoff.read()


def test_clock_zero_dispatch_marker_is_not_replayed(gate, monkeypatch):
    handoff, clock = gate
    handoff.begin()
    clock[0] += 1200
    handoff.release()
    state = handoff.read()
    state['restart_dispatched_at'] = 0
    handoff.write(state)
    monkeypatch.setattr(native, 'handoff', lambda _: handoff)

    class Scheduler:
        config_name = 'sample'
        run = get_next_task = wait_until = lambda *a: 'original'

    native.install_scheduler(Scheduler)
    assert Scheduler().get_next_task() == 'original'


def test_state_replace_failure_keeps_the_previous_deadline(gate, monkeypatch):
    handoff, _ = gate
    handoff.begin()
    before = handoff.path.read_bytes()
    monkeypatch.setattr('module.account_yield.state.os.replace',
                        lambda *a: (_ for _ in ()).throw(OSError('replace failed')))
    with pytest.raises(OSError):
        handoff.write({'phase': 'armed'})
    assert handoff.path.read_bytes() == before
    assert not list(handoff.path.parent.glob('state.json.*'))
