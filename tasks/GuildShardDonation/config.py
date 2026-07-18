# This Python file uses the following encoding: utf-8
from pydantic import Field

from tasks.Component.config_base import ConfigBase
from tasks.Component.config_scheduler import Scheduler


class DonationConfig(ConfigBase):
    target_player: str = Field(default="", description="target_player_help")
    target_shard: str = Field(default="", description="target_shard_help")
    test_mode: bool = Field(default=True, description="test_mode_help")


class GuildShardDonation(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    donation_config: DonationConfig = Field(default_factory=DonationConfig)
