# This Python file uses the following encoding: utf-8
# @brief    Ryou Dokan Toppa (阴阳竂道馆突破功能)
# @author   jackyhwei
# @note     draft version without full test
# github    https://github.com/roarhill/oas
import time
import random
import numpy as np
from enum import Enum

from tasks.Component.GeneralBattle.config_general_battle import GeneralBattleConfig
from tasks.Component.SwitchSoul.switch_soul import SwitchSoul
from tasks.Dokan.assets import DokanAssets
from tasks.Component.GeneralBattle.general_battle import GeneralBattle
from tasks.Component.config_base import ConfigBase, Time
from tasks.GameUi.game_ui import GameUi
from tasks.GameUi.page import page_main, page_kekkai_toppa, page_shikigami_records, page_guild
from tasks.RealmRaid.assets import RealmRaidAssets

from module.logger import logger
from module.exception import TaskEnd
from module.atom.image_grid import ImageGrid
from module.base.utils import point2str
from module.base.timer import Timer
from module.exception import GamePageUnknownError
from tasks.Dokan.config import DokanConfig, Dokan


def detect_safe_area2(image, target_gray_value=255, tolerance=0):
    """
    在灰度图片中查找与目标灰度值在容差范围内的纯色区块，并返回这些区块的坐标。
    
    :param image_path: 图片路径
    :param target_gray_value: 目标灰度值，默认为255（最亮）
    :param tolerance: 灰度差异容忍度，默认为0（即完全匹配）
    :return: 包含找到的纯色区块坐标元组的列表
    """
    import cv2
    # 加载图片并转换为灰度图
    # img = Image.open(image_path).convert('L')  # 'L' 表示转换为灰度图
    # img_arr = np.array(img)  # 转换为numpy数组以便高效处理

    # 将图片转换为灰度图
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    _, img_arr = cv2.threshold(gray, 127, 255, cv2.THRESH_BINARY)

    # 初始化结果列表
    solid_regions = []

    # 遍历图片的每个像素
    for y in range(img_arr.shape[0]):  # 高度
        for x in range(img_arr.shape[1]):  # 宽度
            pixel_gray_value = img_arr[y, x]

            # 检查当前像素灰度值是否与目标灰度值在容差范围内匹配
            if abs(pixel_gray_value - target_gray_value) <= tolerance:
                # 检查周围是否也是同样的灰度值，以确定这是一个区块而非单个像素
                is_solid_region = True
                for dy in range(-1, 2):  # 检查3x3区域
                    for dx in range(-1, 2):
                        if dy == 0 and dx == 0:
                            continue  # 跳过中心点
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < img_arr.shape[0] and 0 <= nx < img_arr.shape[1]:
                            if abs(img_arr[ny, nx] - target_gray_value) > tolerance:
                                is_solid_region = False
                                break
                    if not is_solid_region:
                        break

                if is_solid_region:
                    # 记录纯色区块的左上角坐标和右下角坐标
                    start_x, start_y = x, y
                    while start_y > 0 and abs(img_arr[start_y - 1, x] - target_gray_value) <= tolerance:
                        start_y -= 1
                    while start_x > 0 and abs(img_arr[y, start_x - 1] - target_gray_value) <= tolerance:
                        start_x -= 1
                    end_x, end_y = x, y
                    while end_y < img_arr.shape[0] - 1 and abs(img_arr[end_y + 1, x] - target_gray_value) <= tolerance:
                        end_y += 1
                    while end_x < img_arr.shape[1] - 1 and abs(img_arr[y, end_x + 1] - target_gray_value) <= tolerance:
                        end_x += 1

                    solid_regions.append(((start_x, start_y), (end_x + 1, end_y + 1)))

    return solid_regions


