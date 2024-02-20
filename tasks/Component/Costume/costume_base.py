# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from module.atom.image import RuleImage

from tasks.Component.Costume.config import (MainType, CostumeConfig, RealmType,
                                            ThemeType, ShikigamiType, SignType, BattleType)
from tasks.Component.Costume.assets import CostumeAssets
from tasks.Component.CostumeRealm.assets import CostumeRealmAssets

# 庭院皮肤
main_costume_model = {
    MainType.COSTUME_MAIN_1: {'I_CHECK_MAIN': 'I_CHECK_MAIN_1',
                              'I_MAIN_GOTO_EXPLORATION': 'I_MAIN_GOTO_EXPLORATION_1',
                              'I_MAIN_GOTO_SUMMON': 'I_MAIN_GOTO_SUMMON_1',
                              'I_MAIN_GOTO_TOWN': 'I_MAIN_GOTO_TOWN_1',
                              'I_PET_HOUSE': 'I_PET_HOUSE_1', },
    MainType.COSTUME_MAIN_2: {'I_CHECK_MAIN': 'I_CHECK_MAIN_2',
                              'I_MAIN_GOTO_EXPLORATION': 'I_MAIN_GOTO_EXPLORATION_2',
                              'I_MAIN_GOTO_SUMMON': 'I_MAIN_GOTO_SUMMON_2',
                              'I_MAIN_GOTO_TOWN': 'I_MAIN_GOTO_TOWN_2',
                              'I_PET_HOUSE': 'I_PET_HOUSE_2', },
    MainType.COSTUME_MAIN_3: {'I_CHECK_MAIN': 'I_CHECK_MAIN_3',
                              'I_MAIN_GOTO_EXPLORATION': 'I_MAIN_GOTO_EXPLORATION_3',
                              'I_MAIN_GOTO_SUMMON': 'I_MAIN_GOTO_SUMMON_3',
                              'I_MAIN_GOTO_TOWN': 'I_MAIN_GOTO_TOWN_3',
                              'I_PET_HOUSE': 'I_PET_HOUSE_3', },
    MainType.COSTUME_MAIN_4: {'I_CHECK_MAIN': 'I_CHECK_MAIN_4',
                              'I_MAIN_GOTO_EXPLORATION': 'I_MAIN_GOTO_EXPLORATION_4',
                              'I_MAIN_GOTO_SUMMON': 'I_MAIN_GOTO_SUMMON_4',
                              'I_MAIN_GOTO_TOWN': 'I_MAIN_GOTO_TOWN_4',
                              'I_PET_HOUSE': 'I_PET_HOUSE_4', },
    MainType.COSTUME_MAIN_5: {'I_CHECK_MAIN': 'I_CHECK_MAIN_5',
                              'I_MAIN_GOTO_EXPLORATION': 'I_MAIN_GOTO_EXPLORATION_5',
                              'I_MAIN_GOTO_SUMMON': 'I_MAIN_GOTO_SUMMON_5',
                              'I_MAIN_GOTO_TOWN': 'I_MAIN_GOTO_TOWN_5',
                              'I_PET_HOUSE': 'I_PET_HOUSE_5', },
    MainType.COSTUME_MAIN_6: {'I_CHECK_MAIN': 'I_CHECK_MAIN_6',
                              'I_MAIN_GOTO_EXPLORATION': 'I_MAIN_GOTO_EXPLORATION_6',
                              'I_MAIN_GOTO_SUMMON': 'I_MAIN_GOTO_SUMMON_6',
                              'I_MAIN_GOTO_TOWN': 'I_MAIN_GOTO_TOWN_6',
                              'I_PET_HOUSE': 'I_PET_HOUSE_6', },
    MainType.COSTUME_MAIN_7: {'I_CHECK_MAIN': 'I_CHECK_MAIN_7',
                              'I_MAIN_GOTO_EXPLORATION': 'I_MAIN_GOTO_EXPLORATION_7',
                              'I_MAIN_GOTO_SUMMON': 'I_MAIN_GOTO_SUMMON_7',
                              'I_MAIN_GOTO_TOWN': 'I_MAIN_GOTO_TOWN_7',
                              'I_PET_HOUSE': 'I_PET_HOUSE_7', },
    MainType.COSTUME_MAIN_8: {'I_CHECK_MAIN': 'I_CHECK_MAIN_8',
                              'I_MAIN_GOTO_EXPLORATION': 'I_MAIN_GOTO_EXPLORATION_8',
                              'I_MAIN_GOTO_SUMMON': 'I_MAIN_GOTO_SUMMON_8',
                              'I_MAIN_GOTO_TOWN': 'I_MAIN_GOTO_TOWN_8',
                              'I_PET_HOUSE': 'I_PET_HOUSE_8', },
    MainType.COSTUME_MAIN_9: {'I_CHECK_MAIN': 'I_CHECK_MAIN_9',
                              'I_MAIN_GOTO_EXPLORATION': 'I_MAIN_GOTO_EXPLORATION_9',
                              'I_MAIN_GOTO_SUMMON': 'I_MAIN_GOTO_SUMMON_9',
                              'I_MAIN_GOTO_TOWN': 'I_MAIN_GOTO_TOWN_9',
                              'I_PET_HOUSE': 'I_PET_HOUSE_9', },
}

# 结界皮肤
realm_costume_model = {
    RealmType.COSTUME_REALM_1: {'I_SHI_CARD': 'I_SHI_CARD_1',
                                'I_SHI_DEFENSE': 'I_SHI_DEFENSE_1',},
    RealmType.COSTUME_REALM_2: {'I_SHI_CARD': 'I_SHI_CARD_2',
                                'I_SHI_DEFENSE': 'I_SHI_DEFENSE_2',
                                'I_SHI_GROWN': 'I_SHI_GROWN_2',
                                'I_BOX_AP': 'I_BOX_AP_2',
                                'I_BOX_EXP': 'I_BOX_EXP_2'},
}

class CostumeBase:

    def check_costume(self, config: CostumeConfig=None):
        if config is None:
            config: CostumeConfig = self.config.model.global_game.costume_config
        self.check_costume_main(config.costume_main_type)
        self.check_costume_realm(config.costume_realm_type)

    def replace_img(self, asset_before: str, asset_after: RuleImage):
        if not hasattr(self, asset_before):
            return
        # setattr(self, asset_before, asset_after)
        asset_before_object: RuleImage = getattr(self, asset_before)
        asset_before_object.roi_front = asset_after.roi_front
        asset_before_object.roi_back = asset_after.roi_back
        asset_before_object.threshold = asset_after.threshold
        asset_before_object.file = asset_after.file

    def check_costume_main(self, main_type: MainType):
        if main_type == MainType.COSTUME_MAIN:
            return
        costume_assets = CostumeAssets()
        for key, value in main_costume_model[main_type].items():
            assert_value: RuleImage = getattr(costume_assets, value)
            self.replace_img(key, assert_value)

    def check_costume_realm(self, realm_type: RealmType):
        if realm_type == RealmType.COSTUME_REALM_DEFAULT:
            return
        costume_realm_assets = CostumeRealmAssets()
        for key, value in realm_costume_model[realm_type].items():
            assert_value: RuleImage = getattr(costume_realm_assets, value)
            self.replace_img(key, assert_value)



if __name__ == '__main__':
    c = CostumeBase()
    c.check_costume_main(MainType.COSTUME_MAIN_1)
