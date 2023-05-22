# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

from cached_property import cached_property

from module.device.device import Device

class Script:
    def __init__(self, config_name: str ='oas') -> None:
        self.config_name = config_name
        print('this is script')

    @cached_property
    def device(self) -> Device:
        pass



