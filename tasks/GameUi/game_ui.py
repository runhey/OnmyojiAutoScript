# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
from datetime import datetime
from time import sleep

import random
from collections import deque
from module.atom.gif import RuleGif
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
        page_climb_act_boss, page_climb_act_buff, page_climb_act_ap100,
        # 战斗
        page_battle_auto, page_battle_hand, page_reward, page_failed
    ]
    ui_close = [GameUiAssets.I_BACK_MALL, GeneralBattleAssets.I_CONFIRM,
                BaseTask.I_UI_BACK_RED, BaseTask.I_UI_BACK_YELLOW,
                GameUiAssets.I_BACK_FRIENDS, GameUiAssets.I_BACK_DAILY,
                GameUiAssets.I_REALM_RAID_GOTO_EXPLORATION,
                GameUiAssets.I_SIX_GATES_GOTO_EXPLORATION, SixRealmsAssets.I_EXIT_SIXREALMS,
                ActivityShikigamiAssets.I_SKIP_BUTTON, ActivityShikigamiAssets.I_RED_EXIT, BaseTask.I_UI_BACK_BLUE,
                ActivityShikigamiAssets.I_RED_EXIT_2]

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

    def ui_page_appear(self, page: Page, skip_first_screenshot: bool = True, interval: float = random.uniform(0.5, 1)):
        """
        判断当前页面是否为page
        """
        if interval:
            interval_timer = Timer(interval).start()
            interval_timer.wait()
        self.screenshot(skip_first_screenshot)
        if isinstance(page.check_button, list):
            for button in page.check_button:
                if self.appear(button):
                    return True
            return False
        return self.appear(page.check_button)

    def ui_wait_until_appear(self, page: Page, timeout: float = 3, interval: float = 0.5,
                             skip_first_screenshot: bool = True) -> bool:
        """
        等待页面出现
        """
        logger.info(f'Waiting for {page}')
        timeout_timer = Timer(timeout).start()
        interval_timer = Timer(interval).start()
        while not timeout_timer.reached():
            if self.ui_page_appear(page, skip_first_screenshot):
                return True
            skip_first_screenshot = False
            interval_timer.wait().reset()
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
            self.screenshot(skip_first_screenshot)
            skip_first_screenshot = False
            # 如果20S还没有到底，那么就抛出异常
            if timeout.reached():
                break
            # Known pages
            for page in self.ui_pages:
                if not page.check_button:
                    continue
                if self.ui_page_appear(page=page, interval=None):
                    logger.attr("UI", page.name)
                    self.ui_current = page
                    return page
            # Try to close unknown page
            if self.try_close_unknown_pages():
                timeout = Timer(10, count=20).start()
            # wait to ui
            sleep(random.uniform(0.4, 0.8))
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
        if getattr(button, 'name', None) and button.name in self.interval_timer:
            self.interval_timer[button.name].reset()

    def build_reverse_path_dict(self, destination: Page) -> dict[Page, list[Page]]:
        """
        构建从每个页面到目标页面的最短路径（反向 BFS）

        Returns:
            dict[Page, list[Page]] -> {start_page: [page1, ...destinationPage], ...}
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
        return paths

    def build_reverse_paths(self, destination: Page) -> list[tuple[Page, list[Page]]]:
        """
        构建从每个页面到目标页面的最短路径（反向 BFS）
        路径从短到长排序

        Returns:
            [(start_page, [page1, ...destinationPage]), ...]
        """
        paths = self.build_reverse_path_dict(destination)
        # 转换成列表并按路径长度排序, 短到长
        sorted_paths = sorted(paths.items(), key=lambda kv: len(kv[1]))
        return sorted_paths

    def ui_goto(self, destination: Page, confirm_wait=0, skip_first_screenshot=True, timeout: int = 60):
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
        close_unknown_timer = Timer(3).start()
        # 构建路径映射
        path_dict = self.build_reverse_path_dict(destination)

        found = False
        while not timeout_timer.reached():
            if found:
                confirm_timer.wait()
                return True
            confirm_timer.reset()
            path = path_dict.get(self.ui_current, None)
            # 找不到路径则重新获取页面重试
            if not path:
                self.ui_get_current_page(skip_first_screenshot)
                continue
            skip_first_screenshot = False
            logger.info(f"Current page: {self.ui_current}. Following shortest path:")
            show_paths: str = ' -> '.join([p.name for p in path])
            logger.info(f"{show_paths}")
            # 遍历路径
            found = self._execute_path(path, timeout_timer)
            if not found:
                if close_unknown_timer.reached_and_reset():
                    self.try_close_unknown_pages(skip_screenshot=False)
        else:
            logger.error(f'Cannot goto page[{destination}], timeout[{timeout}s] reached')
        return False

    def try_close_unknown_pages(self, skip_screenshot: bool = True):
        """
        尝试关闭未知界面
        :return: 执行了关闭返回True, 否则False
        """
        self.screenshot(skip_screenshot)
        timer = Timer(None).start()
        logger.warning('Trying to switch to supported page')
        operated = False
        for close in self.ui_close:
            if self.appear_then_click(close, interval=1.5):
                logger.info(f'[{timer.current():.1f}s]Click {close} on {self.ui_current} success')
                operated = True
        return operated

    def _execute_path(self, path: list, timeout_timer):
        """
        执行路径
        :param path: currentPage,page1,page2,...,destinationPage
        :param timeout_timer: 超时定时器
        :return: currentPage==destinationPage
        """
        for i, current_page in enumerate(path):
            if timeout_timer.reached():
                return False
            # 当前页不等于路径中对应页, 尝试下一页
            if self.ui_current != current_page:
                continue
            self.run_additional(current_page)
            # 如果已经是最后一页，不再跳转
            if i == len(path) - 1:
                break
            next_page = path[i + 1]
            logger.info(f'Page switch: {current_page} -> {next_page}')
            # 获取页面跳转操作
            button = current_page.links.get(next_page)
            if not button:
                logger.warning(f"No link from {current_page} to {next_page}")
                continue
            # 跳转页面
            max_wait_timer = Timer(5).start()
            while not max_wait_timer.reached():
                if timeout_timer.reached():
                    return False
                if self.appear_then_operate(button, skip_first_screenshot=False):
                    break
                logger.warning(f"[{max_wait_timer.current():.1f}s]Failed click {button} on {current_page}, retry...")
                sleep(0.3)
            else:
                self.ui_get_current_page(skip_first_screenshot=False)
                # 当前页面不是对应路径的页面, 则尝试下一个页面
                if self.ui_current != current_page:
                    continue
            max_wait_timer.reset()
            while not max_wait_timer.reached():
                if timeout_timer.reached():
                    return False
                if self.ui_wait_until_appear(next_page, timeout=1.5, interval=random.uniform(0.4, 0.8),
                                             skip_first_screenshot=False):
                    logger.info(f'[{max_wait_timer.current():.1f}s]Page arrived {next_page}')
                    self.ui_current = next_page
                    break
            else:
                # 重新获取当前页
                self.ui_get_current_page(skip_first_screenshot=False)
        return self.ui_current == path[-1]

    def run_additional(self, page: Page):
        """执行页面附加操作"""
        if not page.additional:
            return
        for btn in page.additional:
            if self.appear_then_operate(btn, skip_first_screenshot=False, interval=random.uniform(0.4, 0.6)):
                logger.info(f'Page {page} additional {btn} clicked')

    def appear_then_operate(self, target: RuleList | RuleImage | RuleGif | RuleOcr | RuleClick,
                            interval: float = random.uniform(0.6, 1.2), skip_first_screenshot: bool = True):
        self.ui_button_interval_reset(target)
        interval_timer = Timer(interval).start()
        interval_timer.wait()
        self.screenshot(skip_first_screenshot)
        if isinstance(target, RuleList):
            return self.list_appear_click(target)
        if isinstance(target, (RuleImage, RuleGif)):
            return self.appear_then_click(target)
        if isinstance(target, RuleOcr):
            return self.ocr_appear_click(target)
        if isinstance(target, RuleClick):
            self.click(target)
            return True

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
