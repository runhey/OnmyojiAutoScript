# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum
from pydantic import BaseModel, Field

from tasks.GlobalGame.config_emergency import Emergency
from tasks.Component.config_base import ConfigBase
from tasks.Component.Costume.config import CostumeConfig

class Transport(str, Enum):
    TCP = 'TCP'
    SSL_TLS = 'SSL/TLS'


class TeamFlow(BaseModel):
    enable: bool = Field(default=False, description='enable_help')
    broker: str = Field(default='', description='broker_help')
    port: int = Field(default=8883, description='port_help')
    transport: Transport = Field(default=Transport.TCP, description='transport_help')
    ca: str = Field(default='', description='ca_help')
    username: str = Field(default='', description='username_help')
    password: str = Field(default='', description='password_help')


class GlobalGame(BaseModel):
    emergency: Emergency = Field(default_factory=Emergency)
    costume_config: CostumeConfig = Field(default_factory=CostumeConfig)
    team_flow: TeamFlow = Field(default_factory=TeamFlow)

