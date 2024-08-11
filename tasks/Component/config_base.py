# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from typing import Any
from collections.abc import Callable, Generator
from datetime import timedelta, time, datetime

from pydantic import BaseModel, datetime_parse
from pydantic.fields import ModelField



def format_timedelta(tdelta: timedelta):
    days = tdelta.days
    hours, rem = divmod(tdelta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days:02d} {hours:02d}:{minutes:02d}:{seconds:02d}"


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

class TimeDelta(timedelta):
    def __str__(self):
        return format_timedelta(self)

    def __repr__(self):
        return format_timedelta(self)

    @classmethod
    def __modify_schema__(
            cls, field_schema: dict[str, Any], field: ModelField | None
    ):
        if field:
            field_schema['type'] = 'time_delta'

class DateTime(datetime):
    @classmethod
    def __modify_schema__(
            cls, field_schema: dict[str, Any], field: ModelField | None
    ):
        if field:
            field_schema['type'] = 'date_time'


class Time(time):
    """
    尝试将字符串转换为time对象， 但是不生效
    """
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, value):
        # print(f' Time validate: {value} type: {type(value)}')
        if isinstance(value, str):
            hour, minute, second = map(int, value.split(":"))
            return cls(hour, minute, second)
        elif isinstance(value, time):
            return value
        else:
            raise ValueError("Invalid time format")

    @classmethod
    def __modify_schema__(
            cls, field_schema: dict[str, Any], field: ModelField | None
    ):
        if field:
            field_schema['type'] = 'time'

# ---------------------------------------------------------------------------------------------------------------------
class ConfigBase(BaseModel):
    # 这个是导出json时候的配置，但是新的是导出dict，所以的无效
    class Config:
        json_encoders = {
            TimeDelta: format_timedelta
        }
