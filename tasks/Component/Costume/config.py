# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field
from enum import Enum

# 庭院皮肤
class MainType(str, Enum):
    COSTUME_MAIN = 'costume_main'  # 初语谧景
    COSTUME_MAIN_1 = 'costume_main_1'  # 织梦莲庭
    COSTUME_MAIN_2 = 'costume_main_2'  # 琼夜淬光
    COSTUME_MAIN_3 = 'costume_main_3'  # 烬夜韶阁
    COSTUME_MAIN_4 = 'costume_main_4'  # 笔墨山河
    COSTUME_MAIN_5 = 'costume_main_5'  # 枫色秋庭
    COSTUME_MAIN_6 = 'costume_main_6'  # 暖池青苑
    COSTUME_MAIN_7 = 'costume_main_7'  # 盛夏幽庭
    COSTUME_MAIN_8 = 'costume_main_8'  # 远海航船
    COSTUME_MAIN_9 = 'costume_main_9'  # 结缘神社
    COSTUME_MAIN_10 = 'costume_main_10'  # 望月幽庭
    COSTUME_MAIN_11 = 'costume_main_11'  # 鏖刀禁府

# 结界皮肤
class RealmType(str, Enum):
    COSTUME_REALM_DEFAULT = 'costume_realm_default'  # 妖扇结界
    COSTUME_REALM_1 = 'costume_realm_1'  # 鬼灵咒符
    COSTUME_REALM_2 = 'costume_realm_2'  # 狐梦之乡
    COSTUME_REALM_3 = 'costume_realm_3'  # 编心织忆
    COSTUME_REALM_4 = 'costume_realm_4'  # 花海繁生

# 主题，就是庭院最右下角的展开按钮
class ThemeType(str, Enum):
    COSTUME_THEME_DEFAULT = 'costume_theme_default'  # 伊始之卷

# 幕间，就是式神录这里
class ShikigamiType(str, Enum):
    COSTUME_SHIKIGAMI_DEFAULT = 'costume_shikigami_default'  # 静栖走廊

# 签到主题
class SignType(str, Enum):
    COSTUME_SIGN_DEFAULT = 'costume_sign_default'  # 默认

# 战斗主题
class BattleType(str, Enum):
    COSTUME_BATTLE_DEFAULT = 'costume_battle_default'  # 简约主题 / 不支持怀旧
    COSTUME_BATTLE_1 = 'costume_battle_1'  # 雅乐之邦
    COSTUME_BATTLE_2 = 'costume_battle_2'  # 蝶寻花踪
    COSTUME_BATTLE_3 = 'costume_battle_3'  # 凛霜寒雪
    COSTUME_BATTLE_4 = 'costume_battle_4'  # 春缕含青
    COSTUME_BATTLE_5 = 'costume_battle_5'  # 祥夜幽芳
    COSTUME_BATTLE_6 = 'costume_battle_6'  # 桂馥金秋
    COSTUME_BATTLE_7 = 'costume_battle_7'  # 笼梦之境
    COSTUME_BATTLE_8 = 'costume_battle_8'  # 藏金台阁
    COSTUME_BATTLE_9 = 'costume_battle_9'  # 莲华圣域
    COSTUME_BATTLE_10 = 'costume_battle_10'  # 流焰蝶舞



class CostumeConfig(BaseModel):
    # 皮肤配置
    costume_main_type: MainType = Field(default=MainType.COSTUME_MAIN, description='costume_main_type_help')
    costume_realm_type: RealmType = Field(default=RealmType.COSTUME_REALM_DEFAULT, description='costume_realm_type_help')
    costume_theme_type: ThemeType = Field(default=ThemeType.COSTUME_THEME_DEFAULT, description='costume_theme_type_help')
    costume_shikigami_type: ShikigamiType = Field(default=ShikigamiType.COSTUME_SHIKIGAMI_DEFAULT, description='costume_shikigami_type_help')
    costume_sign_type: SignType = Field(default=SignType.COSTUME_SIGN_DEFAULT, description='costume_sign_type_help')
    costume_battle_type: BattleType = Field(default=BattleType.COSTUME_BATTLE_DEFAULT, description='costume_battle_type_help')







