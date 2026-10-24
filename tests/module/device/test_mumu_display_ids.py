"""MuMu 6.0 multi-display detection in `Adb._mumu_display_ids`.

Every test drives the detection with a fake `adb_shell`, so no device is
needed. The dumpsys excerpts are trimmed copies of a real MuMu 6.0
(Android 15) dump.
"""

from module.device.method.adb import Adb

PACKAGE = 'com.netease.onmyoji.wyzymnqsd_cps'
LONG_ID = '4619826888814064386'

# display 5 idle, display 0 the launcher, display 3 the game
WINDOW_DISPLAYS_MUMU6 = f'''\
  Display: mDisplayId=5 (organized)
  mCurrentFocus=null
  mFocusedApp=null
  Display: mDisplayId=0 (organized)
  mFocusedApp=ActivityRecord{{1 u0 app.lawnchair/.LawnchairLauncher t2}}
  Display: mDisplayId=3 (organized)
  mCurrentFocus=Window{{ac9120e u0 {PACKAGE}/{PACKAGE}.Client}}
  mFocusedApp=ActivityRecord{{2 u0 {PACKAGE}/{PACKAGE}.Client t153}}
'''

# old engine / plain phone: everything on display 0
WINDOW_DISPLAYS_SINGLE = f'''\
  Display: mDisplayId=0 (organized)
  mFocusedApp=ActivityRecord{{2 u0 {PACKAGE}/{PACKAGE}.Client t153}}
'''

# another app focused on its own display, listed before the game's
WINDOW_DISPLAYS_OTHER_APP_FIRST = f'''\
  Display: mDisplayId=2 (organized)
  mFocusedApp=ActivityRecord{{3 u0 com.other.app/.Main t10}}
  Display: mDisplayId=3 (organized)
  mFocusedApp=ActivityRecord{{2 u0 {PACKAGE}/{PACKAGE}.Client t153}}
'''

# virtual display exists, but nothing is focused on it yet
WINDOW_DISPLAYS_NOT_READY = f'''\
  Display: mDisplayId=0 (organized)
  mFocusedApp=ActivityRecord{{1 u0 app.lawnchair/.LawnchairLauncher t2}}
  Display: mDisplayId=3 (organized)
  mCurrentFocus=null
'''

# a system dialog takes the focus away from the game package
WINDOW_DISPLAYS_DIALOG = '''\
  Display: mDisplayId=3 (organized)
  mFocusedApp=ActivityRecord{4 u0 com.android.permissioncontroller/.GrantPermissionsActivity t5}
'''

DUMPSYS_DISPLAY = f'''\
    mDisplayId=3
    mPrimaryDisplayDevice=mumuscreen002(local:{LONG_ID})
    mBaseDisplayInfo=DisplayInfo{{"mumuscreen002", ..., deviceProductInfo DeviceProductInfo{{name=mumuscreen002, manufacturerPnpId=GGL}}}}
'''

SURFACEFLINGER = f'''\
Display 4619827820427265280 (HWC display 0): port=0 pnpId=GGL displayName="mumuscreen000"
Display {LONG_ID} (HWC display 2): port=2 pnpId=GGL displayName="mumuscreen002"
'''


def make_adb(window_displays, dumpsys_display=DUMPSYS_DISPLAY, surfaceflinger=SURFACEFLINGER):
    """An Adb instance with only what `_mumu_display_ids` touches."""
    adb = object.__new__(Adb)
    adb.package = PACKAGE
    adb._mumu_display_ids_cache = None
    adb._mumu_display_ids_retry_at = 0.0
    adb._mumu_display_ids_generation = 0
    calls = []

    def adb_shell(cmd, **kwargs):
        calls.append(list(cmd))
        return {
            'window': window_displays,
            'display': dumpsys_display,
            'SurfaceFlinger': surfaceflinger,
        }[cmd[1]]

    adb.adb_shell = adb_shell
    return adb, calls


def test_game_on_a_virtual_display_is_detected():
    adb, calls = make_adb(WINDOW_DISPLAYS_MUMU6)
    assert adb._mumu_display_ids() == (3, LONG_ID)
    # cached: the next call does not probe again
    assert adb._mumu_display_ids() == (3, LONG_ID)
    assert len(calls) == 3


def test_plain_single_display_device_stays_on_display_0():
    adb, calls = make_adb(WINDOW_DISPLAYS_SINGLE)
    assert adb._mumu_display_ids() is None
    # the definitive miss is remembered, so clicks do not probe per call
    assert adb._mumu_display_ids() is None
    assert len(calls) == 1


def test_another_app_on_an_earlier_display_does_not_win():
    adb, _ = make_adb(WINDOW_DISPLAYS_OTHER_APP_FIRST)
    assert adb._mumu_display_ids() == (3, LONG_ID)


def test_dialog_on_top_falls_back_to_the_focused_display():
    adb, _ = make_adb(WINDOW_DISPLAYS_DIALOG)
    assert adb._mumu_display_ids() == (3, LONG_ID)


def test_display_not_up_yet_is_retried_instead_of_remembered():
    adb, calls = make_adb(WINDOW_DISPLAYS_NOT_READY)
    assert adb._mumu_display_ids() is None
    assert adb._mumu_display_ids() is None
    assert len(calls) == 2


def test_input_prefix_targets_the_game_display():
    adb, _ = make_adb(WINDOW_DISPLAYS_MUMU6)
    adb._mumu_display_ids()
    assert adb._input_prefix() == ['input', '-d', '3']


def test_a_reset_drops_the_cached_display():
    adb, calls = make_adb(WINDOW_DISPLAYS_MUMU6)
    assert adb._mumu_display_ids() == (3, LONG_ID)
    adb._reset_mumu_display_ids()
    assert adb._mumu_display_ids() == (3, LONG_ID)
    assert len(calls) == 6
