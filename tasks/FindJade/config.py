import json
from datetime import datetime, timedelta
from enum import IntEnum
from pydantic import Field, BaseModel
from tasks.Component.SwitchAccount.switch_account_config import AccountInfo
from tasks.Component.config_base import ConfigBase
from tasks.Component.config_scheduler import Scheduler
from module.config.utils import write_file
from tasks.WantedQuests.config import CooperationSelectMaskDescription, CooperationSelectMask, CooperationType
from typing import List, Any


class FindJadeConfig(BaseModel):
    find_jade_json_path: str = Field(default='./config/findjade/find_jade.json', description='json conf file path')
    # extra: str = Field(default='')


class FindJade(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    find_jade_config: FindJadeConfig = Field(default_factory=FindJadeConfig)


class InviteHistoryItem(BaseModel):
    cooperation_type: CooperationType
    time: datetime


class InviteInfo(BaseModel):
    # 被邀请人员昵称
    name: str = "defaultName"
    default_invite_type: CooperationSelectMaskDescription

    # 协作任务类型   上次邀请时间
    invite_history: list[InviteHistoryItem]

    def need_invite(self, ctype: CooperationType):
        if not ctype & CooperationSelectMask[self.default_invite_type.value]:
            return False
        # 判断是否邀请过
        lastTime = max([filtered.time for filtered in
                        filter(lambda x: x.cooperation_type == ctype, self.invite_history)],
                       default=datetime(1970, 2, 2))

        now = datetime.now()
        if now - lastTime > timedelta(hours=13):
            return True
        if (lastTime.hour >= 18 or lastTime.hour < 5) and (18 > now.hour >= 5):
            return True
        if (5 <= lastTime.hour < 18) and now.hour >= 18:
            return True
        return False

    def add_invite_history(self, ctype: CooperationType, name=None):
        if name != self.name:
            return
        self.invite_history.append(InviteHistoryItem(cooperation_type=ctype, time=datetime.now()))
        pass


class FindJadeJSON(BaseModel, extra='allow'):
    find_jade_accounts_info: list[AccountInfo]
    invite_info_list: list[InviteInfo]

    def get_invite_name(self, ctype: CooperationType):
        for info in self.invite_info_list:
            if info.need_invite(ctype):
                return info.name
        return ""

    def update_invite_history(self, ctype: CooperationType, name: str):
        # 更新邀请信息
        for info in self.invite_info_list:
            if info.name != name:
                continue
            info.add_invite_history(ctype, name)
        self.updateHandle()

    def update_account_login_history(self, account: AccountInfo):
        accountInfoList = self.find_jade_accounts_info
        for info in accountInfoList:
            if info.character != account.character or info.svr != account.svr:
                continue
            info.last_complete_time = datetime.now()
        self.updateHandle()

    def get_cooperation_type_mask(self) -> CooperationSelectMaskDescription:
        """
            根据配置中各个邀请人 的邀请类型
            综合得出该值
        """
        result = CooperationSelectMask.NoInvite
        for info in self.invite_info_list:
            result |= CooperationSelectMask[info.default_invite_type]
        name = CooperationSelectMask(result).name
        return CooperationSelectMaskDescription(name)

    def save2file(self, conf_path):
        write_file(conf_path, self.dict())

    def updateHandle(self):
        """
            需要刷新配置到磁盘时调用
        """
        pass
