# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import BaseModel, Field

from tasks.Component.GeneralBattle.config_general_battle import GreenMarkType, GeneralBattleConfig
from tasks.Component.config_base import dynamic_hide


class BattleConfig(GeneralBattleConfig):
    hide_fields = dynamic_hide('lock_team_enable', 'preset_enable', 'preset_group', 'preset_team')