def detect_safe_area2(image, safe_color_lower, safe_color_upper, num_areas=3, debug=False):
    ''' 
    找出当前截图里最大的纯色区域，找出来的这个区域将被用于随机点击的区域。
    :note:          注意拿到这个区域后要马上点击，不要sleep！
    :param image:   截图图像
    :return:        最大纯色区域的坐标
    '''
    import cv2
    import numpy as np

    # 将图片从BGR转换到HSV色彩空间
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)

    # 定义颜色范围
    # 注意：这里的颜色范围需要根据实际图片中的安全区域颜色进行调整
    mask = cv2.inRange(hsv, safe_color_lower, safe_color_upper)

    # 应用形态学操作来消除噪点和填补小的孔洞
    kernel = np.ones((5, 5), np.uint8)
    mask = cv2.dilate(mask, kernel, iterations=1)
    mask = cv2.erode(mask, kernel, iterations=1)

    # 查找轮廓  
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # 计算每个轮廓的面积并排序
    # areas = [(cv2.contourArea(contour), contour) for contour in contours]
    areas = []
    for contour in contours:
        area = cv2.contourArea(contour)
        print(f"area={area}")
        areas.append((area, contour))

    # areas.sort(reverse=True)
    # 按面积降序排序
    areas_sorted = sorted(areas, key=lambda x: x[0], reverse=True)

    if debug:
        # 绘制面积排名前3的区域
        for area, contour in areas_sorted[:num_areas]:
            x1, y1, w1, h1 = cv2.boundingRect(contour)
            # 使用蓝色边框，线宽为4
            cv2.rectangle(image, (x1, y1), (x1 + w1, y1 + h1), (255, 0, 0), 4)
            # 使用红色边框，线宽为3
            cv2.drawContours(image, [contour], -1, (0, 0, 255), 3)

    # 假设最大的轮廓是安全区域  
    if contours:
        safe_area = max(contours, key=cv2.contourArea)
        x, y, w, h = cv2.boundingRect(safe_area)

        if debug:
            # 绘制安全区域  
            cv2.drawContours(image, [safe_area], -1, (0, 255, 0), 3)

        return (x, y, w, h)

    return (0, 0, 0, 0)


class DokanScene(Enum):
    # 未知界面
    RYOU_DOKAN_SCENE_UNKNOWN = 0
    # 进入道馆，集结中
    RYOU_DOKAN_SCENE_GATHERING = 1
    # 进入战场，等待用户点击开始战斗
    RYOU_DOKAN_SCENE_IN_FIELD = 2
    # 通常是失败了，并退出来到集结界面，可重新开始点击右下角挑战进入战斗
    RYOU_DOKAN_SCENE_START_CHALLENGE = 3
    # 失败次数超过上限，CD中
    RYOU_DOKAN_SCENE_CD = 4
    # 战斗进行中
    RYOU_DOKAN_SCENE_FIGHTING = 5
    # 加油进行中
    RYOU_DOKAN_SCENE_CHEERING = 6
    # 道馆失败投票保留
    RYOU_DOKAN_SCENE_FAILED_VOTE_NO = 7
    # 阴阳竂
    RYOU_DOKAN_RYOU = 8
    # 战斗结算，可能是打完小朋友了，也可能是失败了。
    RYOU_DOKAN_SCENE_BATTLE_OVER = 9
    # 等待BOSS战
    RYOU_DOKAN_SCENE_BOSS_WAITING = 10
    # 道馆结束
    RYOU_DOKAN_SCENE_FINISHED = 99

    def __str__(self):
        return self.name.title()

    def print(self):
        print(DokanScene.RYOU_DOKAN_SCENE_GATHERING)  # 输出: DokanScene.Ryou_Daoguan_Scene_Gathering
        print(DokanScene.RYOU_DOKAN_SCENE_CD.value)  # 输出: 2
        print(str(DokanScene.RYOU_DOKAN_SCENE_FIGHTING))  # 输出: Ryou_Daoguan_Scene_Fighting


