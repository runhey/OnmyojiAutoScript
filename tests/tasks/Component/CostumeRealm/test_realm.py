"""Offline realm-skin regression tests (no device connection)."""
import unittest
from copy import deepcopy

from tasks.Component.Costume.config import CostumeConfig, RealmType, CarpBannerType
from tasks.Component.Costume.costume_base import CostumeBase
from tasks.Component.CostumeRealm.realm import apply_realm, _REALM_NAMES
from tasks.KekkaiUtilize.assets import KekkaiUtilizeAssets


class RealmTests(unittest.TestCase):
    def setUp(self):
        apply_realm(RealmType.COSTUME_REALM_DEFAULT)

    def tearDown(self):
        apply_realm(RealmType.COSTUME_REALM_DEFAULT)

    def test_schema_and_default(self):
        self.assertEqual(CostumeConfig().costume_realm_type, RealmType.COSTUME_REALM_DEFAULT)
        config = CostumeConfig(costume_realm_type='costume_realm_yuehai_youxing')
        self.assertEqual(config.costume_realm_type, RealmType.COSTUME_REALM_YUEHAI_YOUXING)
        self.assertIn('costume_realm_yuehai_youxing',
                      CostumeConfig.model_json_schema()['$defs']['RealmType']['enum'])

    def test_identity_cache_reset_and_default_restore(self):
        refs = {name: getattr(KekkaiUtilizeAssets, name) for name in _REALM_NAMES}
        defaults = {name: (rule.file, tuple(rule.roi_front), rule.roi_back) for name, rule in refs.items()}
        for rule in refs.values():
            _ = rule.image
            _ = rule.name
        CostumeBase().check_costume_realm(RealmType.COSTUME_REALM_YUEHAI_YOUXING)
        for name, rule in refs.items():
            self.assertIs(rule, getattr(KekkaiUtilizeAssets, name))
            self.assertIn('/CostumeRealm/', rule.file)
            self.assertIsNone(rule._image)
            self.assertNotIn('name', rule.__dict__)
            self.assertEqual(rule.image.shape[:2], (rule.roi_front[3], rule.roi_front[2]))
        apply_realm(RealmType.COSTUME_REALM_DEFAULT)
        for name, rule in refs.items():
            self.assertEqual((rule.file, tuple(rule.roi_front), rule.roi_back), defaults[name])
            self.assertIsNone(rule._image)

    def test_uncollected_icons_dialogs_and_carp_flags_untouched(self):
        names = ('I_UTILIZE_EXP', 'I_BOX_EXP_MAX', 'I_AP_EXTRACT', 'I_EXP_EXTRACT',
                 'I_SHI_GROWN', 'I_SHI_CARD', 'I_SHI_DEFENSE')
        states = {name: deepcopy(getattr(KekkaiUtilizeAssets, name).__dict__) for name in names}
        apply_realm(RealmType.COSTUME_REALM_YUEHAI_YOUXING)
        for name in names:
            self.assertEqual(getattr(KekkaiUtilizeAssets, name).__dict__, states[name])

    def test_reapply_and_invalid_selection(self):
        apply_realm(RealmType.COSTUME_REALM_YUEHAI_YOUXING)
        rule = KekkaiUtilizeAssets.I_CARD_EXP
        original = tuple(rule.roi_front)
        rule.roi_front[0] = 0
        apply_realm(RealmType.COSTUME_REALM_YUEHAI_YOUXING)
        self.assertEqual(tuple(rule.roi_front), original)
        with self.assertRaises(KeyError):
            apply_realm('invalid')
        self.assertEqual(tuple(rule.roi_front), original)

    def test_realm_applied_before_carpbanner(self):
        calls = []
        class Probe(CostumeBase):
            def get_task_name(self): return 'OfflineRealmTest'
            def check_costume_main(self, value): pass
            def check_costume_realm(self, value): calls.append(('realm', value))
            def check_costume_carpbanner(self, value): calls.append(('carp', value))
            def check_costume_battle(self, value): pass
            def check_costume_battle_scene(self, value): pass
            def check_costume_shikigami(self, value): pass
            def check_costume_theme(self, value): pass
        Probe().check_costume(CostumeConfig(costume_realm_type=RealmType.COSTUME_REALM_YUEHAI_YOUXING,
                                           costume_carpbanner_type=CarpBannerType.COSTUME_CARPBANNER_3))
        self.assertEqual(calls, [('realm', RealmType.COSTUME_REALM_YUEHAI_YOUXING),
                                 ('carp', CarpBannerType.COSTUME_CARPBANNER_3)])


if __name__ == '__main__':
    unittest.main()
