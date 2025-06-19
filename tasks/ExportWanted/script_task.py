# This Python file uses the following encoding: utf-8
# @brief    Export wanted tasks (导出勾玉悬赏、狗粮悬赏、猫粮悬赏为json)
# @author   jackyhwei
# @note     draft version without full test
# github    https://github.com/roarhill/oas


import importlib
from datetime import datetime, timedelta

from module.exception import TaskEnd, RequestHumanTakeover
from module.logger import logger
from tasks.Component.SwitchAccount.switch_account import SwitchAccount
from tasks.ExportWanted import WantedQuestsEx
from tasks.ExportWanted.assets import ExportWantedAssets
from tasks.ExportWanted.config import AccountInfo, ExportWanted
from tasks.GameUi.game_ui import GameUi

from tasks.WantedQuests.assets import WantedQuestsAssets

import csv
import json

class ScriptTask(GameUi, ExportWantedAssets):
    fade_conf: ExportWanted= None
    data = []

    def run(self):
        self.fade_conf = self.config.export_wanted

        logger.error(f"self.fade_conf={self.fade_conf}")

        for accountInfo in self.fade_conf.sup_account_list:
            logger.info(f"start {accountInfo.character}-{accountInfo.svr}, accountInfo={accountInfo}")
            if not self.is_need_login(accountInfo):
                logger.warning("%s Skipped last Login Time:%s", accountInfo.character, accountInfo.last_complete_time)
                continue
            suc = SwitchAccount(self.config, self.device, accountInfo).switchAccount()
            if not suc:
                logger.warning("switch to %s-%s Failed", accountInfo.character, accountInfo.svr)
                continue
            # #
            # wq = self.CreatObjectFromModule("WantedQuests", config=self.config, device=self.device)
            # wq.fade_conf = self.fade_conf
            # logger.info(f"fade_conf={wq.fade_conf}")

            try:
                open_seal_count = 0
                while True:
                    self.screenshot()
                    if self.appear(WantedQuestsAssets.I_TRACE_DISABLE):
                        break
                    if self.appear(WantedQuestsAssets.I_TRACE_ENABLE):
                        break
                    if self.appear_then_click(WantedQuestsAssets.I_WQ_SEAL, interval=1):
                        open_seal_count += 1
                        if open_seal_count > 5:
                            logger.error(f"try open seal failed for {open_seal_count} times, give up")
                            break
                        continue
                    if self.appear_then_click(WantedQuestsAssets.I_WQ_DONE, interval=1):
                        break
                    # if self.special_main and self.click(WantedQuestsAssets.C_SPECIAL_MAIN, interval=3):
                    #     logger.info('Click special main left to find wanted quests')
                    #     continue
                    # if self.appear(self.I_UI_BACK_RED):
                    #     if not done_timer.started():
                    #         done_timer.start()
                    # if done_timer.started() and done_timer.reached():
                    #     self.ui_click_until_disappear(self.I_UI_BACK_RED)
                    #     return False
                    
                # 开始检测悬赏任务类型
                logger.info('start detect wanted quests type')

                # 存在协作任务?
                self.screenshot()
                if self.appear(WantedQuestsAssets.I_WQ_INVITE_1):
                    logger.info('there is a cooperation task in the first slot')
                    
                else:
                    logger.info('there is no cooperation task in the first slot')

                if self.appear(WantedQuestsAssets.I_WQ_INVITE_2):
                    logger.info('there is a cooperation task in the second slot')
                else:
                    logger.info('there is no cooperation task in the second slot')

                if self.appear(WantedQuestsAssets.I_WQ_INVITE_3):
                    logger.info('there is a cooperation task in the third slot')
                else:
                    logger.info('there is no cooperation task in the third slot')


                result = self.export_cooperation_info()
                new_entry = {"svr": accountInfo.svr, "account": accountInfo.character, "cooperations": result}
                print(f"new entry:{new_entry}"  )
                self.data.append(new_entry)

                # wq.run()
            except TaskEnd as e:
                logger.warning("%s-%s TaskEnd", accountInfo.character, accountInfo.svr)
                # 更新配置文件中的时间
                self.fade_conf.update_account_login_history(accountInfo)
                self.save_config()
                continue
            except RequestHumanTakeover as e:
                raise
            except Exception as e:
                logger.error(e)
                self.next_run("ExportWanted", success=False)
        print("=============================================")
        print("start to save to json..........................")
        print("=============================================")
        now = datetime.now()
        file_name = now.strftime("%Y-%m-%d_%H-%M-%S.json")

        new_json_data = json.dumps(self.data, indent=4, ensure_ascii=False) 
        with open(file_name, 'w') as file:
            file.write(new_json_data)

        self.next_run("ExportWanted", success=True)
        raise TaskEnd("ExportWanted")
        pass

    def export_cooperation_info(self):
        """
            获取协作任务详情
        @return: 协作任务类型与邀请按钮
        """
        print("export_cooperation_info start....")
        self.screenshot()

        result = ""

        for index in range(3):
            name = "I_WQ_INVITE_" + str(index + 1)
            print("btn name=" + name)
            btn = getattr(WantedQuestsAssets, name)
            print("I_WQ_INVITE_" + str(index) + "," )
            if not self.appear(btn):
                break
            if self.appear(getattr(WantedQuestsAssets, "I_WQ_COOPERATION_TYPE_JADE_" + str(index + 1))):
                print(f"found jade in index={index}")
                result += "jade, "
                continue
            if self.appear(getattr(WantedQuestsAssets, "I_WQ_COOPERATION_TYPE_DOG_FOOD_" + str(index + 1))):
                print(f"found dog food in index={index}")
                result += "dog food, "
                continue
            if self.appear(getattr(WantedQuestsAssets, "I_WQ_COOPERATION_TYPE_CAT_FOOD_" + str(index + 1))):
                print(f"found cat food in index={index}")
                result += "cat food, "
                continue
            if self.appear(getattr(WantedQuestsAssets, "I_WQ_COOPERATION_TYPE_SUSHI_" + str(index + 1))):
                print(f"found sushi in index={index}")
                result += "sushi, "
                continue
            # NOTE 因为食物协作里面也有金币奖励 ,所以判断金币协作放在最后面
            if self.appear(getattr(WantedQuestsAssets, "I_WQ_COOPERATION_TYPE_GOLD_" + str(index + 1))):
                print(f"found gold in index={index}")
                result += "gold, "
                continue

        print("export_cooperation_info end: " + result)

        return result

    def is_need_login(self, item: AccountInfo):
        """
            根据上次登陆时间 判断是否需要登录查找
        @param item:
        @type item:
        """
        lastTime = item.last_complete_time
        now = datetime.now()
        if now - lastTime > timedelta(hours=13):
            return True
        if (lastTime.hour >= 18 or lastTime.hour < 5) and (18 > now.hour >= 5):
            return True
        if (5 <= lastTime.hour < 18) and now.hour >= 18:
            return True
        return False

    def CreatObjectFromModule(self, task_name: str, **kwargs):
        module_name = 'script_task'
        from pathlib import Path
        module_path = str(Path.cwd() / 'tasks' / task_name / (module_name + '.py'))

        spec = importlib.util.spec_from_file_location(module_name, module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        WQEX = type("WQEX", (module.ScriptTask,), {
            "need_invite_vip": WantedQuestsEx.need_invite_vip,
            "get_invite_vip_name": WantedQuestsEx.get_invite_vip_name,
            "next_run": WantedQuestsEx.next_run,
            "invite_success_callback": WantedQuestsEx.invite_success_callback,
            "get_config": WantedQuestsEx.get_config
        })
        wq = WQEX(**kwargs)
        return wq

    def save_config(self):
        self.config.save()

    def next_run(self, task: str, finish: bool = False,
                 success: bool = None, server: bool = True, target: datetime = None) -> None:
        now = datetime.now()
        if success:
            if 5 <= now.hour < 18:
                self.set_next_run(task, target=now.replace(hour=18, minute=5))
            elif now.hour < 5:
                self.set_next_run(task, target=now.replace(hour=5, minute=5))
            else:
                self.set_next_run(task, target=now.replace(hour=18, minute=5) + timedelta(days=1))
        else:
            self.set_next_run(task, target=now + timedelta(minutes=10))


if __name__ == '__main__':
    from module.config.config import Config
    from module.device.device import Device
    # from mypatch import SimplePatch

    # SimplePatch.patch()

    c = Config('oas1')
    d = Device(c)
    t = ScriptTask(c, d)

    t.run()
