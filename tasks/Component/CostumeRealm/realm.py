"""结界皮肤只覆盖共用素材的搜索区域；在鲤鱼旗配置之前应用。"""
from copy import deepcopy

from tasks.Component.Costume.config import RealmType
from tasks.KekkaiUtilize.assets import KekkaiUtilizeAssets


_REALM_NAMES = ('I_REALM_SHIN', 'I_CARD_EXP', 'I_BOX_AP', 'I_BOX_EXP')
# Capture pristine shared rules before a task applies any realm/carp-banner skin.
_DEFAULT_RULES = {name: deepcopy(getattr(KekkaiUtilizeAssets, name)) for name in _REALM_NAMES}
# Only the search region varies. Template, method, threshold and template size
# remain the shared defaults; matching updates the actual click position.
_REALM_REGIONS = {
    RealmType.COSTUME_REALM_DEFAULT: {},
    RealmType.COSTUME_REALM_YUEHAI_YOUXING: {
        'I_REALM_SHIN': (175, 390, 115, 110),
        'I_CARD_EXP': (865, 205, 135, 105),
        'I_BOX_AP': (975, 415, 90, 105),
        'I_BOX_EXP': (1035, 420, 85, 110),
    },
}


def apply_realm(realm_type: RealmType) -> None:
    regions = _REALM_REGIONS[realm_type]  # Validate before mutating shared rules.
    for name, source in _DEFAULT_RULES.items():
        # Preserve references and reset stale images, features and match state.
        target = getattr(KekkaiUtilizeAssets, name)
        target.__dict__.clear()
        target.__dict__.update(deepcopy(source.__dict__))
        if name in regions:
            target.roi_back = regions[name]
