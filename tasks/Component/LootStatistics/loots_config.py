from enum import Enum
from datetime import datetime, time
from pydantic import BaseModel, ValidationError, validator, Field

from tasks.Component.config_base import ConfigBase

# 可以从这儿找
# https://onmyoji.fandom.com/wiki/Items
class Item(str, Enum):
    Realm_Raid_Pass = 'RealmRaidPass'  # 突破券
