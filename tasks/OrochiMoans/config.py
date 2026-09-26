from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase

class OrochiMoans(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)

