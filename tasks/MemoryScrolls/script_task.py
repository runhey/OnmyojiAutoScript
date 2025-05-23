from module.base.base import ModuleBase
from module.exception import TaskError
from module.logger import logger
from .assets import MemoryScrollsAssets as MS
from .config import MemoryScrollsConfig, ScrollNumber


class MemoryScrolls(ModuleBase):
    def __init__(self, config: MemoryScrollsConfig):
        super().__init__(config)
        self.config = config
        self.scroll_map = {
            ScrollNumber.SCROLL_1: MS.C_MS_SCROLL_1,
            ScrollNumber.SCROLL_2: MS.C_MS_SCROLL_2,
            ScrollNumber.SCROLL_3: MS.C_MS_SCROLL_3,
            ScrollNumber.SCROLL_4: MS.C_MS_SCROLL_4,
            ScrollNumber.SCROLL_5: MS.C_MS_SCROLL_5,
            ScrollNumber.SCROLL_6: MS.C_MS_SCROLL_6,
        }

    def run(self):
        """主任务入口"""
        logger.hr("开始绘卷任务", level=1)

        try:
            # 1. 进入绘卷界面
            self._enter()

            # 2. 选择指定分卷
            self._select_scroll()

            # 3. 处理贡献流程
            self._process_contribution()

            # 4. 退出界面
            self._exit()

            logger.info("绘卷任务完成")
            return True
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            return False

    def _enter(self):
        """进入绘卷主界面"""
        logger.info("尝试进入绘卷界面")
        for _ in range(3):
            if self.appear(MS.I_MS_MAIN):
                break
            if self.appear(MS.I_MS_ENTER):
                self.click(MS.C_MS_ENTER)
                if self.wait_until(MS.I_MS_MAIN):
                    break
        else:
            raise TaskError("无法进入绘卷界面")

    def _select_scroll(self):
        """选择配置的分卷"""
        scroll_number = self.config.memory_scrolls_config.scroll_number
        logger.info(f"选择分卷{scroll_number.value}")
        self.click(self.scroll_map[scroll_number])

    def _process_contribution(self):
        """处理碎片贡献流程"""
        logger.info("开始处理碎片贡献")

        while True:
            # 检查是否已完成
            if self.appear(MS.I_MS_COMPLETE):
                logger.info("当前分卷已完成")
                break

            # 检查是否在正确界面
            if not self.appear(MS.I_MS_CONTRIBUTE):
                logger.warning("不在贡献界面，重新开始")
                return self.run()

            # 处理小碎片
            if not self.appear(MS.I_MS_ZERO_S):
                logger.info("贡献小碎片")
                self.swipe(MS.S_MS_SWIPE_S)
                self.click(MS.C_MS_CONTRIBUTE)
                if self.wait_until(MS.I_MS_CONTRIBUTED):
                    self.click(MS.C_MS_CONTRIBUTED)
                continue

            # 处理中碎片
            if not self.appear(MS.I_MS_ZERO_M):
                logger.info("贡献中碎片")
                self.swipe(MS.S_MS_SWIPE_M)
                self.click(MS.C_MS_CONTRIBUTE)
                if self.wait_until(MS.I_MS_CONTRIBUTED):
                    self.click(MS.C_MS_CONTRIBUTED)
                continue

            # 处理大碎片
            if not self.appear(MS.I_MS_ZERO_L):
                logger.info("贡献大碎片")
                self.swipe(MS.S_MS_SWIPE_L)
                self.click(MS.C_MS_CONTRIBUTE)
                if self.wait_until(MS.I_MS_CONTRIBUTED):
                    self.click(MS.C_MS_CONTRIBUTED)
                continue

            # 所有碎片都已贡献
            logger.info("当前分卷所有碎片已贡献完毕")
            break

    def _exit(self):
        """退出绘卷界面"""
        logger.info("退出绘卷界面")
        self.click(MS.C_MS_CLOSE)
        self.click(MS.C_MS_BACK)