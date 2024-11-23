from tasks.Component.SwitchAccount.assets import SwitchAccountAssets
from tasks.base_task import BaseTask
from module.logger import logger


class ExitGame(BaseTask, SwitchAccountAssets):

    def exitGame(self):
        logger.info("start game exit")
        # 打开该页面比较慢 如果interval短 将发生异常
        self.ui_click(self.C_SA_EG_PROFILE_PHOTO, self.I_SA_USER_CENTER_PROFILE, 3)
        self.ui_click(self.I_SA_USER_CENTER, self.I_SA_SWITCH_ACCOUNT_BTN, 6)
        self.ui_click_until_disappear(self.I_SA_SWITCH_ACCOUNT_BTN, 3)
