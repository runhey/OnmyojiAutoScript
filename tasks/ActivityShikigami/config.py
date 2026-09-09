# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field, model_validator

from tasks.Component.GeneralBattle.config_general_battle import GreenMarkType
from tasks.Component.config_scheduler import Scheduler
from tasks.Component.config_base import ConfigBase, TimeDelta
from tasks.Component.BaseActivity.config_activity import GeneralClimb


def check_soul_by_number(enable_switch: bool, group_team: str, label: str):
    if not enable_switch:
        return
    if not group_team or group_team == "-1,-1":
        raise ValueError(f"[{label}]Switch Soul configuration is enabled, but there is no setting")
    if ',' not in group_team:
        raise ValueError(f"[{label}]The switch soul configuration must be in English ','")
    parts = group_team.split(',')
    if len(parts) != 2:
        raise ValueError(f"[{label}]The length of the switch soul configuration must be equal to 2")
    if not all(p.strip().isdigit() for p in parts):
        raise ValueError(f"[{label}]Switching soul configurations must be numeric")


def check_soul_by_ocr(enable_switch: bool, group_team: str, label: str):
    if not enable_switch:
        return
    if not group_team:
        raise ValueError(f"[{label}]Switch Soul configuration is enabled, but there is no setting")
    if ',' not in group_team:
        raise ValueError(f"[{label}]The switch soul configuration must be in English ','")
    parts = group_team.split(',')
    if len(parts) != 2:
        raise ValueError(f"[{label}]The length of the switch soul configuration must be equal to 2")


class SwitchSoulConfig(BaseModel):
    enable_switch_pass: bool = Field(default=False, description='enable_switch_pass_help')
    pass_group_team: str = Field(default='-1,-1', description='pass_group_team_help')
    enable_switch_pass_by_name: bool = Field(default=False, description='enable_switch_pass_by_name_help')
    pass_group_team_name: str = Field(default='', description='pass_group_team_name_help')

    enable_switch_ap: bool = Field(default=False, description='enable_switch_ap_help')
    ap_group_team: str = Field(default='-1,-1', description='ap_group_team_help')
    enable_switch_ap_by_name: bool = Field(default=False, description='enable_switch_ap_by_name_help')
    ap_group_team_name: str = Field(default='', description='ap_group_team_name_help')

    enable_switch_boss: bool = Field(default=False, description='enable_switch_boss_help')
    boss_group_team: str = Field(default='-1,-1', description='boss_group_team_help')
    enable_switch_boss_by_name: bool = Field(default=False, description='enable_switch_boss_by_name_help')
    boss_group_team_name: str = Field(default='', description='boss_group_team_name_help')

    enable_switch_ap100: bool = Field(default=False, description='enable_switch_ap100_help')
    ap100_group_team: str = Field(default='-1,-1', description='ap100_group_team_help')
    enable_switch_ap100_by_name: bool = Field(default=False, description='enable_switch_ap100_by_name_help')
    ap100_group_team_name: str = Field(default='', description='ap100_group_team_name_help')

    # @model_validator(mode='after')
    def validate_switch_soul(self):
        label_set = self.get_label_set()
        for label in label_set:
            enable_num = getattr(self, f"enable_switch_{label}", False)
            team = getattr(self, f"{label}_group_team", None)
            check_soul_by_number(enable_num, team, label=label.upper())

            enable_ocr = getattr(self, f"enable_switch_{label}_by_name", False)
            team_name = getattr(self, f"{label}_group_team_name", None)
            check_soul_by_ocr(enable_ocr, team_name, label=label.upper())
        return self

    def get_label_set(self):
        return {field.replace("enable_switch_", "") for field in self.model_fields if
                     field.startswith("enable_switch_") and not field.endswith("by_name")}


class GeneralBattleConfig(BaseModel):
    enable_pass_preset: bool = Field(default=False, description='enable_pass_preset_help')
    enable_pass_green: bool = Field(default=False, description='enable_pass_green_help')
    pass_green_mark: GreenMarkType = Field(default=GreenMarkType.GREEN_LEFT1, description='pass_green_mark_help')
    enable_pass_anti_detect: bool = Field(default=False, description='enable_pass_anti_detect_help')

    enable_ap_preset: bool = Field(default=False, description='enable_ap_preset_help')
    enable_ap_green: bool = Field(default=False, description='enable_ap_green_help')
    ap_green_mark: GreenMarkType = Field(default=GreenMarkType.GREEN_LEFT1, description='ap_green_mark_help')
    enable_ap_anti_detect: bool = Field(default=False, description='enable_ap_anti_detect_help')

    enable_boss_preset: bool = Field(default=False, description='enable_boss_preset_help')
    enable_boss_green: bool = Field(default=False, description='enable_boss_green_help')
    boss_green_mark: GreenMarkType = Field(default=GreenMarkType.GREEN_LEFT1, description='boss_green_mark_help')
    enable_boss_anti_detect: bool = Field(default=False, description='enable_boss_anti_detect_help')

    enable_ap100_preset: bool = Field(default=False, description='enable_ap100_preset_help')
    enable_ap100_green: bool = Field(default=False, description='enable_ap100_green_help')
    ap100_green_mark: GreenMarkType = Field(default=GreenMarkType.GREEN_LEFT1, description='ap100_green_mark_help')
    enable_ap100_anti_detect: bool = Field(default=False, description='enable_ap100_anti_detect_help')


class ActivityShikigami(ConfigBase):
    scheduler: Scheduler = Field(default_factory=Scheduler)
    general_climb: GeneralClimb = Field(default_factory=GeneralClimb)
    switch_soul_config: SwitchSoulConfig = Field(default_factory=SwitchSoulConfig)
    general_battle: GeneralBattleConfig = Field(default_factory=GeneralBattleConfig)

    # @model_validator(mode='after')
    def validate_switch_preset(self):
        label_set = self.switch_soul_config.get_label_set()
        for label in label_set:
            enable_preset = getattr(self.general_battle, f"enable_{label}_preset", False)
            group_team = getattr(self.switch_soul_config, f"{label}_group_team", None)
            try:
                check_soul_by_number(enable_preset, group_team, label=label.upper())
            except ValueError:
                raise ValueError(f'The switch preset is enabled, but the switch soul is configured incorrectly')
        return self
