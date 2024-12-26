import math
import time

import cv2
from module.atom.click import RuleClick
from module.atom.gif import RuleGif
from module.atom.image import RuleImage
from module.atom.ocr import RuleOcr
from module.logger import logger
from tasks.Component.SwitchAccount.assets import SwitchAccountAssets
from tasks.Component.SwitchAccount.switch_account_config import AccountInfo
from tasks.base_task import BaseTask


class LoginAccount(BaseTask, SwitchAccountAssets):

    def get_svr_name(self):
        self.screenshot()
        ocrRes = self.O_SA_LOGIN_FORM_SVR_NAME.ocr(self.device.image)
        return ocrRes

    def switch_svr(self, svrName: str):
        """
            需保证账号已登录 且处于登录界面
        @param svrName:
        @type svrName:
        """
        self.O_SA_LOGIN_FORM_SVR_NAME.keyword = svrName
        if self.ocr_appear(self.O_SA_LOGIN_FORM_SVR_NAME):
            return True
        self.ui_click(self.C_SA_LOGIN_FORM_SWITCH_SVR_BTN, self.I_SA_CHECK_SELECT_SVR_1, 1.5)
        # 展开底部角色列表,显示角色所属服务器
        self.screenshot()
        if self.appear(self.I_SA_CHECK_SELECT_SVR_1) and (not self.appear(self.I_SA_CHECK_SELECT_SVR_2)):
            self.click(self.O_SA_SELECT_SVR_CHARACTER_LIST)

        self.O_SA_SELECT_SVR_SVR_LIST.keyword = svrName
        found = False
        lastSvrList: tuple = ()
        while 1:
            self.screenshot()
            # 灰度图
            self.device.image = cv2.cvtColor(self.device.image, cv2.COLOR_BGR2GRAY)
            # ret, self.device.image = cv2.threshold(self.device.image, 200, 255, cv2.THRESH_OTSU)
            ret, self.device.image = cv2.threshold(self.device.image, 100, 255, cv2.THRESH_BINARY)
            # self.device.image = cv2.adaptiveThreshold(self.device.image, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 25, 10)
            self.device.image = abs(255 - self.device.image)

            # RGB图
            self.device.image = cv2.cvtColor(self.device.image, cv2.COLOR_GRAY2RGB)

            ocrRes = self.O_SA_SELECT_SVR_SVR_LIST.detect_and_ocr(self.device.image)
            # 受限于图像识别文字准确率,此处对识别结果与实际服务器名字 进行检查 字重合度大于阈值 就认为查找成功
            thresh = 0.5
            ocrSvrList = [res.ocr_text for res in ocrRes]
            for index, ocrSvrName in enumerate(ocrSvrList):
                if len(ocrSvrName) < 3:
                    break
                tmp = set(svrName).intersection(set(ocrSvrName))
                if len(tmp) > max(len(svrName), len(ocrSvrName)) * thresh:
                    logger.info("found svr %s which is similar with %s", ocrSvrName, svrName)
                    found = True
                    # 确定点击位置
                    box = ocrRes[index].box
                    self.O_SA_SELECT_SVR_SVR_LIST.area = [self.O_SA_SELECT_SVR_SVR_LIST.roi[0] + box[0][0],
                                                          self.O_SA_SELECT_SVR_SVR_LIST.roi[1] + box[0][1],
                                                          box[1][0] - box[0][0],
                                                          box[2][1] - box[1][1]]
                    # 跳出此层for循环
                    break
            # 两次OCR结果相等表示滑动到最右侧
            if found or lastSvrList == ocrSvrList:
                break
            lastSvrList = ocrSvrList
            self.swipe(self.S_SA_SVR_SWIPE_LEFT)
            time.sleep(3.5)
        if found:
            self.click(self.O_SA_SELECT_SVR_SVR_LIST, interval=1.5)
            return True
        # 没找到 点击空白区域关闭选择服务器界面
        self.click(self.C_SA_LOGIN_FORM_CANCEL_SVR_SELECT)
        return False

    def switch_character(self, characterName: str):
        """
              需保证账号已登录 且处于登录界面
        @param characterName:
        @return:
        @rtype:
        """
        logger.info("start switch_character")
        self.ui_click(self.C_SA_LOGIN_FORM_SWITCH_SVR_BTN, self.I_SA_CHECK_SELECT_SVR_1)
        # 展开底部角色列表,显示角色所属服务器
        self.screenshot()
        while (not self.appear(self.I_SA_CHECK_SELECT_SVR_2)) and self.appear(self.I_SA_CHECK_SELECT_SVR_1):
            logger.info("open svr icon")
            self.click(self.C_SA_SELECT_SVR_CHARACTER_LIST, interval=1.5)
            self.wait_until_appear(self.I_SA_CHECK_SELECT_SVR_2, False, 1)
            # self.ui_click(self.C_SA_SELECT_SVR_CHARACTER_LIST, self.I_SA_CHECK_SELECT_SVR_2, 1.5)
            self.screenshot()

        self.O_SA_SELECT_SVR_CHARACTER_LIST.keyword = characterName
        lastCharacterNameList = []
        while 1:
            self.screenshot()
            ocrRes = self.O_SA_SELECT_SVR_CHARACTER_LIST.detect_and_ocr(self.device.image)
            # 去除角色等级数字
            characterNameList = [ocrResItem.ocr_text.lstrip('1234567890 ([<>])【】（）《》') for ocrResItem in ocrRes]
            logger.info(characterNameList)
            ocrResBoxList = [ocrResItem.box for ocrResItem in ocrRes]
            for index, item in enumerate(characterNameList):
                if item != characterName:
                    continue
                tmp = self.O_SA_SELECT_SVR_CHARACTER_LIST
                from copy import deepcopy
                tmpClick = RuleClick(
                    roi_back=deepcopy(tmp.roi),
                    roi_front=[
                        tmp.roi[0] + ocrResBoxList[index][0][0],
                        tmp.roi[1] + ocrResBoxList[index][0][1],
                        ocrResBoxList[index][1][0] - ocrResBoxList[index][0][0],
                        ocrResBoxList[index][2][1] - ocrResBoxList[index][1][1]],
                    name="tmpClick"
                )

                # 此时 tmp 内存储的时角色名位置,而点击角色名没有反应
                # 所以需要获取到对应的服务器图标位置
                tmpClick.roi_front[1] -= 30
                self.ui_click_until_disappear(tmpClick, stop=self.I_SA_CHECK_SELECT_SVR_2,
                                              interval=3)
                logger.info("character %s found,and clicked svr icon", characterName)
                return True
            if lastCharacterNameList == characterNameList:
                break
            logger.info(f'{characterName} not found,start swipe')
            lastCharacterNameList = characterNameList
            self.swipe(self.S_SA_SVR_SWIPE_LEFT)
            # 等待滑动动画完成
            time.sleep(1.5)

        self.click(self.C_SA_LOGIN_FORM_CANCEL_SVR_SELECT, 1.5)
        return False

    def jump2SelectAccount(self):
        """
            跳转到切换账号页面 该页面有红色登录按钮
        @return:
        @rtype:
        """
        while 1:
            if self.appear(self.I_SA_NETEASE_GAME_LOGO) and self.appear(self.I_SA_ACCOUNT_LOGIN_BTN):
                return
            if self.appear_then_click(self.I_SA_SWITCH_ACCOUNT_BTN, interval=1.5):
                continue
            if self.appear(self.I_CHECK_LOGIN_FORM):
                self.click(self.C_SA_LOGIN_FORM_USER_CENTER, 1.5)
                continue
        return

    def selectAccount(self, accountInfo: AccountInfo):
        logger.info("start selectAccount")
        self.O_SA_ACCOUNT_ACCOUNT_LIST.keyword = accountInfo.account
        self.O_SA_ACCOUNT_ACCOUNT_SELECTED.keyword = accountInfo.account
        # 正常情况一次就行,但防不住OCR搞幺蛾子 保险起见 多来几次吧 反正挂机不差这点
        for i in range(3):
            while 1:
                self.screenshot()
                if self.appear(self.I_SA_ACCOUNT_DROP_DOWN_CLOSED):
                    if self.ocr_appear(self.O_SA_ACCOUNT_ACCOUNT_SELECTED):
                        return True
                    self.ui_click_until_disappear(self.I_SA_ACCOUNT_DROP_DOWN_CLOSED,
                                                  interval=1.5)
                    continue

                # 账号列表已打开状态
                ocrRes = self.O_SA_ACCOUNT_ACCOUNT_LIST.detect_and_ocr(self.device.image)

                # 找到该账号
                for index, ocr_account in enumerate([ocrResItem.ocr_text for ocrResItem in ocrRes]):
                    if not accountInfo.is_account_alias(ocr_account):
                        continue
                    # if accountInfo.account in [ocrResItem.ocr_text for ocrResItem in ocrRes]:
                    #     index = [ocrResItem.ocr_text for ocrResItem in ocrRes].index(accountInfo.account)
                    ocrResBoxList = [ocrResItem.box for ocrResItem in ocrRes]
                    self.O_SA_ACCOUNT_ACCOUNT_LIST.area = [
                        self.O_SA_ACCOUNT_ACCOUNT_LIST.roi[0] + ocrResBoxList[index][0][
                            0],
                        self.O_SA_ACCOUNT_ACCOUNT_LIST.roi[1] + ocrResBoxList[index][0][
                            1],
                        ocrResBoxList[index][1][0] - ocrResBoxList[index][0][0],
                        ocrResBoxList[index][2][1] - ocrResBoxList[index][1][1]]
                    time.sleep(1)
                    self.click(self.O_SA_ACCOUNT_ACCOUNT_LIST)
                    logger.info("account [ %s ] found", accountInfo.account)
                    return True

                # 未找到该账号
                if self.appear(self.I_SA_ACCOUNT_DROP_DOWN_ADD_ACCOUNT):
                    break
                self.swipe(self.S_SA_ACCOUNT_LIST_UP, 1.5)
                time.sleep(0.5)
        logger.info("account [ %s ] not found ", accountInfo.account)
        return False

    # def loginSubmit(self, appleOrAndroid: bool):
    #     """
    #
    #     @param appleOrAndroid: 安卓平台还是苹果平台
    #     @type appleOrAndroid:   False           Apple
    #                             True            Android
    #     @return:
    #     @rtype:
    #     """
    #     self.screenshot()
    #     if not (self.appear(self.I_SA_ACCOUNT_LOGIN_BTN) and self.appear(self.I_SA_NETEASE_GAME_LOGO)):
    #         # 不在登录界面,返回失败
    #         return False
    #     self.ui_click(self.C_SA_LOGIN_FORM_LOGIN_BTN, self.I_SA_LOGIN_FORM_APPLE, 1)
    #     if appleOrAndroid:
    #         logger.info("APPLE selected")
    #         self.ui_click_until_disappear(self.I_SA_LOGIN_FORM_APPLE, 1)
    #     else:
    #         logger.info("ANDROID selected")
    #         self.ui_click_until_disappear(self.I_SA_LOGIN_FORM_ANDROID, 1)
    #     return True

    def login(self, accountInfo: AccountInfo) -> bool:
        """

        @param accountInfo:
        @type accountInfo:
        @return:    True    点击了"进入游戏"按钮
                    False   未找到相应角色
        @rtype:bool
        """
        self.screenshot()
        #
        if not (self.appear(self.I_CHECK_LOGIN_FORM) or self.appear(self.I_SA_NETEASE_GAME_LOGO)):
            logger.error("Unknown Page,%s %s Login Failed", accountInfo.character, accountInfo.svr)
            return False

        #
        isAccountLogon = False
        isCharacterSelected = False
        self.O_SA_ACCOUNT_ACCOUNT_SELECTED.keyword = accountInfo.account
        self.O_SA_LOGIN_FORM_USER_CENTER_ACCOUNT.keyword = accountInfo.account
        while 1:
            self.screenshot()
            # 处于 选择服务器界面 直接点击空白区域退出该界面 进入切换账号流程
            if self.appear(self.I_SA_CHECK_SELECT_SVR_1) or self.appear(self.I_SA_CHECK_SELECT_SVR_2):
                self.click(self.C_SA_LOGIN_FORM_CANCEL_SVR_SELECT)
                continue

            # 处于选择 苹果安卓界面
            if self.appear(self.I_SA_LOGIN_FORM_APPLE):
                btn = self.I_SA_LOGIN_FORM_ANDROID if accountInfo.apple_or_android else self.I_SA_LOGIN_FORM_APPLE
                self.ui_click_until_disappear(btn)
                isAccountLogon = True
                continue
            # 处于选择账号界面
            if self.appear(self.I_SA_NETEASE_GAME_LOGO) and not self.appear(self.I_SA_LOGIN_FORM_APPLE):
                if not accountInfo.account:
                    logger.error("param account is None,cannot switch account")
                    return False
                # 当前选择账号不是account
                if not self.ocr_appear(self.O_SA_ACCOUNT_ACCOUNT_SELECTED):
                    # 没有找到account
                    if not self.selectAccount(accountInfo):
                        self.ui_click_until_disappear(self.C_SA_LOGIN_FORM_ACCOUNT_CLOSE_BTN,
                                                      stop=self.I_SA_NETEASE_GAME_LOGO)
                        return False
                    # selectAccount 后更新图片
                    self.screenshot()
                self.ui_click(self.I_SA_ACCOUNT_LOGIN_BTN, stop=self.I_SA_LOGIN_FORM_APPLE, interval=1)
                continue
            # 在用户中心界面
            if self.appear(self.I_SA_SWITCH_ACCOUNT_BTN):
                # 如果当前已登录用户就是account
                ocrRes = self.O_SA_LOGIN_FORM_USER_CENTER_ACCOUNT.ocr_single(self.device.image)
                # NOTE 由于邮箱账号@符号极易被误识别为其他,故对账号信息做预处理 便于比对
                if (accountInfo.account is None) or accountInfo.account == "" or accountInfo.is_account_alias(ocrRes):
                    logger.info("current is the account we want:ocr result %s", ocrRes)
                    isAccountLogon = True
                    self.ui_click_until_disappear(self.C_SA_LOGIN_FORM_USER_CENTER_CLOSE_BTN, interval=1,
                                                  stop=self.I_SA_SWITCH_ACCOUNT_BTN)
                    continue
                #
                if self.ui_click(self.I_SA_SWITCH_ACCOUNT_BTN, self.I_SA_NETEASE_GAME_LOGO):
                    isAccountLogon = False
                    continue
                continue
            # 在游戏登录界面 不在用户中心 不在切换账号界面
            if not (self.appear(self.I_SA_NETEASE_GAME_LOGO) or self.appear(self.I_SA_SWITCH_ACCOUNT_BTN)):
                # 判断是否已经账号登录
                if not isAccountLogon:
                    self.click(self.C_SA_LOGIN_FORM_USER_CENTER)
                    continue

                # 已登录 查找对应角色
                if not isCharacterSelected and self.switch_character(accountInfo.character):
                    isCharacterSelected = True
                    continue
                break
            continue

        # 切换角色失败 /未找到该角色
        # 尝试使用 选择服务器方式
        if isAccountLogon and not isCharacterSelected and accountInfo.svr is not None and accountInfo.svr != "":
            logger.info("try to find character with svrName %s", accountInfo.svr)
            isCharacterSelected = self.switch_svr(accountInfo.svr)
        if isAccountLogon and isCharacterSelected:
            # 成功登录账号 找到角色
            # self.ui_click_until_disappear(self.C_SA_LOGIN_FORM_ENTER_GAME_BTN, stop=self.I_CHECK_LOGIN_FORM)
            logger.info("character %s-%s account:%s %s login Success", accountInfo.character, accountInfo.svr,
                        accountInfo.account,
                        'Android' if accountInfo.apple_or_android else 'Apple')
            return True

        logger.error("character %s-%s account:%s %s login Failed", accountInfo.character, accountInfo.svr,
                     accountInfo.account,
                     'Android' if accountInfo.apple_or_android else 'Apple')
        return False

    def ui_click_until_disappear(self, click, interval: float = 1, stop: RuleImage | RuleGif = None):
        """
        重写原ui_click_until_disappear方法,增加stop参数
        点击一个按钮直到stop消失
        如果click为RuleOcr ,直接当作RuleClick点击,不会进行ocr识别,
        @param interval:
        @param click:
        @param stop:
        @type stop:
        @return:
        """
        if (isinstance(click, RuleImage) or isinstance(click, RuleGif)) and (stop is None):
            stop = click
        while 1:
            self.screenshot()
            if not self.appear(stop):
                break
            if isinstance(click, RuleImage) or isinstance(click, RuleGif):
                self.appear_then_click(click, interval=interval)
                continue
            elif isinstance(click, RuleClick):
                self.click(click, interval)
                continue
            elif isinstance(click, RuleOcr):
                self.click(click)
                continue
