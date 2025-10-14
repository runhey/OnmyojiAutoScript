# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
from time import sleep
from collections import deque
from module.atom.image import RuleImage
from module.atom.list import RuleList
from module.atom.ocr import RuleOcr
from module.base.decorator import run_once
from module.base.timer import Timer
from module.exception import (GameNotRunningError, GamePageUnknownError)
from module.logger import logger
from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.page import *
from tasks.Restart.assets import RestartAssets
from tasks.SixRealms.assets import SixRealmsAssets
from tasks.base_task import BaseTask
from tasks.ActivityShikigami.assets import ActivityShikigamiAssets


class GameUi(BaseTask, GameUiAssets):
    ui_current: Page = None
    ui_pages = [
        # 登录
        page_login,
        # 主页
        page_main, page_summon, page_exploration, page_town,
        # 探索的
        page_awake_zones, page_soul_zones, page_realm_raid, page_goryou_realm, page_delegation,
        page_secret_zones, page_area_boss, page_heian_kitan, page_six_gates, page_bondling_fairyland,
        page_kekkai_toppa,
        # 町中的
        page_duel, page_demon_encounter, page_hunt, page_hunt_kirin, page_draft_duel, page_hyakkisen,
        # 庭院里面的
        page_shikigami_records, page_onmyodo, page_friends, page_daily, page_mall, page_guild, page_team,
        page_collection, page_act_list,
        # 爬塔活动
        page_act_list_climb_act, page_climb_act, page_climb_act_2, page_climb_act_pass, page_climb_act_ap,
        page_climb_act_boss, page_climb_act_buff,
        # 战斗
        page_battle_auto, page_battle_hand, page_reward
    ]
    ui_close = [GameUiAssets.I_BACK_MALL, GeneralBattleAssets.I_CONFIRM,
                BaseTask.I_UI_BACK_RED, BaseTask.I_UI_BACK_YELLOW, BaseTask.I_UI_BACK_BLUE,
                GameUiAssets.I_BACK_FRIENDS, GameUiAssets.I_BACK_DAILY,
                GameUiAssets.I_REALM_RAID_GOTO_EXPLORATION,
                GameUiAssets.I_SIX_GATES_GOTO_EXPLORATION, SixRealmsAssets.I_EXIT_SIXREALMS,
                ActivityShikigamiAssets.I_SKIP_BUTTON, ActivityShikigamiAssets.I_RED_EXIT, ActivityShikigamiAssets.I_RED_EXIT_2]

    def home_explore(self) -> bool:
        """
        使用ocr识别到探索按钮并点击
        :return:
        """
        while 1:
            self.screenshot()
            if self.ocr_appear_click(self.O_HOME_EXPLORE, interval=2):
                continue
            if self.appear(self.I_BACK_BLUE, threshold=0.6):
                break
        logger.info(f'Click {self.O_HOME_EXPLORE.name}')
        return True

    def explore_home(self) -> bool:
        """

        :return:
        """
        while 1:
            self.screenshot()
            if self.appear_then_click(self.I_BACK_BLUE, threshold=0.6, interval=2):
                continue
            if self.appear(self.I_HOME_SHIKIKAMI, threshold=0.6):
                break
        logger.info(f'Click {self.I_HOME_SHIKIKAMI.name}')
        return True

    def ui_page_appear(self, page):
        """
        判断当前页面是否为page
        """
        if isinstance(page.check_button, list):
            for button in page.check_button:
                if self.appear(button):
                    return True
            return False
        return self.appear(page.check_button)

    def ui_wait_until_appear(self, page: Page, timeout: int = 3, interval: float = 0.5) -> bool:
        """
        等待页面出现
        """
        logger.info(f'Waiting for {page}')
        timeout_timer = Timer(timeout).start()
        while not timeout_timer.reached():
            self.screenshot()
            if self.ui_page_appear(page):
                return True
            sleep(interval)
        return False

    def ensure_scroll_open(self):
        """
        判断庭院界面卷轴是否打开
        """
        return self.appear(RestartAssets.I_LOGIN_SCROOLL_CLOSE)

    def ensure_button_execute(self, button):
        """
        确保button执行
        """
        if isinstance(button, RuleImage) and self.appear(button):
            return True
        elif callable(button) and button():
            return True
        else:
            return False

    def ui_get_current_page(self, skip_first_screenshot=True) -> Page:
        """
        获取当前页面
        :param skip_first_screenshot:
        :return:
        """
        logger.info("UI get current page")

        @run_once
        def app_check():
            if not self.device.app_is_running():
                raise GameNotRunningError("Game not running")

        @run_once
        def minicap_check():
            if self.config.script.device.control_method == "uiautomator2":
                self.device.uninstall_minicap()

        @run_once
        def rotation_check():
            self.device.get_orientation()

        timeout = Timer(10, count=20).start()
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
                if not hasattr(self.device, "image") or self.device.image is None:
                    self.screenshot()
            else:
                self.screenshot()
            # 如果20S还没有到底，那么就抛出异常
            if timeout.reached():
                break
            # Known pages
            for page in self.ui_pages:
                if not page.check_button:
                    continue
                if self.ui_page_appear(page=page):
                    logger.attr("UI", page.name)
                    self.ui_current = page
                    if page == page_main and self.ensure_scroll_open():
                        self.ui_click_until_disappear(RestartAssets.I_LOGIN_SCROOLL_CLOSE)
                    return page
            # Try to close unknown page
            for close in self.ui_close:
                if self.appear_then_click(close, interval=1.5):
                    logger.info('Trying to switch to supported page')
                    timeout = Timer(10, count=20).start()
            app_check()
            minicap_check()
            rotation_check()
        # Unknown page, need manual switching
        logger.warning("Unknown ui page")
        logger.attr("EMULATOR__SCREENSHOT_METHOD", self.config.script.device.screenshot_method)
        logger.attr("EMULATOR__CONTROL_METHOD", self.config.script.device.control_method)
        logger.warning("Starting from current page is not supported")
        logger.warning(f"Supported page: {[str(page) for page in self.ui_pages]}")
        logger.warning('Supported page: Any page with a "HOME" button on the upper-right')
        logger.critical("Please switch to a supported page before starting oas")
        raise GamePageUnknownError

    def ui_button_interval_reset(self, button):
        """
        Reset interval of some button to avoid mistaken clicks

        Args:
            button (Button):
        """
        pass

    def build_reverse_paths(self, destination: Page) -> list[tuple[Page, list[Page]]]:
        """
        构建从每个页面到目标页面的最短路径（反向 BFS）
        并按路径长度从短到长排序返回。

        Returns:
            list[tuple[Page, list[Page]]] -> [(start_page, [path...destinationPage]), ...]
        """
        paths = {destination: [destination]}
        queue = deque([destination])
        while queue:
            cur = queue.popleft()
            for page in self.ui_pages:
                if page not in paths and cur in page.links:
                    # page -> cur
                    paths[page] = [page] + paths[cur]
                    queue.append(page)
        # 转换成列表并按路径长度排序, 短到长
        sorted_paths = sorted(paths.items(), key=lambda kv: len(kv[1]))
        return sorted_paths

    def ui_goto(self, destination: Page, confirm_wait=0, skip_first_screenshot=True, timeout: int = 45):
        """
        Args:
            destination (Page):
            confirm_wait:
            skip_first_screenshot:
        :return: find destination page or timeout reached
        """
        logger.hr(f"UI goto {destination}")
        # 初始化
        timeout_timer = Timer(timeout).start()
        confirm_timer = Timer(confirm_wait, count=int(confirm_wait // 0.5)).start()
        try_close_unknown_timer = Timer(3).start()
        # 构建路径映射并排序
        paths = self.build_reverse_paths(destination)

        while not timeout_timer.reached():
            if not skip_first_screenshot:
                self.screenshot()
            skip_first_screenshot = False
            # 已经在目标页面
            if self.ui_page_appear(destination):
                if confirm_timer.reached():
                    logger.info(f'Page arrive: {destination}')
                    break
                confirm_timer.reset()
                continue
            # 尝试关闭未知页面
            if try_close_unknown_timer.reached():
                for close in self.ui_close:
                    if self.appear_then_click(close, interval=1.5):
                        logger.warning('Trying to switch to supported page')
                try_close_unknown_timer.reset()
            # 遍历所有路径，优先尝试最短路径
            for page, path in paths:
                if not self.ui_page_appear(page):
                    continue
                logger.info(f"Current page: {page}. Following shortest path:")
                show_paths: str = ' -> '.join([p.name for p in path])
                logger.info(f" {show_paths}")
                if self._execute_path(path, confirm_timer, timeout_timer):
                    return True
            sleep(0.3)
        else:
            logger.error(f'Cannot goto page[{destination}], timeout[{timeout}s] reached')
        return False

    def _execute_path(self, path: list, confirm_timer, timeout_timer):
        """
        执行路径
        :param path: currentPage,page1,page2,...,destinationPage
        :param confirm_timer: 确认定时器
        :param timeout_timer: 超时定时器
        :return: currentPage==destinationPage
        """
        for i in range(len(path) - 1):
            current_page, next_page = path[i], path[i + 1]
            # 已超时则不再遍历
            if timeout_timer.reached():
                return False
            # 等待当前页面出现
            self.ui_wait_until_appear(current_page)
            logger.info(f'Page switch: {current_page} -> {next_page}')
            # 执行附加操作
            if current_page.additional:
                for button in current_page.additional:
                    if ((isinstance(button, RuleClick) and self.click(button)) or
                            self.appear_then_click(button, interval=0.6) or
                            (isinstance(button, RuleOcr) and self.ocr_appear_click(button, interval=2))):
                        logger.info(f'Page {current_page} additional {button} clicked')
                        # 每次点击之间添加随机延迟, 等待响应
                        sleep(random.uniform(0.2, 0.6))
            # 执行页面跳转
            button = current_page.links.get(next_page)
            if not button:
                logger.warning(f"No link from {current_page} to {next_page}")
                return False
            # 执行对应操作
            if ((isinstance(button, RuleList) and self.list_appear_click(button)) or
                    (isinstance(button, RuleClick) and self.click(button)) or
                    self.appear_then_click(button, interval=2) or
                    (isinstance(button, RuleOcr) and self.ocr_appear_click(button, interval=2))):
                self.ui_button_interval_reset(button)
                confirm_timer.reset()
            else:
                logger.warning(f"Failed to click {button} on {current_page}")
                return False
        # 最后确认目标页面
        return self.ui_page_appear(path[-1])

    # ------------------------------------------------------------------------------------------------------------------
    # 下面的这些是一些特殊的页面，需要额外处理
    # ------------------------------------------------------------------------------------------------------------------

    def main_goto_daily(self):
        """
        无法直接一步到花合战，需要先到主页，然后再到花合战
        :return:
        """
        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_DAILY):
                break
            if self.appear_then_click(self.I_MAIN_GOTO_DAILY, interval=1):
                continue
            if self.ocr_appear_click(self.O_CLICK_CLOSE_1, interval=1):
                continue
            if self.ocr_appear_click(self.O_CLICK_CLOSE_2, interval=1):
                continue
        logger.info('Page arrive: Daily')
        time.sleep(1)
        return


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas2')
    d = Device(c)
    game = GameUi(config=c, device=d)
    game.ui_get_current_page()
    game.ui_goto(page_main)
