from pydantic import Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase
from pydantic import BaseModel, Field

class GuildActivityMonitorCombatTime(BaseModel):
    # 设置检测时间
    detection_interval: int = Field(default=5, description="OCR检测间隔（秒）\n通过截图OCR识别通知区域文字，自动拉起对应任务")
    monitor_duration: int = Field(default=15, description="监控持续时间（分）")
    recheck_interval: int = Field(default=5, description="拉起对应活动后，间隔多久再次开启检测（分）\n若监控时间内未检测到活动，则按调度器设置下次运行时间")

class GuildActivity(BaseModel):
    # 道馆
    Dokan: bool = Field(default=True)
    # 狭间
    AbyssShadows: bool = Field(default=True)
    # 宴会
    GuildBanquet: bool = Field(default=True)
    # 退治
    DemonRetreat: bool = Field(default=True)


class GuildActivityMonitor(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    guild_activity_monitor_combat_time: GuildActivityMonitorCombatTime = Field(default_factory=GuildActivityMonitorCombatTime)
    guild_activity: GuildActivity = Field(default_factory=GuildActivity)
