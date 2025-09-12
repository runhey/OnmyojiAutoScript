# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from module.atom.image import RuleImage
from module.logger import logger

from tasks.Component.Costume.config import (MainType, CostumeConfig, RealmType,
                                            ThemeType, ShikigamiType, SignType, BattleType)
from tasks.Component.Costume.assets import CostumeAssets
from tasks.Component.CostumeRealm.assets import CostumeRealmAssets
from tasks.Component.CostumeBattle.assets import CostumeBattleAssets

# 庭院皮肤
# 主界面皮肤（使用字典推导式动态生成）
main_costume_model = {
    getattr(MainType, f"COSTUME_MAIN_{i}"): {
        'I_CHECK_MAIN': f'I_CHECK_MAIN_{i}',
        'I_MAIN_GOTO_EXPLORATION': f'I_MAIN_GOTO_EXPLORATION_{i}',
        'I_MAIN_GOTO_SUMMON': f'I_MAIN_GOTO_SUMMON_{i}',
        'I_MAIN_GOTO_TOWN': f'I_MAIN_GOTO_TOWN_{i}',
        'I_PET_HOUSE': f'I_PET_HOUSE_{i}'
    } for i in range(1, 13)
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

# 战斗主题（使用循环处理常规情况 + 特例处理）
battle_theme_model = {}
for i in range(1, 11):
    entry = {
        'I_LOCAL': f'I_LOCAL_{i}',
        'I_EXIT': f'I_EXIT_{i}',
        'I_FRIENDS': f'I_FRIENDS_{i}',
    }
    if i == 8:  # 特殊处理第8项
        entry.update({
            'I_WIN': 'I_WIN_8',
            'I_DE_WIN': 'I_DE_WIN_8',
            'I_FALSE': 'I_FALSE_8'
        })
    battle_theme_model[getattr(BattleType, f"COSTUME_BATTLE_{i}")] = entry


class CostumeBase:

    def check_costume(self, config: CostumeConfig=None):
        if config is None:
            config: CostumeConfig = self.config.model.global_game.costume_config
        self.check_costume_main(config.costume_main_type)
        self.check_costume_realm(config.costume_realm_type)
        self.check_costume_battle(config.costume_battle_type)

    def replace_img(self,
                    asset_before: str,
                    asset_after: RuleImage,
                    rp_roi_back: bool = True):
        if not hasattr(self, asset_before):
            return
        # setattr(self, asset_before, asset_after)
        asset_before_object: RuleImage = getattr(self, asset_before)
        asset_before_object.roi_front = asset_after.roi_front
        if rp_roi_back:
            asset_before_object.roi_back = asset_after.roi_back
        asset_before_object.threshold = asset_after.threshold
        asset_before_object.file = asset_after.file

    def check_costume_main(self, main_type: MainType):
        if main_type == MainType.COSTUME_MAIN:
            return
        logger.info(f'Switch main costume to {main_type}')
        costume_assets = CostumeAssets()
        for key, value in main_costume_model[main_type].items():
            assert_value: RuleImage = getattr(costume_assets, value)
            self.replace_img(key, assert_value)

    def check_costume_realm(self, realm_type: RealmType):
        if realm_type == RealmType.COSTUME_REALM_DEFAULT:
            return
        logger.info(f'Switch realm theme {realm_type}')
        costume_realm_assets = CostumeRealmAssets()
        for key, value in realm_costume_model[realm_type].items():
            assert_value: RuleImage = getattr(costume_realm_assets, value)
            self.replace_img(key, assert_value)

    def check_costume_battle(self, battle_type: BattleType):
        if battle_type == BattleType.COSTUME_BATTLE_DEFAULT:
            return
        logger.info(f'Switch battle theme {battle_type}')
        costume_battle_assets = CostumeBattleAssets()
        for key, value in battle_theme_model[battle_type].items():
            assert_value: RuleImage = getattr(costume_battle_assets, value)
            # 绿标的坐标点范围不变
            if key == 'I_LOCAL':
                self.replace_img(key, assert_value, rp_roi_back=False)
            else:
                self.replace_img(key, assert_value)


if __name__ == '__main__':
    c = CostumeBase()
    c.check_costume_main(MainType.COSTUME_MAIN_2)
