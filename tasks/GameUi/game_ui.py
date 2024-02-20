# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import time
from time import sleep

from module.base.decorator import run_once
from module.base.timer import Timer
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr

from tasks.GameUi.assets import GameUiAssets
from tasks.GameUi.page import *
from tasks.base_task import BaseTask
from module.logger import logger
from module.exception import (GameNotRunningError, GamePageUnknownError, RequestHumanTakeover)


class GameUi(BaseTask, GameUiAssets):
    ui_current: Page = None
    ui_pages = [page_main, page_summon, page_exploration, page_town,
                # 探索的
                page_awake_zones, page_soul_zones, page_realm_raid, page_goryou_realm, page_delegation,
                page_secret_zones, page_area_boss, page_heian_kitan, page_six_gates, page_bondling_fairyland,
                page_kekkai_toppa,
                # 町中的
                page_duel, page_demon_encounter, page_hunt, page_draft_duel, page_hyakkisen,
                # 庭院里面的
                page_shikigami_records, page_onmyodo, page_friends, page_daily, page_mall, page_guild, page_team,
                page_collection
                ]
    ui_close = [GameUiAssets.I_BACK_MALL,
                BaseTask.I_UI_BACK_RED, BaseTask.I_UI_BACK_YELLOW, BaseTask.I_UI_BACK_BLUE,
                GameUiAssets.I_BACK_FRIENDS, GameUiAssets.I_BACK_DAILY,
                GameUiAssets.I_REALM_RAID_GOTO_EXPLORATION,
                GameUiAssets.I_SIX_GATES_GOTO_EXPLORATION]

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
        return self.appear(page.check_button)

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

            # End
            # 如果20S还没有到底，那么就抛出异常
            if timeout.reached():
                break

            # Known pages
            for page in self.ui_pages:
                if page.check_button is None:
                    continue
                if self.ui_page_appear(page=page):
                    logger.attr("UI", page.name)
                    self.ui_current = page
                    return page
            # Try to close unknown page
            for close in self.ui_close:
                if self.appear_then_click(close, interval=1.5):
                    logger.info('Trying to switch to supported page')
                    timeout = Timer(10, count=20).start()
            # Unknown page but able to handle
            # logger.info("Unknown ui page")
            # if self.appear_then_click(GOTO_MAIN, offset=(30, 30), interval=2) or self.ui_additional():
            #     timeout.reset()
            #     continue

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

    def ui_goto(self, destination: Page, confirm_wait=0, skip_first_screenshot=True):
        """
        Args:
            destination (Page):
            confirm_wait:
            skip_first_screenshot:
        """
        # Reset connection
        for page in self.ui_pages:
            page.parent = None

        # Create connection
        visited = [destination]
        visited = set(visited)
        # 广度优先搜索
        while 1:
            new = visited.copy()
            for page in visited:
                for link in self.ui_pages:
                    if link in visited:
                        continue
                    if page in link.links:
                        link.parent = page
                        new.add(link)
            # 没有新的页面加入，说明已经遍历完毕
            if len(new) == len(visited):
                break
            visited = new

        logger.hr(f"UI goto {destination}")
        confirm_timer = Timer(confirm_wait, count=int(confirm_wait // 0.5)).start()
        while 1:
            if skip_first_screenshot:
                skip_first_screenshot = False
            else:
                self.screenshot()

            # Destination additional button
            if destination.additional and isinstance(destination.additional, list):
                appear = False
                for button in destination.additional:
                    if self.appear_then_click(button, interval=0.6):
                        appear = True
                        logger.info(f'Page {destination} AB {button} clicked')
                if appear:
                    continue

            # Destination page
            if self.appear(destination.check_button):
                if confirm_timer.reached():
                    logger.info(f'Page arrive: {destination}')
                    break
            else:
                confirm_timer.reset()

            # Other pages
            clicked = False
            for page in visited:
                if page.parent is None or page.check_button is None:
                    continue
                # 如果当前页面不出现可以检测当前按键的按钮，那可能是有一些弹窗，广告，这个时候额外处理
                # if page.additional:
                #     if not isinstance(page.additional, list):
                #         page.additional = [page.additional]
                #     for button in page.additional:
                #         logger.info(f'Page {page} AB {button} checking')
                #         if self.appear_then_click(button, interval=1):
                #             sleep(0.2)
                #             logger.info(f'Page {page} AB {button} clicked')


                # 获取当前页面的要点击的按钮
                if self.appear(page.check_button, interval=4):
                    logger.info(f'Page switch: {page} -> {page.parent}')
                    button = page.links[page.parent]
                    if self.appear_then_click(button, interval=2):
                        self.ui_button_interval_reset(button)
                        confirm_timer.reset()
                        clicked = True
                        break

            if clicked:
                continue

        # Reset connection
        for page in self.ui_pages:
            page.parent = None

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

    c = Config('oas1')
    d = Device(c)
    game = GameUi(config=c, device=d)

    game.screenshot()
    print(game.appear(game.I_CHECK_AREA_BOSS))
    print(game.appear(game.I_RECORDS_CLOSE))
