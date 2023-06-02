# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, ValidationError, validator, Field

from module.tasks.Script.config_device import Device
from module.tasks.Script.config_error import Error
from module.tasks.Script.config_optimization import Optimization
from module.logger import logger

class Script(BaseModel):
    device: Device = Field(default_factory=Device)
    error: Error = Field(default_factory=Error)
    optimization: Optimization = Field(default_factory=Optimization)