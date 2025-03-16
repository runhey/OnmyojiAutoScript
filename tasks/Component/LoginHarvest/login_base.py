# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from module.atom.image import RuleImage
from module.logger import logger
from tasks.Restart.assets import RestartAssets
from tasks.Component.Costume.config import (MainType, CostumeConfig)

# 庭院皮肤
# 主界面皮肤（使用字典推导式动态生成）
login_harvest_model = {
    getattr(MainType, f"COSTUME_MAIN_{i}"): {
        'I_HARVEST_JADE': f'I_HARVEST_JADE_{i}',
        'I_HARVEST_SIGN': f'I_HARVEST_SIGN_{i}',
        'I_HARVEST_SIGN_999': f'I_HARVEST_SIGN_999_{i}',
        'I_HARVEST_AP': f'I_HARVEST_AP_{i}',
        'I_HARVEST_SOUL': f'I_HARVEST_SOUL_{i}',
    } for i in range(1, 12)
}


class LoginBase:

    def check_login(self, config: CostumeConfig=None):
        if config is None:
            config: CostumeConfig = self.config.model.global_game.costume_config
        self.check_login_harvest(config.costume_main_type)

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
        logger.info(f'Replace {asset_before} to {asset_after}')
        logger.info(f'{asset_before} roi_front: {asset_before_object.roi_front}')

    def check_login_harvest(self, main_type: MainType):
        if main_type == MainType.COSTUME_MAIN:
            return
        logger.info(f'Switch main costume to {main_type}')
        restart_assets = RestartAssets()
        for key, value in login_harvest_model[main_type].items():
            if not hasattr(restart_assets, value):
                return
            assert_value: RuleImage = getattr(restart_assets, value)


if __name__ == '__main__':
    pass
    # c = CostumeBase()
    # c.check_costume_main(MainType.COSTUME_MAIN_2)
