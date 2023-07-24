# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from datetime import timedelta
from pydantic import BaseModel, Field

from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase
from tasks.Utils.config_enum import DemonClass


class ThousandThings(BaseModel):
    # 千物宝箱
    enable: bool = Field(title='Enable', default=False)
    mystery_amulet: bool = Field(title='Mystery Amulet', default=False)
    black_daruma_fragment: bool = Field(title='Black Daruma Fragment', default=False)
    ap: bool = Field(title='AP', default=False, description='ap_help')

class Consignment(BaseModel):
    # 寄售屋
    enable: bool = Field(title='Enable', default=False)
    buy_sale_ticket: bool = Field(title='Buy Sale Ticket', default=False, description='buy_sale_ticket_help')

class Scales(BaseModel):
    # 密卷屋 蛇皮
    enable: bool = Field(title='Enable', default=False)
    orochi_scales: int = Field(title='Orochi Scales', default=40, description='orochi_scales_help')
    demon_souls: int = Field(title='Demon Souls', default=50, description='demon_souls_help')
    demon_class: DemonClass = Field(title='DemonClass', default=DemonClass.TSUCHIGUMO, description='demon_class_help')
    demon_position: int = Field(title='Demon Position', default=1, description='demon_position_help')
    picture_book_scrap: int = Field(title='Picture Book Scrap', default=30, description='picture_book_scrap_help')
    picture_book_rule: str = Field(title='Picture Book Rule', default='auto', description='picture_book_rule_help')


class SpecialRoom(BaseModel):
    # 杂货铺 特殊购买
    enable: bool = Field(title='Enable', default=False)
    totem_pass: bool = Field(title='Totem Pass', default=False)
    medium_bondling_discs: int = Field(title='Medium Bondling Discs', default=0, description='medium_bondling_discs_special')
    low_bondling_discs: int = Field(title='Low Bondling Discs', default=0, description='low_bondling_discs_special')

class HonorRoom(BaseModel):
    # 杂货铺 荣誉购买
    enable: bool = Field(title='Enable', default=False)
    mystery_amulet: bool = Field(title='Mystery Amulet', default=False, description='mystery_amulet_help_honor')
    black_daruma_scrap: bool = Field(title='Black Daruma Scrap', default=False, description='black_daruma_scrap_help_honor')

class FriendshipPoints(BaseModel):
    # 杂货铺 友情点
    enable: bool = Field(title='Enable', default=False)
    white_daruma: bool = Field(title='White Daruma', default=False)
    red_daruma: int = Field(title='Red Daruma', default=0)
    broken_amulet: int = Field(title='Broken Amulet', default=0)

class MedalRoom(BaseModel):
    # 杂货铺 勋章购买
    enable: bool = Field(title='Enable', default=False)
    black_daruma: bool = Field(title='Black Daruma', default=False)
    mystery_amulet: bool = Field(title='Mystery Amulet', default=False)
    ap_100: bool = Field(title='AP 100', default=False)
    random_soul: bool = Field(title='Random Soul', default=False)
    white_daruma: bool = Field(title='White Daruma', default=False)
    challenge_pass: int = Field(title='Challenge Pass', default=0, description='challenge_pass_help')
    red_daruma: int = Field(title='Red Daruma', default=0)
    broken_amulet: int = Field(title='Broken Amulet', default=0)

class Charisma(BaseModel):
    # 杂货铺 魅力购买
    enable: bool = Field(title='Enable', default=False)
    black_daruma_scrap: bool = Field(title='Black Daruma Scrap', default=False)
    mystery_amulet: bool = Field(title='Mystery Amulet', default=False)

class Shrine(BaseModel):
    # 神社 神龛
    enable: bool = Field(title='Enable', default=False)
    black_daruma: bool = Field(title='Black Daruma', default=False)
    white_daruma_five: bool = Field(title='White Daruma Five', default=False)
    white_daruma_four: bool = Field(title='White Daruma Four', default=False)

class Bondlings(BaseModel):
    # 契灵商店 契忆
    enable: bool = Field(title='Enable', default=False)
    random_soul: int = Field(title='Random Soul', default=0, description='random_soul_help')
    bondling_stone: int = Field(title='Bondling Stone', default=0, description='bondling_stone_help')
    high_bondling_discs: int = Field(title='High Bondling Discs', default=0, description='high_bondling_discs_help')
    medium_bondling_discs: int = Field(title='Medium Bondling Discs', default=0, description='medium_bondling_discs_help')

class GuildStore(BaseModel):
    # 寮商店
    enable: bool = Field(title='Enable', default=False)
    mystery_amulet: bool = Field(title='Mystery Amulet', default=False)
    black_daruma_scrap: bool = Field(title='Black Daruma Scrap', default=False)
    skin_ticket: int = Field(title='Skin Ticket', default=0, description='skin_ticket_help')




class RichMan(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    special_room: SpecialRoom = Field(default_factory=SpecialRoom)
    honor_room: HonorRoom = Field(default_factory=HonorRoom)
    friendship_points: FriendshipPoints = Field(default_factory=FriendshipPoints)
    medal_room: MedalRoom = Field(default_factory=MedalRoom)
    charisma: Charisma = Field(default_factory=Charisma)

    thousand_things: ThousandThings = Field(default_factory=ThousandThings)
    consignment: Consignment = Field(default_factory=Consignment)
    scales: Scales = Field(default_factory=Scales)
    bondlings: Bondlings = Field(default_factory=Bondlings)
    shrine: Shrine = Field(default_factory=Shrine)
    guild_store: GuildStore = Field(default_factory=GuildStore)
