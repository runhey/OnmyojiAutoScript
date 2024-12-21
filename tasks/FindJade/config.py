from datetime import datetime, timedelta
from typing import Any, Dict

from pydantic import Field, BaseModel, model_validator, model_serializer, ValidationError

from deploy.logger import logger
from tasks.Component.SwitchAccount.switch_account_config import AccountInfo
from tasks.Component.config_base import ConfigBase, DateTime
from tasks.Component.config_scheduler import Scheduler
from tasks.WantedQuests.config import CooperationSelectMaskDescription, CooperationSelectMask, CooperationType


class InviteHistoryItem(BaseModel):
    cooperation_type: CooperationType
    time: DateTime


class InviteInfo(BaseModel):
    # 被邀请人员昵称
    name: str = Field(default="", description='name_help')
    default_invite_type: CooperationSelectMaskDescription = Field(default=CooperationSelectMaskDescription.JadeAndFood,
                                                                  description='default_invite_type_help')

    # 协作任务类型   上次邀请时间
    invite_history_1: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"),
                                       description='invite_history_1_help')
    invite_history_2: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"),
                                       description='invite_history_2_help')
    invite_history_4: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"),
                                       description='invite_history_4_help')
    invite_history_8: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"),
                                       description='invite_history_8_help')

    def need_invite(self, ctype: CooperationType):
        if not ctype & CooperationSelectMask[self.default_invite_type.value]:
            return False
        last_time = self.__getattribute__("invite_history_" + str(ctype))

        now = datetime.now()
        if now - last_time > timedelta(hours=13):
            return True
        if (last_time.hour >= 18 or last_time.hour < 5) and (18 > now.hour >= 5):
            return True
        if (5 <= last_time.hour < 18) and now.hour >= 18:
            return True
        return False

    def update_invite_history(self, ctype: CooperationType, name=None):
        if name != self.name:
            return
        self.__setattr__("invite_history_" + str(ctype), datetime.now())

    def is_valid(self):
        return self.name != "" and self.name is not None


class FindJadeConfig(ConfigBase, extra='allow'):
    # 被邀请人数
    invite_info_count: int = Field(default=1, ge=1, description='invite_info_count_help')
    # 小号数
    sup_account_count: int = Field(default=1, ge=1, description='sup_account_count_help')


class FindJade(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    find_jade_config: FindJadeConfig = Field(default_factory=FindJadeConfig)
    # 邀请人员信息
    invite_info_list: list[InviteInfo] = None
    # 小号信息
    sup_account_list: list[AccountInfo] = None

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
            info.update_invite_history(ctype, name)

    def update_account_login_history(self, account: AccountInfo):
        accountInfoList = self.sup_account_list
        for info in accountInfoList:
            if info.character != account.character or info.svr != account.svr:
                continue
            info.last_complete_time = datetime.now()
            break

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

    @model_validator(mode='before')
    @classmethod
    def validator_all(cls, v: dict) -> Any:
        invite_info_count = v.get('find_jade_config', {}).get('invite_info_count', 1)
        sup_account_count = v.get('find_jade_config', {}).get('sup_account_count', 1)

        def validator_list(list_name, data, item_type=None, list_size=1):
            if list_name not in data:
                data[list_name] = []

            remove_keys = []
            for key, value in data.items():
                if list_name == key or list_name not in key:
                    continue
                try:
                    item = item_type(**value)
                    if item.is_valid():
                        data[list_name].append(item)
                    remove_keys.append(key)
                except ValidationError as e:
                    pass
                except TypeError as e:
                    pass

            for key in remove_keys:
                del data[key]

            if item_type is not None:
                if len(data[list_name]) < list_size:
                    for i in range(list_size - len(data[list_name])):
                        data[list_name].append(item_type())

        validator_list('invite_info_list', v, InviteInfo, invite_info_count)
        validator_list('sup_account_list', v, AccountInfo, sup_account_count)

        return v

    @model_serializer()
    def serializer_model(self, value: Any) -> Dict[str, Any]:
        properties = self.__dict__
        data = {}

        def v_dump(v):
            try:
                return v.model_dump()
            except AttributeError as e:
                logger.error(e)
                return v

        for key, value in properties.items():
            if isinstance(value, list):
                for index, v in enumerate(value):
                    data[f'{key}_{index + 1}'] = v_dump(v)
            else:
                data[key] = v_dump(value)
        return data
