"""结界皮肤的非鲤鱼旗资源；必须在鲤鱼旗覆盖之前应用。"""
from copy import deepcopy

from tasks.Component.Costume.config import RealmType
from tasks.Component.CostumeRealm.assets import CostumeRealmAssets
from tasks.KekkaiUtilize.assets import KekkaiUtilizeAssets


_REALM_NAMES = ('I_REALM_SHIN', 'I_CARD_EXP', 'I_BOX_AP', 'I_BOX_EXP')
_DEFAULT_RULES = {name: deepcopy(getattr(KekkaiUtilizeAssets, name)) for name in _REALM_NAMES}
_REALM_RULES = {
    RealmType.COSTUME_REALM_DEFAULT: _DEFAULT_RULES,
    RealmType.COSTUME_REALM_YUEHAI_YOUXING: {
        name: getattr(CostumeRealmAssets, name + '_YUEHAI_YOUXING')
        for name in _REALM_NAMES
    },
}


def apply_realm(realm_type: RealmType) -> None:
    rules = _REALM_RULES[realm_type]
    for name, source in rules.items():
        # Preserve shared references and discard cached images/match coordinates.
        target = getattr(KekkaiUtilizeAssets, name)
        target.__dict__.clear()
        target.__dict__.update(deepcopy(source.__dict__))
