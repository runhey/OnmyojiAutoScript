# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey


from tasks.base_task import BaseTask
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.GeneralInvite.general_invite import GeneralInvite
from tasks.Component.GeneralBuff.general_buff import GeneralBuff
from tasks.Component.GeneralRoom.general_room import GeneralRoom
from tasks.GameUi.game_ui import GameUi
from tasks.Orochi.assets import OrochiAssets
from tasks.Orochi.config import Orochi, UserStatus
from module.logger import logger

class ScriptTask(GeneralBattle, GeneralInvite, GeneralBuff, GeneralRoom, GameUi, OrochiAssets):

    def run(self) -> bool:
        config: Orochi = self.config.orochi
        if config.orochi_config.soul_buff_enable:
            self.open_buff()
            self.soul(is_open=True)
            self.close_buff()

        match config.orochi_config.user_status:
            case UserStatus.LEADER: self.run_leader()
            case UserStatus.MEMBER: self.run_member()
            case UserStatus.ALONE: self.run_alone()
            case UserStatus.WILD: self.run_wild()
            case _: logger.error('Unknown user status')


    def check_layer(self, layer: str) -> bool:
        """
        检查挑战的层数, 并选中挑战的层
        :return:
        """
        pos = self.list_find(self.L_LAYER_LIST, layer)
        if pos:
            self.device.click(x=pos[0], y=pos[1])
            return True


    def run_leader(self):
        pass

    def run_member(self):
        pass

    def run_alone(self):
        pass

    def run_wild(self):
        logger.error('Wild mode is not implemented')
        pass






if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.check_layer('陆')







