# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from typing import Any
from collections.abc import Callable, Generator
from datetime import timedelta

from pydantic import BaseModel, datetime_parse
from pydantic.fields import ModelField



def format_timedelta(tdelta: timedelta):
    days = tdelta.days
    hours, rem = divmod(tdelta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days:02d} {hours:02d}:{minutes:02d}:{seconds:02d}"

class TimeDelta(timedelta):
    def __str__(self):
        return format_timedelta(self)

    def __repr__(self):
        return format_timedelta(self)

class ConfigBase(BaseModel):
    class Config:
        json_encoders = {
            TimeDelta: format_timedelta
        }



class MultiLine(str):
    # @classmethod
    # def __get_validators__(cls) -> Generator[Callable, None, None]:
    #     yield cls.validate
    #
    # @classmethod
    # def validate(cls, value: str, field: ModelField):
    #     return cls(value)

    @classmethod
    def __modify_schema__(
        cls, field_schema: dict[str, Any], field: ModelField | None
    ):
        if field:
            field_schema['type'] = 'multi_line'


