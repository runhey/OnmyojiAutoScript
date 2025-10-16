# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import json

from pathlib import Path

from module.config.config_model import ConfigModel
from module.config.config import Config
from module.logger import logger





if __name__ == "__main__":
    # ConfigModel对象并更新保存
    config = ConfigModel()
    config_path = Path("./config/template.json")
    config.write_json("template", config.model_dump())
