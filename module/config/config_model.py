# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import json

from pathlib import Path
from pydantic import BaseModel, ValidationError, validator, Field, root_validator

from module.config.utils import *
from module.logger import logger

# 导入配置的Python文件
from module.tasks.Script.config import Script
from module.tasks.Restart.config import Restart






class ConfigModel(BaseModel):
    config_name: str = "oas"
    script: Script = Field(default_factory=Script)
    restart: Restart = Field(default_factory=Restart)

    # @validator('script')
    # def script_validator(cls, v):
    #     if v is None:
    #         return Script()

    def __init__(self, config_name: str) -> None:
        """

        :param config_name:
        """
        data = self.read_json(config_name)
        data["config_name"] = config_name
        super().__init__(**data)

    def __setattr__(self, key, value):
        """
        只要修改属性就会触发这个函数 自动保存
        :param key:
        :param value:
        :return:
        """
        super().__setattr__(key, value)
        logger.info("auto save config")
        self.save()



    @staticmethod
    def read_json(config_name: str) -> dict:
        """
        读文件 没有额外操作
        :param config_name:  不带后缀
        :return:
        """
        filepath = Path.cwd() / "config" / f"{config_name}.json"
        return read_file(filepath)

    @staticmethod
    def write_json(config_name: str, data) -> None:
        """

        :param config_name: 不带后缀
        :param data:  字典而不是字符串
        :return:
        """
        filepath = Path.cwd() / "config" / f"{config_name}.json"
        write_file(filepath, data)

    def gui_args(self, task: str) -> str:
        """
        返回提供给gui显示的参数
        :param task: 输入的是任务的名称英文 如'Script' 或者是'script'都是可以的
        :return: 返回的是pydantic给我们结构化的输出的信息, 如果不能获取就返回空的str
        """
        task = convert_to_underscore(task)
        task_gui = getattr(self, task, None)
        if task_gui is None:
            logger.error(f'{task} is no inexistence')
            return ''
        return task_gui.schema_json()

    def gui_task(self, task: str) -> str:
        """
        返回提供给gui显示的参数
        :param task:
        :return:
        """
        task_name = convert_to_underscore(task)
        task = getattr(self, task_name, None)
        if task is None:
            logger.error(f'{task_name} is no inexistence')
            return ''
        return task.json()

    def save(self) -> None:
        """

        :return:
        """
        self.write_json(self.config_name, self.dict())


    # @root_validator
    # def on_on_property_change(cls, values):
    #     """
    #     当属性改变时保存
    #     :param values:
    #     :return:
    #     """
    #     logger.info(f'property change auto save')
    #     cls.save()


if __name__ == "__main__":
    try:
        c = ConfigModel("oas1")
    except ValidationError as e:
        print(e)
        c = ConfigModel()
    # c.write_json('oas1', c.dict())
    # c.write_json('oas1', c.schema())
    c.script.device.serial = "5555"
