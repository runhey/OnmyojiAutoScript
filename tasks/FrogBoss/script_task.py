# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime, timedelta, time as time_of_day
import requests
import re
import json

from module.exception import TaskEnd
from module.logger import logger
from module.atom.image import RuleImage
from module.base.timer import Timer

from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main
from tasks.Component.RightActivity.right_activity import RightActivity
from tasks.Component.GeneralBattle.assets import GeneralBattleAssets
from tasks.FrogBoss.assets import FrogBossAssets
from tasks.FrogBoss.config import Strategy

# 每轮竞猜时长（小时），用于推算下一轮的下注时刻
ROUND_HOURS = 2
# 场次表：首场 8:30 开（10:00 结算），其余整点开、两小时后整点结算
ROUND_STARTS = [time_of_day(8, 30)] + [time_of_day(h, 0) for h in range(10, 23, 2)]
# 下注界面 5 档投入按钮坐标（2万/5万/10万/20万/30万，1280x720）
TIER_POINTS = {1: (273, 610), 2: (430, 610), 3: (593, 610), 4: (750, 610), 5: (907, 610)}

# 网易大神内置博主池：昵称, hex uid（用户主页网址 ds.163.com/user/<uid> 里那串）
DASHEN_BUILTIN_UPS = [
    ("面灵气喵", "462382f1127b46c5add1185d88f0ea40"),
    ("余岁岁", "54399446d5084a0e8878dac8f6ff56d0"),
    ("七面相", "840742d60e4a43208605ae68ca8c3f64"),
    ("待机中的徐ok", "c3c989fae4074d04b478b8ba47ae4120"),
    ("雯雯", "aaa923436aa440df9ac1ee3f47387b99"),
    ("晨时微凉", "72584a679e2f45b6859566b5523400d5"),
    ("梅布斯尼", "3d4726d99f2642a485729695b798cb8c"),
    ("鸽海成路", "1d2dcbbd7e3d481c8d0f27ba4ff0dc71"),
    ("徐清林", "21657a558bdd4ddfb6501298350336e7"),
    ("不包邮哦亲", "0e4e0c5a1e494a1fa9a58ac55de689c1"),
    ("天真珈百璃", "30e383c884f844a18a7a76fe3c1e888f"),
    ("薛定谔家查查尔", "d9dc2a75497c4a91b2db1e909a36544d"),
    ("嘤嘤井", "e7107cd3010e418da26672669d8eeb5e"),
    ("Prince班崎", "74adeb1bfb2b4cf382edbbb430da2149"),
    ("靠脸混饭", "e87f855f36f24b34b9d8f8a4fb2d62b2"),
    ("夜神月丶L", "82de68c7672e4b6da65493fb829b57b6"),
    ("是大荣啦", "f6d6bb15d6024200a985752e2ab4c373"),
    ("炒饭菌", "06e2bba14a914012bc8064601cfa19ea"),
    ("清流不加班", "8982241de1844638b4bb455139b8dcc0"),
    ("槐夏三十", "a9724e98c1cb4a4e931ebc3f467ea73d"),
    ("落沫颜", "e9b0a16325af46628e8dfb9e7942cf1d"),
    ("Mico林木森", "b6b5bc8277e34f69aeca018db0081397"),
    ("CC南浔", "74db771d92a54c28ae3e98d19aa565a3"),
    ("冰七喜Den", "e498e524252041e29999b38e57c4df1d"),
    ("行水姑娘", "30b0c2923faa483f95572c324a5bc910"),
    ("更慕林", "e32aedbdd8da46a5b5b497a16c4b7658"),
]

# 押红/押蓝关键词，取在文中出现更靠前的一边
RED_REGEX = re.compile(r'(押红|押左|压红|压左|红方|红色|我红|我左|红优|左|红六|红七|红八|红九|红十|91开|82开|73开|64开)')
BLUE_REGEX = re.compile(r'(押蓝|押右|压蓝|压右|蓝方|蓝色|我蓝|我右|蓝优|右|蓝六|蓝七|蓝八|蓝九|蓝十|19开|28开|37开|46开)')
# 每场竞猜的两小时时段（博主只看当前时段内发布的帖子）
DASHEN_TIME_RANGES = [(8, 10), (10, 12), (12, 14), (14, 16), (16, 18), (18, 20), (20, 22), (22, 24)]


