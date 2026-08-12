from pydantic import BaseModel, Field, model_validator

from tasks.Component.GeneralBattle.config_general_battle import GreenMarkType
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, TimeDelta
from tasks.Component.BaseActivity.config_activity import GeneralClimb

class DailyTraining(ConfigBase):
    limit_daily_training: int = Field(default=200, description='limit_daily_training_help')
    limit_cultivation_drills: int = Field(default=30, description='limit_cultivation_drills_help')
    active_souls_clean: bool = Field(default=False, description='是否运行结束后清理御魂')  # 结束后激活 御魂清理
    random_sleep: bool = Field(default=False, description='是否启用在点击战斗前随机休息')  # 点击战斗随机休息

class SwitchSoulConfig(BaseModel):
    enable_switch_daily_training: bool = Field(default=False, description='是否切换门票爬塔御魂')
    group_team_daily_training: str = Field(default='-1,-1', description='组1-7,队伍1-4 中间用英文,分隔')
    enable_switch_by_name_daily_training: bool = Field(default=False, description='是否通过ocr切换御魂')
    group_team_name_daily_training: str = Field(default='', description='组名,队伍名 中间用英文,分隔')

    enable_switch_cultivation_drills: bool = Field(default=False, description='是否切换门票爬塔御魂')
    group_team_cultivation_drills: str = Field(default='-1,-1', description='组1-7,队伍1-4 中间用英文,分隔')
    enable_switch_by_name_cultivation_drills: bool = Field(default=False, description='是否通过ocr切换御魂')
    group_team_name_cultivation_drills: str = Field(default='', description='组名,队伍名 中间用英文,分隔')

    def get_label_set(self):
        return {field.replace("enable_switch_", "") for field in self.model_fields if
                     field.startswith("enable_switch_") and not field.endswith("by_name")}

    def validate_switch_soul(self):
        from tasks.ActivityShikigami.config import check_soul_by_number, check_soul_by_ocr
        label_set = self.get_label_set()
        for label in label_set:
            enable_num = getattr(self, f"enable_switch_{label}", False)
            team = getattr(self, f"group_team_{label}", None)
            check_soul_by_number(enable_num, team, label=label.upper())

            enable_ocr = getattr(self, f"enable_switch_by_name_{label}", False)
            team_name = getattr(self, f"group_team_name_{label}", None)
            check_soul_by_ocr(enable_ocr, team_name, label=label.upper())
        return self



class GeneralBattleConfig(BaseModel):
    enable_preset_daily_training: bool = Field(default=False, description='是否切换门票爬塔预设, 仅数字切换御魂可用')
    enable_green_daily_training: bool = Field(default=False, description='是否开启门票爬塔绿标')
    green_mark_daily_training: GreenMarkType = Field(default=GreenMarkType.GREEN_LEFT1, description='门票爬塔绿标位置')
    enable_anti_detect_daily_training: bool = Field(default=False, description='门票爬塔战斗过程是否随机点击或滑动')

    enable_preset_cultivation_drills: bool = Field(default=False, description='是否切换门票爬塔预设, 仅数字切换御魂可用')
    enable_green_cultivation_drills: bool = Field(default=False, description='是否开启门票爬塔绿标')
    green_mark_cultivation_drills: GreenMarkType = Field(default=GreenMarkType.GREEN_LEFT1, description='门票爬塔绿标位置')
    enable_anti_detect_cultivation_drills: bool = Field(default=False, description='门票爬塔战斗过程是否随机点击或滑动')

class BudokaiTournament(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    daily_training: DailyTraining = Field(default_factory=DailyTraining)
    # cultivation_drills: CultivationDrills = Field(default_factory=CultivationDrills)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
    general_battle: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)

    @classmethod
    def run_sequence(cls) -> list[str]:
        return ['daily_training', 'cultivation_drills']










