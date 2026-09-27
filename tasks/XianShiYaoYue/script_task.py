# This Python file uses the following encoding: utf-8
# @author Tokisaki
# github https://github.com/runhey
from time import sleep
from cached_property import cached_property

from module.atom.image import RuleImage
from module.base.timer import Timer
from module.exception import TaskEnd, GameStuckError
from module.logger import logger

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_shikigami_records
from tasks.XianShiYaoYue.page import page_xian_shi_yao_yue
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.XianShiYaoYue.assets import XianShiYaoYueAssets
from tasks.XianShiYaoYue.config import XianShiYaoYue


class BattleCountOut(Exception):
    """挑战次数已用尽, 任务完成"""
    pass


class ScriptTask(GameUi, SwitchSoul, GeneralBattle, XianShiYaoYueAssets):

    @cached_property
    def conf(self) -> XianShiYaoYue:
        return self.config.model.xian_shi_yao_yue

    def run(self) -> None:
        # 上次异常退出可能残留结算弹窗, 先关掉再识别页面, 否则页面识别会失败
        for _ in range(5):
            self.screenshot()
            if self.appear_then_click(self.I_XY_CONFIRM, interval=1):
                logger.info('Close leftover confirm popup')
                continue
            break
        # 任务前切换御魂
        self.ui_get_current_page()
        self.ui_goto(page_main)
        self._switch_soul()

        # 进入现世妖约活动页
        self._goto_activity_from_main()

        # 购买现世祝福
        if self.conf.xian_shi_yao_yue_config.buy_blessing:
            self._buy_blessing()

        # 循环战斗
        total = int(self.conf.xian_shi_yao_yue_config.battle_count)
        win_count = 0
        fail_streak = 0
        for i in range(total):
            logger.hr(f'XianShiYaoYue battle {i + 1}/{total}', 1)
            try:
                if self._round():
                    win_count += 1
                    fail_streak = 0
                else:
                    # 等待超时被取消恢复的失败轮: 连续多轮失败说明环境异常,
                    # 抛 GameStuckError 交回调度器重启, 别空转到次数用完
                    fail_streak += 1
                    if fail_streak >= 3:
                        raise GameStuckError('Too many failed rounds')
            except BattleCountOut:
                logger.warning('Battle count exhausted during round, task complete')
                break

        # 战斗统计: 按实际开打的场数算, 配置的 total 是上限不是已打数
        logger.hr('XianShiYaoYue statistics', 1)
        played = self.current_count
        logger.info(f'Battles played: {played}, Win: {win_count}, Lose: {played - win_count}')

        # 返回庭院: 先点右上角粉色叉关闭页面(复用 I_UI_BACK_RED), 再点左上角黄色返回
        self._exit_to_main()
        self.set_next_run(task='XianShiYaoYue', success=True)
        raise TaskEnd

    def _exit_to_main(self) -> None:
        """
        退出活动页回庭院。
        活动页/商店页的黄色返回在页面未关闭时不生效, 必须先点右上角粉色叉
        (模板复用通用的 I_UI_BACK_RED), 关闭后黄色返回才可用。
        """
        timer = Timer(60).start()
        while 1:
            self.screenshot()
            if self.appear(self.I_CHECK_MAIN):
                return
            if timer.reached():
                raise GameStuckError('Cannot exit XianShiYaoYue to main page')
            if (self.appear_then_click(self.I_UI_BACK_RED, interval=2) or
                    self.appear_then_click(self.I_UI_BACK_YELLOW, interval=2)):
                continue
            if (self.appear_then_click(self.I_UI_CONFIRM, interval=1) or
                    self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1)):
                continue

    def _goto_activity_from_main(self) -> None:
        """
        从庭院点击右侧活动栏的线下庆典图标进入活动页。
        图标位置随账号右侧图标数量浮动, 小猫立绘也会轮换:
        匹配不到入口图标时点击右栏底部的刷新按钮换一批。
        入口/刷新仅限在庭院时点击, 点击后等待页面过渡防止连点。
        """
        timer = Timer(60).start()
        while 1:
            self.screenshot()
            if self.appear(self.I_XY_CHECK_ACTIVITY):
                return
            if timer.reached():
                raise GameStuckError('Cannot find offline celebration entry on main page')
            # 页面过渡期间不点击(且入口/刷新只在庭院有效)
            if not self.appear(self.I_CHECK_MAIN):
                continue
            if (self.appear_then_click(self.I_XY_OFFLINE_CELEBRATION, interval=2) or
                    self.appear_then_click(self.I_XY_OFFLINE_CELEBRATION_2, interval=2)):
                # 等待页面过渡
                transition = Timer(4).start()
                while not transition.reached():
                    self.screenshot()
                    if self.appear(self.I_XY_CHECK_ACTIVITY):
                        return
                continue
            # 入口图标没匹配到, 点刷新换一批
            if self.appear_then_click(self.I_XY_REFRESH, interval=3):
                logger.info('Offline celebration icon not found, click refresh')
                transition = Timer(2).start()
                while not transition.reached():
                    self.screenshot()
                    if self.appear(self.I_XY_CHECK_ACTIVITY):
                        return
                continue
            sleep(0.5)

    def _switch_soul(self) -> None:
        """
        执行任务前切换御魂
        """
        conf = self.conf.switch_soul_config
        if not conf.enable and not conf.enable_switch_by_name:
            return
        logger.hr('Switch soul', 2)
        if conf.enable:
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(conf.switch_group_team)
        if conf.enable_switch_by_name:
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(conf.group_name, conf.team_name)
        self.ui_goto(page_main)

    def _buy_blessing(self) -> None:
        """
        商店购买现世祝福(100勾玉), 已购买则跳过
        """
        logger.hr('Buy XianShi blessing', 2)
        self.ui_click(self.I_XY_GOTO_SHOP, stop=self.I_XY_CHECK_SHOP, interval=1, timeout=30)
        for attempt in range(3):
            self.screenshot()
            # 用子串匹配而不是 ocr_appear: 后者是全串相等, OCR 结果带尾随空格等噪声时恒为 False,
            # 2026-09-26 实测导致已上架的现世祝福被判成"已购买"而跳过
            blessing_text = self.O_XY_BLESSING.ocr(self.device.image)
            if self.O_XY_BLESSING.keyword not in blessing_text:
                logger.info('Blessing not found in shop, maybe already bought')
                break
            logger.info(f'Find XianShi blessing, try buy, attempt {attempt + 1}')
            self.click(self.C_XY_BLESSING)
            if self._click_blessing_buy():
                break
            # 弹窗没弹出或按钮没等到: 关掉弹窗后重试
            logger.warning('Buy button not appear, close popup and retry')
            self._close_popup()
        # 切换回活动界面
        self._switch_to_activity()

    def _click_blessing_buy(self) -> bool:
        """
        点击卡片后弹出详情弹窗: 底部是金色"100勾玉"价格按钮, 它本身就是购买按钮
        (没有确定/取消对, I_UI_CONFIRM 系列全部不适用, 2026-09-27 实测)。
        等弹窗淡入后点购买按钮, 再等按钮消失(购买完成弹窗自动关闭)。
        :return: 是否完成购买
        """
        timer = Timer(8).start()
        while not timer.reached():
            self.screenshot()
            if self.appear_then_click(self.I_XY_BUY_BLESSING, interval=1.5):
                # 防御: 个别购买可能还有系统级二次确认; 按钮消失即弹窗关闭
                gone_timer = Timer(8).start()
                while not gone_timer.reached():
                    self.screenshot()
                    if (self.appear_then_click(self.I_UI_CONFIRM, interval=1) or
                            self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1)):
                        continue
                    if not self.appear(self.I_XY_BUY_BLESSING):
                        break
                    sleep(0.3)
                logger.info('Blessing bought')
                return True
            sleep(0.3)
        return False

    def _switch_to_activity(self) -> None:
        """
        从商店切回活动页。
        商店页的"活动"灯笼是灰暗状态, 与活动页的金色状态模板不同, 两个都要尝试;
        全部失败时走页面导航兜底。
        """
        timer = Timer(30).start()
        while 1:
            self.screenshot()
            if self.appear(self.I_XY_CHECK_ACTIVITY):
                return
            if timer.reached():
                logger.warning('Switch back to activity page timeout, try recover from main')
                self.ui_goto(page_main)
                self._goto_activity_from_main()
                return
            if (self.appear_then_click(self.I_XY_GOTO_ACTIVITY, interval=1.5) or
                    self.appear_then_click(self.I_XY_GOTO_ACTIVITY_2, interval=1.5) or
                    self.appear_then_click(self.I_UI_BACK_YELLOW, interval=2.5)):
                continue

    def _hook_special_reward(self) -> bool:
        """
        战斗结算可能弹出重复奖励转换弹窗(内容不定, 统一检测确定按钮),
        出现则点击确定并关闭; GeneralBattle.battle_wait 的结算循环会调用本钩子
        """
        return self.appear_then_click(self.I_XY_CONFIRM, interval=1)

    def _close_popup(self) -> None:
        """
        关闭可能残留的弹窗
        """
        for _ in range(3):
            self.screenshot()
            if (self.appear_then_click(self.I_XY_CONFIRM, interval=1) or
                    self.appear_then_click(self.I_UI_CANCEL_SAMLL, interval=1) or
                    self.appear_then_click(self.I_UI_CONFIRM, interval=1) or
                    self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1)):
                continue
            break

    def _ensure_activity_page(self) -> None:
        """
        确保回到活动主界面
        """
        timer = Timer(15).start()
        while 1:
            self.screenshot()
            if self.appear(self.I_XY_CHECK_ACTIVITY):
                return
            if timer.reached():
                logger.warning('Not back at activity page, try recover from main')
                self.ui_goto(page_main)
                self._goto_activity_from_main()
                return
            if (self.appear_then_click(self.I_XY_CONFIRM, interval=1) or
                    self.appear_then_click(self.I_UI_CONFIRM, interval=1) or
                    self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1) or
                    self.appear_then_click(self.I_UI_BACK_YELLOW, interval=2)):
                continue

    def _battle_count_remain(self) -> int | None:
        """
        返回剩余挑战次数, 识别失败返回 None(视为还有)
        注意: 界面标签"挑战次数 x/40"中 x 是剩余次数,
        ocr_digit_counter 会把 x/y 解析为 已用/上限, 所以剩余取 current 而不是 remain
        """
        self.screenshot()
        current, remain, limit = self.O_XY_BATTLE_COUNT.ocr_digit_counter(self.device.image)
        if limit <= 0:
            return None
        logger.info(f'XianShiYaoYue battle count: {current}/{limit}')
        return current

    def _check_battle_count(self) -> bool:
        """
        检查活动挑战次数是否还有剩余(38/40), 识别失败视为还有
        """
        remain = self._battle_count_remain()
        return remain is None or remain > 0

    def _raise_if_count_out(self) -> None:
        """
        寻找队伍/组队挑战点击无响应时调用: 若挑战次数已用尽则判定任务完成
        """
        remain = self._battle_count_remain()
        if remain == 0:
            raise BattleCountOut

    def _round(self) -> bool:
        """
        一轮: (自动匹配 或 直接组队挑战) -> 等待进入战斗 -> 通用战斗
        :return: 是否胜利
        """
        self._ensure_activity_page()
        # 次数标签只在活动页可见, 必须在 _ensure_activity_page 之后再 OCR
        # (run() 循环里此时是上一场的结算画面, OCR 必然为空)
        if not self._check_battle_count():
            logger.warning('No battle count left, stop early')
            raise BattleCountOut
        if self.conf.xian_shi_yao_yue_config.direct_challenge:
            # 开启虚拟定位后直接点击组队挑战:
            # 点击后弹出"队伍公开权限"弹窗(弹窗居中, 不遮挡右下角的组队挑战按钮,
            # 两者可能同时可见), 需勾选"所有人"再点创建;
            # 弹窗与按钮都消失后进入协战队伍等待界面
            logger.info('Direct team challenge')
            click_timer = Timer(20).start()
            blank_timer = None
            while 1:
                self.screenshot()
                team_challenge = self.appear(self.I_XY_TEAM_CHALLENGE)
                create_popup = self.appear(self.I_XY_CREATE)
                if not team_challenge and not create_popup:
                    # 注意: 点击后弹窗有淡入过渡期, 过渡帧里两个目标都可能短暂失配,
                    # 连续3秒都检测不到才判定进入等待界面, 否则继续处理
                    if blank_timer is None:
                        blank_timer = Timer(3).start()
                    if blank_timer.reached():
                        break
                    continue
                blank_timer = None
                if click_timer.reached():
                    # 点击无响应: 可能挑战次数已用完
                    self._raise_if_count_out()
                    raise GameStuckError('Click team challenge timeout')
                if create_popup:
                    # 勾选"所有人"(已选中时重复点击无副作用), 再点创建
                    self.click(self.C_XY_RADIO_ALL, interval=1)
                    if self.appear_then_click(self.I_XY_CREATE, interval=1.5):
                        continue
                    continue
                if self.click(self.C_XY_TEAM_CHALLENGE, interval=2):
                    continue
        else:
            # 点击寻找队伍, 跳转到组队界面(点击无响应时每1.5s重试)
            if not self.ui_click(self.I_XY_FIND_TEAM, stop=self.I_XY_AUTO_MATCH, interval=1.5, timeout=20):
                # 一直无响应: 可能挑战次数已用完
                self._raise_if_count_out()
                raise GameStuckError('Click find team timeout')
            # 点击自动匹配, 点击后界面会跳转等待匹配
            match_timer = Timer(15).start()
            while 1:
                self.screenshot()
                if not self.appear(self.I_XY_AUTO_MATCH):
                    break
                if match_timer.reached():
                    # 点击无响应: 可能挑战次数已用完
                    self._raise_if_count_out()
                    raise GameStuckError('Click auto match timeout')
                if self.click(self.I_XY_AUTO_MATCH, interval=2):
                    continue
        # 等待匹配 -> 协战队伍 -> (挑战) -> 战斗
        return self._match_and_battle()

    def _match_and_battle(self) -> bool:
        wait_timer = Timer(180).start()
        rematch = 0
        last_queue = None
        queue_change_timer = Timer(600).start()
        queue_ocr_timer = Timer(3).start()
        while 1:
            self.screenshot()
            # 匹配/排队阶段可能长时间没有任何点击, 每轮重置设备卡死检测,
            # 超时由本循环的 wait_timer 自行管理, 避免排队过久误触发任务重启
            self.device.stuck_record_clear()
            # 已经进入战斗准备或战斗中(活动主界面右下角也有类似的鼓按钮, 需排除)
            if (not self.appear(self.I_XY_CHECK_ACTIVITY) and
                    (self.is_in_prepare(False) or self.is_in_real_battle(False))):
                logger.info('Team matched, enter battle')
                break
            # 协战队伍出现挑战按钮(不消耗体力的版本), 点击进入战斗
            if self.appear_then_click(self.I_XY_CHALLENGE, interval=2):
                continue
            # 可能出现的确认弹窗
            if (self.appear_then_click(self.I_UI_CONFIRM, interval=1) or
                    self.appear_then_click(self.I_UI_CONFIRM_SAMLL, interval=1)):
                continue
            # 防御: 直接组队挑战的权限弹窗可能因过渡帧竞态残留, 在此兜底关闭
            if self.appear(self.I_XY_CREATE):
                self.click(self.C_XY_RADIO_ALL, interval=1)
                if self.appear_then_click(self.I_XY_CREATE, interval=1.5):
                    continue
                continue
            # 匹配失败回到组队界面, 重新点击自动匹配
            if self.appear(self.I_XY_AUTO_MATCH):
                rematch += 1
                if rematch > 3:
                    raise GameStuckError('Auto match failed too many times')
                logger.warning('Match reset, click auto match again')
                self.click(self.I_XY_AUTO_MATCH, interval=2)
                continue
            # 排队横幅: 横幅右上角的X出现即说明排队中(X平时是取消按钮, 不可点击;
            # 只在下方整体超时需要撤离时才点它取消排队)
            if self.appear(self.I_XY_QUEUE_CLOSE):
                if queue_ocr_timer.reached():
                    queue_ocr_timer.reset()
                    # 用原文而不是 ocr_digit: Digit 模式把读空强修成 0、全 0 串强修成 1,
                    # 且数字位数不定导致固定 roi 频繁读空刷屏; 文本有变化即视为排队有进展
                    text = self.O_XY_QUEUE.ocr_single_line(self.device.image)
                    digits = ''.join(ch for ch in text if ch.isdigit())
                    current = digits if digits else text
                    if current and current != last_queue:
                        last_queue = current
                        queue_change_timer.reset()
                        logger.info(f'Queuing: {text}')
                    if last_queue is not None and queue_change_timer.reached():
                        logger.warning(f'Queue unchanged for 10 min: {last_queue}')
                        queue_change_timer.reset()
                # 排队中, 重置整体等待计时, 不触发重启
                wait_timer = Timer(180).start()
                continue
            if wait_timer.reached():
                # 不直接重启: 先查次数(耗尽=任务完成), 再尝试取消排队并恢复到活动页,
                # 把本轮作为失败轮交回外层循环
                self._raise_if_count_out()
                logger.warning('Waiting match timeout, cancel queue and back to activity')
                if self.appear_then_click(self.I_XY_QUEUE_CLOSE, interval=1):
                    sleep(1)
                self._ensure_activity_page()
                return False
            sleep(0.5)
        # 通用战斗: 准备 -> 战斗 -> 结算
        return self.run_general_battle(config=self.conf.general_battle)


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)
    t.run()
