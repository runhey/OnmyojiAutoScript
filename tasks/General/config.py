# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from pydantic import BaseModel, ValidationError, validator, Field
from tasks.Component.config_base import ConfigBase

from module.logger import logger