class ScriptTask(RightActivity, FrogBossAssets, GeneralBattleAssets):

    def run(self):
        if not self._enter_activity():
            logger.warning('FrogBoss entrance not found, treat as rest')
            self._schedule_from_rest()
            raise TaskEnd('FrogBoss')

        # 兜底软超时：界面识别不了时不无限空转（也绝不让 60s 卡死保护重启游戏）
        soft = Timer(150).start()
        while 1:
            self.screenshot()
            self.device.stuck_record_clear()
            # 休息中（图7）
            if self.appear(self.I_FROG_BOSS_REST):
                logger.info('Frog Boss rest')
                self._schedule_from_rest()
                break
            # 竞猜成功（图1：中间有宝箱）
            if self.appear(self.I_BET_SUCCESS):
                logger.info('You bet win')
                self._collect_result(win=True)
                continue
            # 竞猜失败（图9：中间无宝箱）
            if self.appear(self.I_BET_FAILURE):
                logger.info('You bet lose')
                self._collect_result(win=False)
                continue
            # 已竞猜（图4：单鼓）
            if self.appear(self.I_BETTED):
                logger.info('You have betted')
                self._schedule_after_bet()
                break
            # 可下注（图3：左右两个竞猜鼓）
            if self.appear(self.I_BET_LEFT) and self.appear(self.I_BET_RIGHT):
                if not self._handle_betting():
                    break
                continue
            if soft.reached():
                logger.warning('FrogBoss unknown state too long, skip this round')
                self._save_debug_screenshot()
                self._notify('对弈竞猜界面无法识别', '任务已跳过并改期重试，请查看错误截图')
                self._schedule_retry()
                break

        logger.info('FrogBoss end')
        raise TaskEnd('FrogBoss')

    # ---------- 调度 ----------

    def _schedule_from_rest(self):
        """休息态：按场次表唤醒到下一场开场后 3 分钟"""
        target = self._next_round_start()
        logger.info(f'FrogBoss rest, next round start {target}')
        self.set_next_run(task='FrogBoss', target=target)

    def _next_round_start(self) -> datetime:
        now = datetime.now()
        for t in ROUND_STARTS:
            if now.time() < t:
                return datetime.combine(now.date(), t) + timedelta(minutes=3)
        return datetime.combine(now.date() + timedelta(days=1), ROUND_STARTS[0]) + timedelta(minutes=3)

    def _schedule_after_bet(self):
        """已竞猜态（含手动下注后再次进入）：按剩余时间推算下一轮下注时刻"""
        remaining = self._ocr_remaining()
        if remaining is None:
            self._schedule_from_rest()
            return
        self._schedule_next_round(datetime.now() + timedelta(seconds=remaining))

    def _schedule_next_round(self, settlement: datetime):
        """
        本轮结算时刻 settlement → 下一轮下注时刻 = 结算 + 2h - before_end(+1min 余量)。
        （首场 8:30-10:00 之后的场次都是 2 小时一场，公式通用；估错场次时下次到点
        会按倒计时再校正，自愈。）若已越过当日最后一场（结算跨到明天）→ 明早首场后再来。
        调度器不用改，竞猜用自己的时间计算。
        """
        before_end = self._before_end_seconds()
        target = settlement + timedelta(hours=ROUND_HOURS) - timedelta(seconds=before_end) + timedelta(seconds=60)
        tomorrow = False
        if settlement.date() > datetime.now().date() or settlement.hour >= 23 or settlement.hour < 8:
            tomorrow = True
            target = datetime.combine(datetime.now().date() + timedelta(days=1), ROUND_STARTS[0]) + timedelta(minutes=3)
        logger.info(f'FrogBoss settlement {settlement}, next bet at {target}' + (' (tomorrow)' if tomorrow else ''))
        self.set_next_run(task='FrogBoss', target=target)

    def _schedule_retry(self):
        target = datetime.now() + timedelta(minutes=30)
        logger.info(f'FrogBoss retry at {target}')
        self.set_next_run(task='FrogBoss', target=target)

    def _before_end_seconds(self) -> int:
        t = self.config.model.frog_boss.frog_boss_config.before_end_frog
        return t.hour * 3600 + t.minute * 60 + t.second

    def _notify(self, title: str, content: str):
        try:
            self.config.notifier.push(title=title, content=content)
        except Exception as e:
            logger.warning(f'Notify error: {e}')

    def _save_debug_screenshot(self):
        try:
            import cv2
            import os
            dir_ = './log/error'
            os.makedirs(dir_, exist_ok=True)
            path = f'{dir_}/frogboss_{datetime.now().strftime("%Y%m%d_%H%M%S")}.png'
            cv2.imwrite(path, self.device.image)
            logger.info(f'Debug screenshot saved: {path}')
        except Exception as e:
            logger.warning(f'Save screenshot error: {e}')

    # ---------- 界面流转 ----------

    def _enter_activity(self) -> bool:
        self.ui_get_current_page()
        self.ui_goto(page_main)
        if not self.ui_click(self.I_TOGGLE_BUTTON, self.I_FROG_BOSS_ENTER, interval=2, timeout=30):
            return False
        timer = Timer(20).start()
        while 1:
            self.screenshot()
            self.device.stuck_record_clear()
            if not self.appear(self.I_FROG_BOSS_ENTER):
                return True
            if timer.reached():
                return False
            if self.appear_then_click(self.I_FROG_BOSS_ENTER, interval=3):
                continue

    def _handle_betting(self) -> bool:
        """
        双鼓可下注（图3）。没到下注窗口就改期到本轮结算前 before_end；到了就策略选边下注。
        返回 False 表示已设置 next_run，任务结束；True 回主循环继续。
        """
        remaining = self._ocr_remaining()
        if remaining is None:
            logger.warning('Cannot OCR remaining time on betting page')
            self._schedule_from_rest()
            return False
        before_end = self._before_end_seconds()
        if remaining > before_end + 90:
            target = datetime.now() + timedelta(seconds=remaining - before_end + 60)
            logger.info(f'Remaining {remaining}s > before_end, next bet at {target}')
            self.set_next_run(task='FrogBoss', target=target)
            return False

        count_left = self._ocr_count(self.O_LEFT_COUNT)
        count_right = self._ocr_count(self.O_RIGHT_COUNT)
        logger.info(f'Bet counts left={count_left} right={count_right}')
        side = self._decide_side(count_left, count_right)
        logger.info(f'Bet on {"LEFT(red)" if side is self.I_BET_LEFT else "RIGHT(blue)"}')
        if self._do_bet(side):
            settlement = datetime.now() + timedelta(seconds=remaining)
            self._schedule_next_round(settlement)
        else:
            self._notify('对弈竞猜下注未完成', '金币不足或下注弹窗无法识别，已跳过本轮，30分钟后重试')
            self._schedule_retry()
        return False

    def _collect_result(self, win: bool):
        """结果页（图1/图9）：赢了点宝箱→关结算→点下一局；输了直接点下一局"""
        self._log_side()
        if win:
            # 宝箱有两种外观：未开启的紫金箱 / 开启后带内容物，任一命中即点
            box = Timer(15).start()
            while not box.reached():
                self.screenshot()
                self.device.stuck_record_clear()
                if self.appear_then_click(self.I_BET_SUCCESS_BOX, interval=2):
                    break
                if self.appear_then_click(self.I_BET_SUCCESS_BOX2, interval=2):
                    break
            # 奖励结算页（图6“点击屏幕继续”）：优先点继续文字，退而点宝箱原位置（避开奖励图标）
            reward = Timer(15).start()
            blind = Timer(2.5).start()
            while not reward.reached():
                self.screenshot()
                self.device.stuck_record_clear()
                if self.appear(self.I_NEXT_COMPETITION) or self.appear(self.I_BET_LEFT) or self.appear(self.I_BETTED):
                    break
                if self.appear_then_click(self.I_CLICK_CONTINUE, interval=2):
                    continue
                if self.appear_then_click(self.I_REWARD, interval=2):
                    continue
                if blind.reached():
                    self.device.click(750, 410)
                    blind.reset()
        self._click_next()

    def _click_next(self):
        """点下一局直到按钮消失"""
        timer = Timer(20).start()
        while not timer.reached():
            self.screenshot()
            self.device.stuck_record_clear()
            if not self.appear(self.I_NEXT_COMPETITION):
                return
            if self.appear_then_click(self.I_NEXT_COMPETITION, interval=2):
                continue

    def _do_bet(self, side: RuleImage) -> bool:
        """
        点竞猜鼓 → 全屏下注界面点档位(2万~30万) → 点竞猜按钮 → “是否确认”弹窗点确定。
        默认从配置档位开始，金币不足（点了竞猜不出确认弹窗）自动降档重试，
        最低档也不行则报告失败。所有环节都有超时验证，绝不无限等待/重启。
        """
        logger.hr('FrogBoss do bet', level=2)
        preset = min(5, max(1, self.config.model.frog_boss.frog_boss_config.frog_gold_preset))
        if not self._open_bet_dialog(side):
            logger.warning('Bet dialog did not open')
            return False
        try:
            for tier in range(preset, 0, -1):
                x, y = TIER_POINTS[tier]
                logger.info(f'Bet tier {tier} at ({x},{y})')
                self.device.click(x, y)
                self.device.sleep(0.8)
                if self._click_go_and_confirm() and self._verify_betted():
                    logger.info(f'Bet done (tier {tier})')
                    return True
                logger.warning(f'Tier {tier} no confirm popup (gold not enough?), try lower')
            return False
        finally:
            self._close_bet_dialog()

    def _open_bet_dialog(self, side: RuleImage) -> bool:
        """点竞猜鼓直到下注界面出现；已竞猜则不打扰"""
        timer = Timer(25).start()
        while not timer.reached():
            self.screenshot()
            self.device.stuck_record_clear()
            if self.appear(self.I_BET_DIALOG):
                return True
            if self.appear(self.I_BETTED):
                logger.info('Already betted, skip opening dialog')
                return False
            if self.appear_then_click(side, interval=2):
                continue
        return False

    def _click_go_and_confirm(self) -> bool:
        """点右侧竞猜按钮，等“是否确认”弹窗出现后点确定，弹窗消失算成功"""
        timer = Timer(12).start()
        popup = False
        while not timer.reached():
            self.screenshot()
            self.device.stuck_record_clear()
            if self.appear(self.I_BET_SURE):
                popup = True
                break
            if self.appear_then_click(self.I_BET_GO, interval=2):
                continue
        if not popup:
            return False
        timer = Timer(8).start()
        while not timer.reached():
            self.screenshot()
            self.device.stuck_record_clear()
            if not self.appear(self.I_BET_SURE):
                return True
            if self.appear_then_click(self.I_BET_SURE, interval=2):
                continue
        return False

    def _verify_betted(self) -> bool:
        """下注成功的判据：已竞猜出现，或下注界面与双竞猜鼓都已消失。30 秒内等不到算失败"""
        timer = Timer(30).start()
        while not timer.reached():
            self.screenshot()
            self.device.stuck_record_clear()
            if self.appear(self.I_BETTED):
                return True
            if not self.appear(self.I_BET_DIALOG) and not (self.appear(self.I_BET_LEFT) and self.appear(self.I_BET_RIGHT)):
                return True
            self.appear_then_click(self.I_UI_CONFIRM, interval=3)
        return False

    def _close_bet_dialog(self):
        """尽力关掉残留的下注界面（点红叉），失败也没关系（软超时会兜底）"""
        timer = Timer(8).start()
        blind = Timer(2.5).start()
        while not timer.reached():
            self.screenshot()
            self.device.stuck_record_clear()
            if not self.appear(self.I_BET_DIALOG):
                return
            if self.appear_then_click(self.I_BET_CLOSE, interval=2):
                continue
            if blind.reached():
                self.device.click(1191, 158)
                blind.reset()

    # ---------- 识别 ----------

    def _ocr_remaining(self):
        """剩余结算时间 MM:SS → 秒；读不到返回 None"""
        for _ in range(3):
            self.screenshot()
            text = str(self.O_TIME_REMAIN.ocr(self.device.image))
            m = re.search(r'(\d{1,3})[:：](\d{2})', text)
            if m:
                return int(m.group(1)) * 60 + int(m.group(2))
            m = re.fullmatch(r'(\d{1,3})(\d{2})', text.strip())
            if m:
                return int(m.group(1)) * 60 + int(m.group(2))
        return None

    def _ocr_count(self, rule) -> int:
        for _ in range(2):
            self.screenshot()
            try:
                return int(str(rule.ocr(self.device.image)))
            except ValueError:
                continue
        return 0

    def _log_side(self):
        """胜/败鼓宽 roi 匹配，命中坐标判左右（纯日志，不影响流程）"""
        if self.appear(self.I_SUCCESS_LEFT):
            side = 'LEFT' if self.I_SUCCESS_LEFT.roi_front[0] < 640 else 'RIGHT'
            logger.info(f'{side} win')
        elif self.appear(self.I_FAILURE_RIGHT):
            side = 'LEFT' if self.I_FAILURE_RIGHT.roi_front[0] < 640 else 'RIGHT'
            logger.info(f'{side} lose')
        else:
            logger.info('Side unknown')

    # ---------- 策略 ----------

    def _decide_side(self, count_left: int, count_right: int) -> RuleImage:
        strategy = self.config.model.frog_boss.frog_boss_config.strategy_frog
        match strategy:
            case Strategy.Majority | Strategy.Bilibili:
                return self.I_BET_LEFT if count_left > count_right else self.I_BET_RIGHT
            case Strategy.Minority:
                return self.I_BET_LEFT if count_left < count_right else self.I_BET_RIGHT
            case Strategy.AlwaysRed:
                return self.I_BET_LEFT
            case Strategy.AlwaysBlue:
                return self.I_BET_RIGHT
            case Strategy.Dashen:
                return self._dashen(count_left, count_right)
            case Strategy.DashenSpecific:
                return self._dashen(count_left, count_right, only_uid=self.config.model.frog_boss.frog_boss_config.dashen_uid.strip())
            case _:
                raise ValueError(f'Unknown bet mode: {strategy}')

    def _dashen_pool(self) -> list:
        """自定义博主池优先（每行“昵称,uid”，只有 uid 也行），留空用内置池"""
        pool = []
        custom = self.config.model.frog_boss.frog_boss_config.dashen_pool or ''
        for line in custom.replace('，', ',').splitlines():
            line = line.strip()
            if not line:
                continue
            if ',' in line:
                name, uid = line.split(',', 1)
                name, uid = name.strip(), uid.strip()
            else:
                uid = name = line
            if uid:
                pool.append((name or uid[:8], uid))
        if not pool:
            pool = DASHEN_BUILTIN_UPS
        logger.info(f'Dashen pool size: {len(pool)}')
        return pool

    def _dashen(self, count_left: int, count_right: int, only_uid: str = '') -> RuleImage:
        """拉取博主最新动态投票。only_uid 非空时只看指定博主，该博主没表态则回退跟随多数"""
        up_left, up_right = self._dashen_votes(only_uid or None)
        if only_uid and up_left == 0 and up_right == 0:
            logger.warning('Specified UP has no valid post this round, fallback to majority')
            up_left, up_right = self._dashen_votes(None)
        if up_left > up_right:
            logger.info(f'Final decision: bet LEFT({up_left}:{up_right})')
            return self.I_BET_LEFT
        if up_right > up_left:
            logger.info(f'Final decision: bet RIGHT({up_right}:{up_left})')
            return self.I_BET_RIGHT
        logger.info('UP votes tied, bet screen minority for bonus')
        return self.I_BET_LEFT if count_left < count_right else self.I_BET_RIGHT

    def _dashen_votes(self, only_uid: str = None):
        """返回 (投左人数, 投右人数)。纯网络循环定期保活，防止 60 秒卡死误判"""
        up_left = up_right = 0
        pool = self._dashen_pool()
        if only_uid:
            pool = [(n, u) for n, u in pool if u == only_uid] or [(only_uid[:8], only_uid)]
        budget = Timer(240).start()
        for name, uid in pool:
            if budget.reached():
                logger.warning('Dashen fetch budget exhausted, decide with current votes')
                break
            self.device.stuck_record_clear()
            data = self._dashen_fetch(uid)
            if not data:
                continue
            create_time, body_text = data
            if not body_text or not self._dashen_time_valid(create_time):
                logger.attr('Dashen', f'{name}: skip (old post or off-session)')
                continue
            result = self._dashen_analyze(body_text)
            logger.attr('Dashen', f'{name}: {result}')
            if result == 'LEFT':
                up_left += 1
            elif result == 'RIGHT':
                up_right += 1
        return up_left, up_right

    @staticmethod
    def _dashen_fetch(uid: str):
        """取博主最新一条动态，返回 (发布时间毫秒, 正文) 或 None"""
        try:
            r = requests.get(
                f'https://inf.ds.163.com/v1/web/feed/basic/getSomeOneFeeds?feedTypes=1,2,3,4,6,7,10,11&someOneUid={uid}',
                timeout=5)
            feeds = r.json().get('result', {}).get('feeds', [])
            if not feeds:
                return None
            r2 = requests.get(f'https://inf.ds.163.com/v1/web/feed/basic/facade?feedId={feeds[0]["id"]}', timeout=5)
            d = r2.json()['result']
            text = json.loads(d['feed']['content'])['body']['text']
            return int(d['feed']['createTime']), text
        except Exception as e:
            logger.warning(f'Dashen fetch {uid[:8]} error: {e}')
            return None

    @staticmethod
    def _dashen_time_valid(create_time_ms: int) -> bool:
        """只接受与本场同属一个两小时时段的帖子"""
        now = datetime.now()
        post = datetime.fromtimestamp(create_time_ms / 1000)
        return any(s <= post.hour < e and s <= now.hour < e for s, e in DASHEN_TIME_RANGES)

    @staticmethod
    def _dashen_analyze(body_text: str) -> str:
        red_span = RED_REGEX.search(body_text)
        blue_span = BLUE_REGEX.search(body_text)
        red_pos = red_span.start() if red_span else 9999
        blue_pos = blue_span.start() if blue_span else 9999
        if red_pos < blue_pos:
            return 'LEFT'
        if red_pos > blue_pos:
            return 'RIGHT'
        return 'Unknown'


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
