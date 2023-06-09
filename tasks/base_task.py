# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import datetime

from module.config.config import Config
from module.device.device import Device

class BaseTask:
    config: Config = None
    device: Device = None

    folder: str
    name: str
    stage: str

    limit_time: datetime  # 限制运行的时间，是软时间，不是硬时间


    def __init__(self, config: Config, device: Device) -> None:
        self.config = config
        self.device = device