class ScriptTask(GeneralBattle, GameUi, SwitchSoul, DokanAssets):
    medal_grid: ImageGrid = None
    attack_priority_selected: bool = False
    team_switched: bool = False
    green_mark_done: bool = False

    def run(self):
        """ 道馆主函数

        :return:
        """
        cfg: Dokan = self.config.dokan
        current_scene: DokanScene = DokanScene.RYOU_DOKAN_SCENE_UNKNOWN
        in_dokan: bool = False

        # 攻击优先顺序
        attack_priority: int = cfg.dokan_config.dokan_attack_priority

        # 自动换御魂
        if cfg.switch_soul_config.enable:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul(cfg.switch_soul_config.switch_group_team)
        if cfg.switch_soul_config.enable_switch_by_name:
            self.ui_get_current_page()
            self.ui_goto(page_shikigami_records)
            self.run_switch_soul_by_name(cfg.switch_soul_config.group_name, cfg.switch_soul_config.team_name)

        success = True
        scene_err_count = 0

        # 在阴阳竂界面点击并进入道馆
        # 检测当前界面的场景（时间关系，暂时没有做庭院、町中等主界面的场景检测, 应考虑在GameUI.game_ui.ui_get_current_page()里实现）
        in_dokan, current_scene = self.get_current_scene(True)

        if not in_dokan:
            self.ui_get_current_page()
            self.ui_goto(page_guild)

            self.goto_dokan()

        # 开始道馆流程
        while 1:
            self.screenshot()

            # 检测当前界面的场景（时间关系，暂时没有做庭院、町中等主界面的场景检测, 应考虑在GameUI.game_ui.ui_get_current_page()里实现）
            in_dokan, current_scene = self.get_current_scene(True)

            logger.info(f"in_dokan={in_dokan}, current_scene={current_scene}")

            # 如果当前不在道馆，或者被人工操作退出道馆了，重新尝试进入道馆
            if not in_dokan:
                scene_err_count += 1
                logger.info(f"err count={scene_err_count}")
                if scene_err_count >= 3:
                    self.goto_dokan()
                # 先点击一下，然后等5秒再重新截图
                self.anti_detect(True, True, False)
                time.sleep(5)
                continue
            else:
                scene_err_count = 0

            # 场景状态：道馆集结中
            if current_scene == DokanScene.RYOU_DOKAN_SCENE_GATHERING:
                logger.debug(f"Ryou DOKAN gathering, 集结中...")
                # 如果还未选择优先攻击，选一下
                if not self.attack_priority_selected:
                    self.dokan_choose_attack_priority(attack_priority=attack_priority)
                    self.attack_priority_selected = True
            # 场景状态：等待馆主战开始
            elif current_scene == DokanScene.RYOU_DOKAN_SCENE_BOSS_WAITING:
                logger.debug(f"Ryou DOKAN boss battle waiting...")
            # 场景状态：检查右下角有没有挑战？通常是失败了，并退出来到集结界面，可重新开始点击右下角挑战进入战斗
            elif current_scene == DokanScene.RYOU_DOKAN_SCENE_START_CHALLENGE:
                self.appear_then_click(self.I_RYOU_DOKAN_START_CHALLENGE)
            # 场景状态：进入战斗，待开始
            elif current_scene == DokanScene.RYOU_DOKAN_SCENE_IN_FIELD:
                # 战斗
                success = self.dokan_battle(cfg)
                # 战斗结束后，随便点三下，确保跳过各种结算画面
                self.click(click=self.C_DOKAN_READY_FOR_BATLLE, interval=1.5)
                self.click(click=self.C_DOKAN_RANDOM_CLICK_AREA2, interval=2.2)
                self.click(click=self.C_DOKAN_RANDOM_CLICK_AREA3, interval=1.8)
                # 每次战斗结束都重置绿标
                self.green_mark_done = False
            # 场景状态：如果CD中，开始加油
            elif current_scene == DokanScene.RYOU_DOKAN_SCENE_CD:
                logger.info(f"CD中，是否加油：{cfg.dokan_config.dokan_auto_cheering_while_cd}..")
                if cfg.dokan_config.dokan_auto_cheering_while_cd:
                    self.start_cheering()
            # 场景状态：战斗中，左上角的加油图标
            elif current_scene == DokanScene.RYOU_DOKAN_SCENE_FIGHTING:
                logger.info("战斗进行中")
            # 场景状态：加油中
            elif current_scene == DokanScene.RYOU_DOKAN_SCENE_CHEERING:
                self.appear_then_click(self.I_RYOU_DOKAN_CHEERING)
            # 场景状态：道馆已经结束
            elif current_scene == DokanScene.RYOU_DOKAN_SCENE_FINISHED:
                logger.info("道馆已经结束，退出")
                break
            elif current_scene == DokanScene.RYOU_DOKAN_SCENE_FAILED_VOTE_NO:
                logger.info("道馆挑战失败：投票保留")
            else:
                logger.info(f"unknown scene, skipped")

            # 防封，随机移动，随机点击（安全点击），随机时延
            if not self.anti_detect(True, True, True):
                time.sleep(1)

        # 保持好习惯，一个任务结束了就返回到庭院，方便下一任务的开始
        self.goto_main()

        # 设置下次运行时间
        if success:
            self.set_next_run(task='Dokan', finish=True, server=True, success=True)
        else:
            self.set_next_run(task='Dokan', finish=True, server=True, success=False)
        raise TaskEnd

    def dokan_battle(self, cfg: Dokan):
        """ 道馆战斗
        道馆集结结束后会自动进入战斗，打完一个也会自动进入下一个，因此直接点击右下角的开始

        :return: 战斗成功(True) or 战斗失败(False) or 区域不可用（False）
        """
        config: GeneralBattleConfig = cfg.general_battle_config

        # 正式进攻会设定 2s - 10s 的随机延迟，避免攻击间隔及其相近被检测为脚本。
        if cfg.dokan_config.random_delay:
            self.anti_detect(False, False, True)

        # 上面可能睡了一觉，重新截图
        self.screenshot()

        # 更换队伍
        if not self.team_switched:
            logger.info(
                f"更换队伍: config.preset_enable={config.preset_enable}, config.preset_group={config.preset_group}, config.preset_team={config.preset_team}")
            self.switch_preset_team(config.preset_enable, config.preset_group, config.preset_team)
            self.team_switched = True
            # 切完队伍后有时候会卡顿，先睡一觉，防止快速跳到绿标流程，导致未能成功绿标
            time.sleep(3)

        # 等待准备按钮的出现
        logger.debug("等待准备按钮的出现")
        self.wait_until_appear(self.I_PREPARE_HIGHLIGHT)

        # 点击准备
        if self.appear_then_click(self.I_PREPARE_HIGHLIGHT, interval=1.5):
            logger.info("点击准备")

            # 绿标式神, should we check there's a green marked role?
            if not self.green_mark_done and self.is_in_battle(False):
                logger.info(
                    f"绿标式神:config.green_enable={config.green_enable}, config.green_mark={config.green_mark}")
                self.green_mark(config.green_enable, config.green_mark)
                self.green_mark_done = True

        # 等待战斗结果
        logger.info(f"等待战斗结果:config.random_click_swipt_enable={config.random_click_swipt_enable}")
        logger.info("come on baby, let's go.")

        while 1:
            # logger.info("take a nap")
            time.sleep(1)

            self.device.stuck_record_add('BATTLE_STATUS_S')
            self.device.click_record_clear()

            self.screenshot()

            # 如果出现赢 就点击
            if self.appear(GeneralBattle.I_WIN, threshold=0.8):
                logger.info("道馆的小朋友们打完了，boss is on the way")
                win = True
                break

            # 如果出现打败馆主的赢，就点击
            if self.appear(self.I_RYOU_DOKAN_WIN, threshold=0.8):
                logger.info("We've defeated the boss, and win the final game.")
                win = True
                break

            # 如果出现失败 就点击，返回False。 TODO 不知道挑战馆主失败是不是同一个画面？
            if self.appear(GeneralBattle.I_FALSE, threshold=0.8):
                logger.info("Battle failed")
                win = False
                break

            # 如果领奖励
            if self.appear(self.I_RYOU_DOKAN_BATTLE_OVER, threshold=0.6):
                logger.info("Battle over")
                win = True
                break

            # 如果领奖励出现金币
            if self.appear(GeneralBattle.I_REWARD_GOLD, threshold=0.8):
                win = True
                break

            # 如果开启战斗过程随机滑动
            if config.random_click_swipt_enable:
                logger.info("random swipt ...")
                self.random_click_swipt()

            # 打完一个小朋友，自动进入下一个小朋友
            if self.appear_then_click(self.I_RYOU_DOKAN_IN_FIELD):
                logger.info("New battle starts")

            continue

        logger.info(f"输赢：{win}")
        if win:
            return True
        else:
            return False

    def dokan_choose_attack_priority(self, attack_priority: int):
        ''' 选择优先攻击
        : return 
        '''
        logger.info("选择优先攻击")
        ret = False
        max_try = 5

        if not self.appear_then_click(self.I_RYOU_DOKAN_PRIORITY, interval=2):
            logger.error(f"can not find dokan priority option button, choose attack priority process skipped")
            return ret

        logger.info(f"start select attack priority: {attack_priority}, remain try: {max_try}")

        while 1:
            time.sleep(2)
            self.screenshot()
            if max_try <= 0:
                logger.warn("give up priority selection!")
                break

            if attack_priority == 0:
                if self.appear_then_click(self.I_RYOU_DOKAN_PRIORITY_0, interval=1.8):
                    logger.info(f"selected attack priority: {attack_priority}")
                else:
                    continue
            elif attack_priority == 1:
                if self.appear_then_click(self.I_RYOU_DOKAN_PRIORITY_1, interval=1.8):
                    logger.info(f"selected attack priority: {attack_priority}")
                else:
                    continue
            elif attack_priority == 2:
                if self.appear_then_click(self.I_RYOU_DOKAN_PRIORITY_2, interval=1.8):
                    logger.info(f"selected attack priority: {attack_priority}")
                else:
                    continue
            elif attack_priority == 3:
                if self.appear_then_click(self.I_RYOU_DOKAN_PRIORITY_3, interval=1.8):
                    logger.info(f"selected attack priority: {attack_priority}")
                else:
                    continue
            elif attack_priority == 4:
                if self.appear_then_click(self.I_RYOU_DOKAN_PRIORITY_4, interval=1.8):
                    logger.info(f"selected attack priority: {attack_priority}")
                else:
                    continue
            else:
                self.appear_then_click(self.I_RYOU_DOKAN_PRIORITY_0, interval=1.8)
                logger.error(f"invalid attack priority setting: {attack_priority}")

            self.attack_priority_selected = True
            ret = True
            break

        return ret

    def anti_detect(self, random_move: bool = True, random_click: bool = True, random_delay: bool = True):
        '''额外的防封测试

        准备找个号做做爬楼活动的每天300次试试
        '''
        res = False
        # 三个行为中，任何一个生效了都返回True, 否则返回False
        if random_move:
            self.random_click_swipt()
            res = True
        if random_click:
            # 0到2秒之间的随机浮点数
            sleep = random.uniform(0, 2)
            # 只保留2位小数
            sleep = round(sleep, 2)
            if not self.config.dokan.dokan_config.anti_detect_click_fixed_random_area:
                # 多搞几个安全点击区域
                num = random.randint(0, 5)
                if num == 0:
                    self.click(click=self.C_DOKAN_RANDOM_CLICK_AREA, interval=sleep)
                elif num == 1:
                    self.click(click=self.C_DOKAN_RANDOM_CLICK_AREA2, interval=sleep)
                elif num == 2:
                    self.click(click=self.C_DOKAN_RANDOM_CLICK_AREA3, interval=sleep)
                elif num == 3:
                    self.click(click=self.C_DOKAN_RANDOM_CLICK_AREA, interval=sleep)
                else:
                    self.click(click=self.C_DOKAN_RANDOM_CLICK_AREA2, interval=sleep)
            else:
                # 假设安全区域是绿色的  
                safe_color_lower = np.array([45, 25, 25])  # HSV颜色空间的绿色下界  
                safe_color_upper = np.array([90, 255, 255])  # HSV颜色空间的绿色上界
                pos = detect_safe_area2(self.device.image, safe_color_lower, safe_color_upper, 3, True)
                logger.info(f"random click area: {pos}, delay: {sleep}")
                self.click(pos)

            res = True
        if random_delay:
            # 0到2秒之间的随机浮点数
            sleep = random.uniform(0, 5)
            # 只保留2位小数
            sleep = round(sleep, 2)
            time.sleep(sleep)
            res = True
        return res

    def goto_main(self):
        ''' 保持好习惯，一个任务结束了就返回庭院，方便下一任务的开始或者是出错重启
         FIXME 退出道馆。注意：有的时候有退出确认框，有的时候没有。未找到规律。
               先试试用确认框的，若是实在不行，就改成等道馆时间结束后，系统自动退出
               但是如果出错了，需要重启任务时必须走GameUi.ui_goto(page_main)，
               那样有或者无确认框不确定性还是会导致ui_goto()出错
        '''
        # self.ui_current = page_dokan
        # self.ui_goto(page_main)

        max_try = 3
        while 1:
            self.screenshot()
            if self.appear_then_click(GeneralBattle.I_EXIT, interval=1.5):
                logger.info(f"Click {GeneralBattle.I_EXIT.name}")
                continue
            # 点了后EXIT后，可能无确认框
            if self.appear_then_click(self.I_RYOU_DOKAN_EXIT_ENSURE, interval=1.5):
                logger.info(f"Click {self.I_RYOU_DOKAN_EXIT_ENSURE}")
                break
            else:
                max_try -= 1
                time.sleep(1.2)

            if max_try <= 0:
                break

        # 退出道馆地图
        while 1:
            self.screenshot()
            # 确认后会跳到竂地图，再点击左上角的蓝色的返回，但是不知道这个返回有没有确认
            if self.appear_then_click(GameUi.I_BACK_BL, interval=2.5):
                logger.info(f"Click {GameUi.I_BACK_BL.name}")
                break

    def goto_dokan(self):
        ''' 进入道馆
        TODO 道馆相关场景
        :return 
        '''
        self.ui_get_current_page()
        try_count = 0
        while try_count < 5:
            # 点击进入道馆
            logger.info("进入阴阳竂")
            self.ui_goto(page_guild)
            # 查找道馆
            activity = "道馆"
            pos = self.list_find(self.L_RYOU_ACTIVITY_LIST, activity)
            if pos:
                logger.info(f"Enter Dokan map: pos = {pos}")
                self.device.click(x=pos[0], y=pos[1])

                # 进了后的画面，我没有截图，盲猜应该是在画面正中间的
                time.sleep(2)
                image = self.screenshot()

                # O_DOKAN_MAP = RuleOcr(roi=(270,130,740,460), area=(270,130,740,460), mode="Full", method="Default", keyword="万", name="dokan_map")
                # image = cv2.imread("g:/yys/oas/tests/2.png")
                pos = self.O_DOKAN_MAP.ocr_full(image)
                if pos == (0, 0, 0, 0):
                    logger.info("failed to find {self.O_DOKAN_MAP.keyword}")
                else:
                    # 取中间
                    x = pos[0] + pos[2] / 2
                    # 往上偏移20
                    y = pos[1] - 20

                    logger.info("ocr detect result pos={pos}, try click pos, x={x}, y={y}")

                    self.device.click(x=x, y=y)
                    break
            try_count += 1
            time.sleep(1)

        print(f"try_count: {try_count}")

    def start_cheering(self):
        logger.info("start cheering")

    def get_current_scene(self, reuse_screenshot: bool = True):
        ''' 检测当前场景
        '''
        if not reuse_screenshot:
            self.screenshot()
        logger.info(f"get_current_scene={reuse_screenshot}")
        # 场景检测：阴阳竂
        if self.appear(self.I_SCENE_RYOU, threshold=0.8):
            return False, DokanScene.RYOU_DOKAN_RYOU

        # 状态：判断是否集结中
        # if self.ocr_appear(self.O_DOKAN_GATHERING):
        if self.appear(self.I_RYOU_DOKAN_GATHERING, threshold=0.95):
            return True, DokanScene.RYOU_DOKAN_SCENE_GATHERING
        # 状态：是否在等待馆主战
        # if self.ocr_appear(self.O_DOKAN_BOSS_WAITING):
        if self.appear(self.I_DOKAN_BOSS_WAITING):
            return True, DokanScene.RYOU_DOKAN_SCENE_BOSS_WAITING

        # 状态：检查右下角有没有挑战？通常是失败了，并退出来到集结界面，可重新开始点击右下角挑战进入战斗
        elif self.appear(self.I_RYOU_DOKAN_START_CHALLENGE, 0.95):
            return True, DokanScene.RYOU_DOKAN_SCENE_START_CHALLENGE

        # 状态：进入战斗，待开始
        elif self.appear(self.I_RYOU_DOKAN_IN_FIELD, threshold=0.85):
            return True, DokanScene.RYOU_DOKAN_SCENE_IN_FIELD
        # 状态：战斗结算，可能是打完小朋友了，也可能是失败了。
        if self.appear(self.I_RYOU_DOKAN_BATTLE_OVER, threshold=0.85):
            return True, DokanScene.RYOU_DOKAN_SCENE_BATTLE_OVER

        # 状态：达到失败次数，CD中
        if self.appear(self.I_RYOU_DOKAN_CD, threshold=0.8):
            return True, DokanScene.RYOU_DOKAN_SCENE_CD
        # 状态：加油中，左下角有鼓
        if self.appear_then_click(self.I_RYOU_DOKAN_CHEERING, threshold=0.8) or self.appear(
                self.I_RYOU_DOKAN_CHEERING_GRAY, threshold=0.8):
            return True, DokanScene.RYOU_DOKAN_SCENE_CHEERING
        # # 状态：战斗中，左上角的加油图标
        # if self.appear(self.I_RYOU_DOKAN_FIGHTING, threshold=0.8):
        #     return True, DokanScene.RYOU_DOKAN_SCENE_FIGHTING
        # if self.appear(self.I_RYOU_DOKAN_FAILED_VOTE_NO):
        #     return True, DokanScene.RYOU_DOKAN_SCENE_FAILED_VOTE_NO

        # 状态：道馆已经结束
        # if self.ocr_appear(self.O_DOKAN_SUCCEEDED):
        if self.appear(self.I_RYOU_DOKAN_FINISHED, threshold=0.8):
            return True, DokanScene.RYOU_DOKAN_SCENE_FINISHED

        return False, DokanScene.RYOU_DOKAN_SCENE_UNKNOWN


