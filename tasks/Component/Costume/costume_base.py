# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from module.atom.image import RuleImage

from tasks.Component.Costume.config import MainType, CostumeConfig
from tasks.Component.Costume.assets import CostumeAssets

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
}


class CostumeBase:

    def check_costume(self, config: CostumeConfig):
        self.check_costume_main(config.costume_main_type)

    def check_costume_main(self, main_type: MainType):
        if main_type == MainType.COSTUME_MAIN:
            return
        costume_assets = CostumeAssets()
        for key, value in main_costume_model[main_type].items():
            assert_value: RuleImage = getattr(costume_assets, value)
            self.replace_img(key, assert_value)

    def replace_img(self, asset_before: str, asset_after: RuleImage):
        if not hasattr(self, asset_before):
            return
        # setattr(self, asset_before, asset_after)
        asset_before_object: RuleImage = getattr(self, asset_before)
        asset_before_object.roi_front = asset_after.roi_front
        asset_before_object.roi_back = asset_after.roi_back
        asset_before_object.threshold = asset_after.threshold
        asset_before_object.file = asset_after.file



if __name__ == '__main__':
    c = CostumeBase()
    c.check_costume_main(MainType.COSTUME_MAIN_1)
