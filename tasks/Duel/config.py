# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from typing import Any, Dict
from pydantic import (Field,
                      model_validator,
                      ValidationError,
                      model_serializer,
                      WithJsonSchema,
                      SerializerFunctionWrapHandler,
                      GetJsonSchemaHandler)

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, Time
from tasks.Component.GeneralBattle.config_general_battle import GreenMarkType

class DuelConfig(ConfigBase):
    # 一键切换斗技御魂
    switch_all_soul: bool = Field(default=False, description='switch_all_soul_help')
    # 限制时间
    limit_time: Time = Field(default=Time(minute=30), description='limit_time_help')
    # 目标分数
    target_score: int = Field(default=2000, description='target_score_help')
    # 刷满荣誉就退出
    honor_full_exit: bool = Field(default=False, description='honor_full_exit_help')
    # 是否开启绿标
    green_enable: bool = Field(default=False, description='green_enable_help')
    # 选哪一个绿标
    green_mark: GreenMarkType = Field(default=GreenMarkType.GREEN_LEFT1, description='green_mark_help')


class Duel(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    duel_config: DuelConfig = Field(default_factory=DuelConfig)
    # test_list: list[DuelConfig]
    #
    # @model_validator(mode='before')
    # @classmethod
    # def check_list(cls, data: dict) -> Any:
    #     if 'test_list' not in data:
    #         data['test_list'] = []
    #     for key, value in data.items():
    #         if isinstance(value, list):
    #             continue
    #         if 'test_list' not in key:
    #             continue
    #         try:
    #             DuelConfig(**value)
    #             data['test_list'].append(value)
    #         except ValidationError as e:
    #             pass
    #     # 补全list
    #     while len(data['test_list']) < data['scheduler']['priority']:
    #         data['test_list'].append(DuelConfig())
    #     return data
    #
    # @model_serializer()
    # def serializer_model(self, value: Any) -> Dict[str, Any]:
    #     properties = self.__dict__
    #     data = {}
    #     for key,value in properties.items():
    #         if isinstance(value, list):
    #             for index, v in enumerate(value):
    #                 data[f'{key}_{index+1}'] = v.model_dump()
    #         else:
    #             data[key] = value.model_dump()
    #     return data