def test_ocr_locate_dokan_target():
    import cv2
    from module.atom.ocr import RuleOcr

    logger.info("========================================>>test 2")
    O_DOKAN_MAP = RuleOcr(roi=(270, 130, 740, 460), area=(270, 130, 740, 460), mode="Full", method="Default",
                          keyword="万", name="dokan_map")

    image = cv2.imread("g:/yys/oas/tests/1.png")
    pos = O_DOKAN_MAP.ocr_full(image)
    print(f"image1: {pos}")

    image = cv2.imread("g:/yys/oas/tests/2.png")
    pos = O_DOKAN_MAP.ocr_full(image)
    print(f"image2: {pos}")

    image = cv2.imread("g:/yys/oas/tests/3.png")
    pos = O_DOKAN_MAP.ocr_full(image)
    print(f"image3: {pos}")

    image = cv2.imread("g:/yys/oas/tests/4.png")
    pos = O_DOKAN_MAP.ocr_full(image)
    print(f"image4: {pos}")
    if pos == (0, 0, 0, 0):
        logger.info("failed to find {self.O_DOKAN_MAP.keyword}")
    else:
        # 取中间
        x = pos[0] + pos[2] / 2
        # 往上偏移20
        y = pos[1] - 20

        logger.info(f"ocr detect result pos={pos}, try click pos, x={x}, y={y}")


