# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
from datetime import timedelta, time, datetime
from typing import Any

from pydantic import BaseModel, ValidationError
from pydantic import (BeforeValidator,
                      PlainSerializer,
                      WithJsonSchema,
                      field_serializer,
                      SerializationInfo)
from typing_extensions import Annotated


def format_timedelta(tdelta: timedelta):
    days = tdelta.days
    hours, rem = divmod(tdelta.seconds, 3600)
    minutes, seconds = divmod(rem, 60)
    return f"{days:02d} {hours:02d}:{minutes:02d}:{seconds:02d}"

def datadelta_validator(v: Any) -> timedelta:
    if isinstance(v, str):
        try:
            pattern = r'(\d{1,2})\s+(\d{1,2}):(\d{1,2}):(\d{1,2})'
            match = re.match(pattern, v)
            if match:
                days = int(match.group(1))
                hours = int(match.group(2))
                minutes = int(match.group(3))
                seconds = int(match.group(4))
                return TimeDelta(days=days, hours=hours, minutes=minutes, seconds=seconds)
            return TimeDelta(days=1, hours=0, minutes=0, seconds=0)
        except ValueError:
            raise ValueError('Invalid interval value. Expected format: seconds')
    return v

def datetime_validator(v: Any) -> datetime:
    if isinstance(v, str):
        return datetime.fromisoformat(v)
    return v

def time_validator(v: Any) -> time:
    if isinstance(v, str):
        return time.fromisoformat(v)
    return v


MultiLine = Annotated[str,
                      WithJsonSchema({'type': 'multi_line'}),]


TimeDelta = Annotated[timedelta,
                      BeforeValidator(datadelta_validator),
                      PlainSerializer(format_timedelta, return_type=str),
                      WithJsonSchema({'type': 'time_delta'}),]

DateTime = Annotated[datetime,
                     BeforeValidator(datetime_validator),
                     PlainSerializer(lambda v: v.strftime('%Y-%m-%d %H:%M:%S'), return_type=str),
                     WithJsonSchema({'type': 'date_time'}),]

Time = Annotated[time,
                 BeforeValidator(time_validator),
                 PlainSerializer(lambda v: v.strftime('%H:%M:%S'), return_type=str),
                 WithJsonSchema({'type': 'time'}),]

# ---------------------------------------------------------------------------------------------------------------------

@classmethod
def serializer_exclude(cls, value: any, info: SerializationInfo):
    if info.context and info.context.get('hide', False):
        return 0xABCDEF
    return value


def dynamic_hide(*fields: str,):
    return field_serializer(*fields)(serializer_exclude)


class ConfigBase(BaseModel):
    def __init__(self, *args, **kwargs):
        try:
            super().__init__(*args, **kwargs)
        except ValidationError as exc:
            """
            During the initialization of the ConfigBase class, 
            if a ValidationError occurs, the default value of the field is used to initialize the field, 
            and the exception is re-raised after the initialization is complete.
            """
            exc_info = exc.errors()[0]
            val_error_type = exc_info.get('type', None)
            val_error_key = exc_info.get('loc', None)[0]
            if val_error_type not in ['greater_than_equal',
                                      'greater_than',
                                      'less_than',
                                      'less_than_equal',]:
                raise exc
            from module.logger import logger

            try:
                default_value = self.model_fields[val_error_key].default
                kwargs[val_error_key] = self.model_fields[val_error_key].default
                logger.warning(f'Field {val_error_key} is out of range, using default value {default_value}')
                logger.warning(repr(exc))
                logger.warning(str(kwargs))
                super().__init__(*args, **kwargs)
            except Exception as e:
                raise


