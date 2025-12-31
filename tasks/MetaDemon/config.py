# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from pydantic import BaseModel, ValidationError, validator, Field, field_validator
from pydantic import Field, BaseModel, model_validator, model_serializer, ValidationError
from enum import Enum
from typing import Any, Dict

from module.logger import logger
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.SwitchSoul.switch_soul_config import SwitchSoulConfig
from tasks.Component.config_base import ConfigBase, dynamic_hide


class DefaultStrategy(ConfigBase):
    # 1 是高于阈值选这个阵容 2是低于这个阈值选这个阵容
    md_preset_group_team_default_1: str = Field(default='1,1', description='md_preset_group_team_default_1_help')
    md_preset_group_team_default_2: str = Field(default='1,1', description='md_preset_group_team_default_2_help')

    # fff = dynamic_hide('md_match_names')


class Strategy(ConfigBase):
    # 匹配的式神中文名字
    md_match_names: str = Field(default='御撰津')
    # 选哪一个预设组
    md_preset_group_team_1: str = Field(default='1,1')
    md_preset_group_team_2: str = Field(default='1,1')

    def is_valid(self):
        return self.md_match_names != "" and self.md_match_names is not None

    @classmethod
    def parse_names(cls, names: str) -> list[str]:
        names = names.replace('，', ',').replace(' ', '')
        try:
            return names.split(',')
        except Exception as e:
            logger.error(f'parse_names error: {e}')
            raise e

    @classmethod
    def parse_group_team(cls, team: str) -> list[int]:
        team = team.replace('，', ',').replace(' ', '')
        team = ''.join([c for c in team if c.isdigit() or c == ','])
        try:
            result = [int(i) for i in team.split(',')]
            if len(result) != 2:
                raise Exception('group team length is not 2')
            if result[0] < 0 and result[1] < 0:
                raise Exception('group team is not valid')
            # group 不能小于1 和大于 7
            if result[0] < 1 or result[0] > 7:
                raise Exception('group is not valid')
            # team 不能小于1 和大于 5
            if result[1] < 1 or result[1] > 5:
                raise Exception('team is not valid')
            return result
        except Exception as e:
            logger.error(f'group team string: {team}')
            logger.error(f'parse_team error: {e}')
            raise e

    @classmethod
    def parse_all(cls, data: list['Strategy']) -> dict[str, list[int]]:
        result = {}
        for item in data:
            value = item.parse_group_team(item.md_preset_group_team_1) \
                    + item.parse_group_team(item.md_preset_group_team_2)
            for name in cls.parse_names(item.md_match_names):
                result[name] = value
        return result


class MetaDemonConfig(ConfigBase):
    meta_crafting_card: bool = Field(default=True, description='craft_essence_help')
    auto_tea: bool = Field(default=False, description='auto_tea_help')
    # extreme_notify: bool = Field(default=False, description='extreme_notify_help')
    md_strategy_count: int = Field(default=0, ge=0, description='md_strategy_count_help')
    md_use_strategy: bool = Field(default=False, description='md_use_strategy_help')

    @field_validator('auto_tea', mode='after')
    @classmethod
    def to_false(cls, v):
        return False

    @field_validator('md_strategy_count', mode='after')
    @classmethod
    def validator_strategy_count(cls, v):
        if v < 0:
            return 0
        return v


class MetaDemon(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    switch_soul: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
    meta_demon_config: MetaDemonConfig = Field(default_factory=MetaDemonConfig)
    md_default_strategy: DefaultStrategy = Field(default_factory=DefaultStrategy)
    md_strategies: list[Strategy] = None

    @model_validator(mode='before')
    @classmethod
    def validator_all(cls, v: dict) -> Any:
        strategy_count = v.get('meta_demon_config', {}).get('md_strategy_count', 1)

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
                current_list = data[list_name]
                current_length = len(current_list)
                if current_length < list_size:
                    num_to_add = list_size - current_length
                    new_elements = [item_type() for _ in range(num_to_add)]
                    data[list_name].extend(new_elements)
                elif current_length > list_size:
                    data[list_name] = data[list_name][:list_size]

        validator_list('md_strategies', v, Strategy, strategy_count)

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


if __name__ == '__main__':
    ff = MetaDemon()
    ff.model_dump()