def test_anti_detect_random_click():
    import cv2

    # image_list = ['g:/yys/oas/tests/1.png', 'g:/yys/oas/tests/2.png', 'g:/yys/oas/tests/3.png', 'g:/yys/oas/tests/4.png', 'g:/yys/oas/tests/5.png']
    image_list = ['g:/yys/oas/tests/a.png', 'g:/yys/oas/tests/b.png', 'g:/yys/oas/tests/c.png']

    for item in image_list:
        print(f"item: {item}")
        image = cv2.imread(item)

        # 注意：这里的颜色范围需要根据实际图片进行调整  
        # http://kb.rg4.net/docs/omassistant/omassistant-1fnirpstkhdnh
        # 0<=h<20， 红色
        # 30<=h<45，黄色
        # 45<=h<90，绿色
        # 90<=h<125，青色
        # 125<=h<150，蓝色
        # 150<=h<175，紫色
        # 175<=h<200，粉红色
        # 200<=h<220，砖红色
        # 220<=h<255，品红色

        # 示例使用：假设安全区域是绿色的  
        safe_color_lower = np.array([45, 25, 25])  # HSV颜色空间的绿色下界  
        safe_color_upper = np.array([90, 255, 255])  # HSV颜色空间的绿色上界

        # 读取图片  
        image = cv2.imread('c.png')
        if image is None:
            print("Error: Image not found.")
        else:
            # 调用函数  
            pos = detect_safe_area2(image, safe_color_lower, safe_color_upper, 3, True)
            print(f"pos={pos}")

            # 显示结果  
            cv2.imshow('Safe Area', image)
            cv2.waitKey(0)
            cv2.destroyAllWindows()


def test_goto_main():
    from module.config.config import Config
    from module.device.device import Device
    from tasks.GameUi.page import page_dokan

    config = Config('oas1')
    device = Device(config)
    t = ScriptTask(config, device)
    # t.run()
    t.ui_current = page_dokan
    t.ui_goto(page_main)


if __name__ == "__main__":
    # from module.config.config import Config
    # from module.device.device import Device

    # config = Config('oas1')
    # device = Device(config)
    # t = ScriptTask(config, device)
    # t.run()

    # test_ocr_locate_dokan_target()
    # test_anti_detect_random_click()
    test_goto_main()
