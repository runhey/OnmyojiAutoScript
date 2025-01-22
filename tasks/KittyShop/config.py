# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase

class KittyShopConfig(BaseModel):
    kitty_attempts: int = Field(default=1, description='kitty_attempts_help')
    kitty_quit_when_finished: bool = Field(default=False, description='kitty_quit_when_finished_help')


class KittyShop(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    kitty_shop_config: KittyShopConfig = Field(default_factory=KittyShopConfig)