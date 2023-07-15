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

    def run_replace(self, shikigami_class: ShikigamiClass = ShikigamiClass.N, shikigami_order: int = 7):
        """
        要求在式神育成的界面
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
            if self.appear_then_click(check_click, interval=0.5):
                continue
            if self.click(self.C_SHIKIGAMI_SWITCH_1, interval=3):
                continue
        logger.info('Select shikigami class: %s' % shikigami_class)

        #
