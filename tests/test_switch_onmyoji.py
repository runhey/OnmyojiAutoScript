"""SwitchOnmyoji must have a bounded exit path.

Both loops in `SwitchOnmyoji.switch_role` used to be unconditional `while True`.
When the onmyoji/hero tab cannot be reached (stale asset coordinates after a
game UI update, emulator showing a different page, ...), they kept clicking
forever until the global `GameStuckError` watchdog fired roughly two minutes
later, discarding all context about what actually went wrong.

These tests pin the exit conditions: a loop that never finds its target has to
raise a named, catchable `ScriptError` instead of spinning, and the happy path
must keep working unchanged.
"""
import pytest

from module.base.timer import Timer
from module.exception import ScriptError
from tasks.Component.SwitchOnmyoji.config import Onmyoji
from tasks.Component.SwitchOnmyoji.switch_onmyoji import SwitchOnmyoji


class ScriptedSwitch(SwitchOnmyoji):
    """Double that replays a fixed sequence of `appear` results.

    `screenshot` and every click are no-ops, so the test exercises the real
    loop control flow of `switch_role` without a Config, a Device or a game.
    """

    def __init__(self, appear_results, timeout=0):
        # deliberately skip BaseTask.__init__: it needs a real Config/Device
        self._appear_results = list(appear_results)
        self._appear_calls = 0
        self.switch_clicks = 0
        self.battle_clicks = 0
        self.ui_clicks = 0
        # override the real 20s guards so the test does not have to wait
        self.SWITCH_TAB_TIMEOUT = timeout
        self.SWITCH_BATTLE_TIMEOUT = timeout

    def _next_appear(self, button):
        self._appear_calls += 1
        if not self._appear_results:
            return False
        return self._appear_results.pop(0)

    def screenshot(self):
        pass

    def appear(self, button, interval=None, **kwargs):
        return self._next_appear(button)

    def appear_then_click(self, button, interval=None, **kwargs):
        self.switch_clicks += 1
        return True

    def click(self, button, interval=None, **kwargs):
        self.battle_clicks += 1
        return True

    def ui_click(self, button1, button2, interval=None, **kwargs):
        self.ui_clicks += 1
        return True


def test_switch_role_raises_when_battle_list_never_appears():
    task = ScriptedSwitch(appear_results=[])

    with pytest.raises(ScriptError):
        task.switch_role(role=None, battle_dict={'x': object()}, check_img=object())


def test_switch_role_raises_when_check_icon_never_appears():
    # battle icon visible, confirm icon never does
    task = ScriptedSwitch(appear_results=[True])

    with pytest.raises(ScriptError):
        task.switch_role(role=Onmyoji.KAGURA, battle_dict={Onmyoji.KAGURA: object()}, check_img=object())


def test_switch_role_still_switches_when_the_flow_is_healthy():
    # appear order: battle icon, then confirm icon -> no extra clicks needed
    task = ScriptedSwitch(appear_results=[True, True])

    task.switch_role(role=Onmyoji.KAGURA, battle_dict={Onmyoji.KAGURA: object()}, check_img=object())

    assert task.switch_clicks == 0
    assert task.battle_clicks == 0
    assert task.ui_clicks == 0


def test_switch_role_clicks_the_battle_icon_when_confirm_icon_is_absent():
    # appear order: battle icon, not-confirm, battle icon -> ui_click back path
    task = ScriptedSwitch(appear_results=[True, False, True])

    task.switch_role(role=Onmyoji.KAGURA, battle_dict={Onmyoji.KAGURA: object()}, check_img=object())

    assert task.switch_clicks == 0
    assert task.ui_clicks == 1


def test_timeouts_are_not_shared_between_instances():
    a = ScriptedSwitch(appear_results=[])
    b = ScriptedSwitch(appear_results=[])

    assert a.SWITCH_TAB_TIMEOUT is not None
    assert b.SWITCH_TAB_TIMEOUT is not None
