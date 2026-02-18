# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey


from module.logger import logger
from module.base.timer import Timer

from tasks.KekkaiActivation.script_task import ScriptTask as KekkaiActivationScriptTask

class ScriptTask(KekkaiActivationScriptTask):

    def run(self):
        """
        测试多尺度匹配在默认鲤鱼旗皮肤下的识别效果
        验证同一张图片能否识别不同缩放大小的按钮
        """
        logger.hr('Multi-Scale Matching Test - Default Skin')
        logger.info('Testing if one image can recognize scaled versions of 育成 button')

        images_count = [[self.I_SHI_GROWN,     0, 0],  # 式神育成
                        [self.I_SHI_CARD,      0, 0],  # 结界卡
                        [self.I_SHI_DEFENSE,   0, 0],  # 结界防守
                        [self.I_REALM_SHIN,    0, 0],  # 结界皮肤
                        [self.I_CARD_EXP,      0, 0],  # 收取经验
                        [self.I_BOX_AP,        0, 0],  # 收取体力
                        [self.I_BOX_EXP,       0, 0],  # 收取盒子经验
                        [self.I_BOX_EXP_MAX,   0, 0],  # 收取盒子经验（满）
                        [self.I_UTILIZE_EXP,   0, 0],  # 收取寄养经验
                        ]

        timer = Timer(10)
        timer.start()
        logger.info('Testing for 10 seconds...')
        while 1:
            self.screenshot()

            for i in images_count:
                # 普通匹配
                if self.appear(i[0]):
                    i[1] += 1
                # 多尺度匹配
                if self.appear_multi_scale(i[0]):
                    i[2] += 1

            if timer.reached():
                break

        print('\n' + '=' * 70)
        print('%-20s   %8s   %8s' % ('Image', 'Normal', 'Multi-Scale'))
        print('=' * 70)
        for i in images_count:
            if i[1] > 0 or i[2] > 0:  # 只显示有匹配结果的
                print('%-20s %8d   %8d' % (str(i[0]), i[1], i[2]))
        print('=' * 70)

        logger.info('Test completed')


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.run()