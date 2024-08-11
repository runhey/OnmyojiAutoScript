# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey


from module.logger import logger
from module.base.timer import Timer

from tasks.KekkaiActivation.script_task import ScriptTask as KekkaiActivationScriptTask
from tasks.Component.Costume.config import RealmType

class ScriptTask(KekkaiActivationScriptTask):

    def run(self):

        images_count = [[self.I_SHI_GROWN,     0],  # 式神育成
                        [self.I_SHI_CARD,      0],  # 结界卡
                        [self.I_SHI_DEFENSE,   0],  # 结界防守
                        [self.I_REALM_SHIN,    0],  # 结界皮肤
                        # 下面是测试的时候不一定有的， 但是这三个运行一段时间后应该会有
                        [self.I_CARD_EXP,      0],  # 收取经验（没有满的图）
                        [self.I_BOX_AP,        0],  # 收取体力（没有满的图）
                        [self.I_BOX_EXP,       0],  # 收取盒子经验（没有满）
                        # 下面两个才是很难有
                        [self.I_BOX_EXP_MAX,   0],  # 收取盒子经验（经验满）
                        [self.I_UTILIZE_EXP,   0],  # 收取寄养别人的经验
                        ]

        logger.hr('Costume Test Start')
        timer = Timer(5)
        timer.start()
        while 1:
            self.screenshot()
            logger.info('Detecting images...')

            for i in images_count:
                if self.appear(i[0]):
                    i[1] += 1
                    # logger.info('Find image %s %d times' % (i[0], i[1]))

            if timer.reached():
                # 五秒测试结束
                logger.info('Five seconds test over')
                break

        print('--------------------------------------------------------')
        print('%-20s   %s' % ('Image', 'Count'))
        for i in images_count:
            print('%-20s %3d times' % (i[0], i[1]))
        logger.info('Test Done')

    def set_costume(self, costume: RealmType=RealmType.COSTUME_REALM_DEFAULT):
        self.config.model.global_game.costume_config.costume_realm_type = costume
        self.check_costume()
        logger.info('Set costume to %s' % self.config.model.global_game.costume_config.costume_realm_type)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.set_costume(RealmType.COSTUME_REALM_2)
    t.run()


