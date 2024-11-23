# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from pydantic import Field

from tasks.Component.config_base import ConfigBase, TimeDelta, DateTime, Time

class Scheduler(ConfigBase):
    enable: bool = Field(default=False, description='enable_help')
    next_run: DateTime = Field(default=DateTime.fromisoformat("2023-01-01 00:00:00"), description='next_run_help')
    priority: int = Field(default=5, description='priority_help')

    success_interval: TimeDelta = Field(default=TimeDelta(days=1), description='success_interval_help')
    failure_interval: TimeDelta = Field(default=TimeDelta(days=1), description='failure_interval_help')
    server_update: Time = Field(default=Time(hour=9, minute=0, second=0), description='server_update_help')
    float_time: Time = Field(default=Time(hour=0, minute=0, second=0), description='float_time_help')


if __name__ == "__main__":
    s = Scheduler(success_interval='00 00:00:10', float_time='00:01:00', next_run='2023-01-01 00:00:10')
    print(s.model_dump())
    schema = s.model_json_schema(mode='validation')
    import json
    print(str(schema))


