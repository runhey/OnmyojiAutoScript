# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from module.atom.ocr import RuleOcr
from module.atom.image import RuleImage
from module.logger import logger

from tasks.base_task import BaseTask
from tasks.Utils.config_enum import ShikigamiClass
from tasks.Component.ReplaceShikigami.assets import ReplaceShikigamiAssets


class ReplaceShikigami(BaseTask, ReplaceShikigamiAssets):


    def in_shikigami_growth(self, screenshot=False) -> bool:
        # 判定是否在式神育成界面
        # 判定的依据是是否出现了 式神录 这个图片
        if screenshot:
            self.screenshot()
        return self.appear(self.I_RS_RECORDS_SHIKI, interval=0.5)

    def switch_shikigami_class(self, shikigami_class: ShikigamiClass = ShikigamiClass.N):
        """
        要求在式神育成的界面
        切换分类
        :param shikigami_class:
        :param shikigami_order:
        :return:
        """
        match_selected = {ShikigamiClass.MATERIAL: self.I_RS_MATERIAL_SELECTED,
                          ShikigamiClass.N: self.I_RS_N_SELECTED,
                          ShikigamiClass.R: self.I_RS_R_SELECTED,
                          ShikigamiClass.SR: self.I_RS_SR_SELECTED,
                          ShikigamiClass.SSR: self.I_RS_SSR_SELECTED,
                          ShikigamiClass.SP: self.I_RS_SP_SELECTED}
        match_click = {ShikigamiClass.MATERIAL: self.I_RS_MATERIAL,
                       ShikigamiClass.N: self.I_RS_N,
                       ShikigamiClass.R: self.I_RS_R,
                       ShikigamiClass.SR: self.I_RS_SR,
                       ShikigamiClass.SSR: self.I_RS_SSR,
                       ShikigamiClass.SP: self.I_RS_SP}
        check_selected = match_selected[shikigami_class]
        check_click = match_click[shikigami_class]
        # 选择式神的种类
        while 1:
            self.screenshot()

            if self.appear(check_selected):
                break
            if self.appear_then_click(check_click, interval=1):
                continue
            if self.click(self.C_SHIKIGAMI_SWITCH_1, interval=3):
                continue
        logger.info('Select shikigami class: %s' % shikigami_class)

    def unset_shikigami_max_lv(self):
        """
        要求在式神育成的界面
        拉下满级的式神，留空位置
        :return:
        """
        while 1:
            self.screenshot()
            if not self.appear(self.I_RS_LEVEL_MAX):
                break
            else:
                self.appear_then_click(self.I_RS_LEVEL_MAX, interval=0.5)
        logger.info('Unset all shikigami max lv')

    def set_shikigami(self, shikigami_order: int = 7, stop_image: RuleImage = None):
        """
        要求在式神育成的界面
        选择式神 1-7
        :param stop_image:  结束的图片，如果不出现就结束
        :param shikigami_order:
        :return:
        """
        # 选择式神
        _click_match = {1: self.C_SHIKIGAMI_LEFT_1,
                        2: self.C_SHIKIGAMI_LEFT_2,
                        3: self.C_SHIKIGAMI_LEFT_3,
                        4: self.C_SHIKIGAMI_LEFT_4,
                        5: self.C_SHIKIGAMI_LEFT_5,
                        6: self.C_SHIKIGAMI_LEFT_6,
                        7: self.C_SHIKIGAMI_LEFT_7}
        click_match = _click_match[shikigami_order]
        while 1:
            self.screenshot()

            if not self.appear(stop_image):
                break

            if self.appear_then_click(self.I_U_CONFIRM_SMALL, interval=0.5):
                continue

            if self.click(click_match, interval=1.5):
                continue
            if self.click(_click_match[6], interval=4.5):
                # 有的时候第七个格子被占用到寄养上去了
                # 导致一直无法选上
                continue
            if self.appear_then_click(self.I_U_CIRCLE_ALTERNATE, interval=2.5):
                self.appear_then_click(self.I_U_CONFIRM_ALTERNATE, interval=1.5)
                continue
        logger.info('Set shikigami: %d' % shikigami_order)

    def detect_no_shikigami(self) -> bool:
        self.screenshot()
        if self.appear(self.I_DETECT_EMPTY_1)\
            and self.appear(self.I_DETECT_EMPTY_2) \
                and self.appear(self.I_DETECT_EMPTY_3) \
                and self.appear(self.I_DETECT_EMPTY_4) \
                and self.appear(self.I_DETECT_EMPTY_5) \
                and self.appear(self.I_DETECT_EMPTY_6):
            return True
        return False
