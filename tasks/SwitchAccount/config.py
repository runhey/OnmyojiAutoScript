from typing import Any, Dict

from pydantic import Field, model_validator, model_serializer, ValidationError

from deploy.logger import logger
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase
from tasks.Component.SwitchAccount.switch_account_config import AccountInfo


class SwitchAccountConfig(ConfigBase):
    sup_account_count: int = Field(default=1, ge=1, description='sup_account_count_help')
    task_after_switch: str = Field(default='', description='切换账号后执行的任务名称(大驼峰),如WantedQuests,留空则仅切换账号')


class SwitchAccount(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    switch_account_config: SwitchAccountConfig = Field(default_factory=SwitchAccountConfig)
    sup_account_list: list[AccountInfo] = None

    def update_account_login_history(self, account: AccountInfo):
        if not self.sup_account_list:
            return
        for info in self.sup_account_list:
            if info.character != account.character or info.svr != account.svr:
                continue
            from datetime import datetime
            info.last_complete_time = datetime.now()
            break

    @model_validator(mode='before')
    @classmethod
    def validator_all(cls, v: dict) -> Any:
        sup_account_count = v.get('switch_account_config', {}).get('sup_account_count', 1)

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
