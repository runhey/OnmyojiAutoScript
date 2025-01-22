# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import os
import json
import yaml

from filelock import FileLock
from datetime import datetime, timedelta, timezone, time

from module.config.atomicwrites import atomic_write

DEFAULT_TIME = datetime(2023, 1, 1, 0, 0)

def filepath_config(filename, mod_name='script') -> str:
    """
    返回配置文件的路径
    """
    if mod_name == 'script':
        return os.path.join('./config', f'{filename}.json')
    else:
        return os.path.join('./config', f'{filename}.{mod_name}.json')

def filepath_args(filename='args', mod_name='alas'):
    return f'./module/config/argument/{filename}.json'


def filepath_argument(filename):
    return f'./module/config/argument/{filename}.yaml'


def read_file(file: str):
    """
    Read a file, support both .yaml and .json format.
    Return empty dict if file not exists.

    Args:
        file (str):

    Returns:
        dict, list:
    """
    folder = os.path.dirname(file)
    if not os.path.exists(folder):
        os.mkdir(folder)

    if not os.path.exists(file):
        return {}

    _, ext = os.path.splitext(file)
    lock = FileLock(f"{file}.lock")
    with lock:
        print(f'read: {file}')
        if ext == '.yaml':
            with open(file, mode='r', encoding='utf-8') as f:
                s = f.read()
                data = list(yaml.safe_load_all(s))
                if len(data) == 1:
                    data = data[0]
                if not data:
                    data = {}
                return data
        elif ext == '.json':
            with open(file, mode='r', encoding='utf-8') as f:
                s = f.read()
                return json.loads(s)
        else:
            print(f'Unsupported config file extension: {ext}')
            return {}

def write_file(file: str, data):
    """
    Write data into a file, supports both .yaml and .json format.

    Args:
        file (str):
        data (dict, list):
    """
    folder = os.path.dirname(file)
    if not os.path.exists(folder):
        os.mkdir(folder)

    _, ext = os.path.splitext(file)
    lock = FileLock(f"{file}.lock")
    with lock:
        print(f'write: {file}')
        if ext == '.yaml':
            with atomic_write(file, overwrite=True, encoding='utf-8', newline='') as f:
                if isinstance(data, list):
                    yaml.safe_dump_all(data, f, default_flow_style=False, encoding='utf-8', allow_unicode=True,
                                       sort_keys=False)
                else:
                    yaml.safe_dump(data, f, default_flow_style=False, encoding='utf-8', allow_unicode=True,
                                   sort_keys=False)
        elif ext == '.json':
            with atomic_write(file, overwrite=True, encoding='utf-8', newline='') as f:
                s = json.dumps(data, indent=2, ensure_ascii=False, sort_keys=False, default=str)
                f.write(s)
        else:
            print(f'Unsupported config file extension: {ext}')


def deep_iter(data, depth=0, current_depth=1):
    """
    Iter a dictionary safely.

    Args:
        data (dict):
        depth (int): Maximum depth to iter
        current_depth (int):

    Returns:
        list: Key path
        Any:
    """
    if isinstance(data, dict) \
            and (depth and current_depth <= depth):
        for key, value in data.items():
            for child_path, child_value in deep_iter(value, depth=depth, current_depth=current_depth + 1):
                yield [key] + child_path, child_value
    else:
        yield [], data

def server_timezone() -> timedelta:
    return timedelta(hours=8)

def server_time_offset() -> timedelta:
    """
    To convert local time to server time:
        server_time = local_time + server_time_offset()
    To convert server time to local time:
        local_time = server_time - server_time_offset()
    """
    return datetime.now(timezone.utc).astimezone().utcoffset() - server_timezone()

def get_server_next_update(daily_trigger):
    """
    Args:
        daily_trigger (list[str], str): [ "00:00", "12:00", "18:00",]

    Returns:
        datetime.datetime
    """
    if isinstance(daily_trigger, str):
        daily_trigger = daily_trigger.replace(' ', '').split(',')

    diff = server_time_offset()
    local_now = datetime.now()
    trigger = []
    for t in daily_trigger:
        h, m = [int(x) for x in t.split(':')]
        future = local_now.replace(hour=h, minute=m, second=0, microsecond=0) + diff
        s = (future - local_now).total_seconds() % 86400
        future = local_now + timedelta(seconds=s)
        trigger.append(future)
    update = sorted(trigger)[0]
    return update


def convert_to_underscore(text: str) -> str:
    """
    大驼峰形式的字符串转换为下划线形式的字符串，并在数字前插入下划线。如果字符串中已经包含下划线，则会直接返回原始字符串。
    :param text:
    :return:
    """
    if '_' in text:
        # If text already contains underscore, assume it's in the correct format
        return text
    text = text.replace(' ', '')

    result = ''
    for i, char in enumerate(text):
        if char.isupper():
            if i > 0 and (text[i-1].islower() or (i < len(text) - 1 and text[i+1].islower())):
                # Insert underscore before uppercase letter, except at the beginning
                result += '_'
            result += char.lower()
        elif char.isdigit():
            if i > 0 and (text[i-1].isalpha() or (i < len(text) - 1 and text[i+1].isalpha())):
                # Insert underscore before digit, except at the beginning
                result += '_'
            result += char
        else:
            result += char

    return result

def get_server_last_update(daily_trigger):
    """
    Args:
        daily_trigger (list[str], str): [ "00:00", "12:00", "18:00",]

    Returns:
        datetime.datetime
    """
    if isinstance(daily_trigger, str):
        daily_trigger = daily_trigger.replace(' ', '').split(',')

    diff = server_time_offset()
    local_now = datetime.now()
    trigger = []
    for t in daily_trigger:
        h, m = [int(x) for x in t.split(':')]
        future = local_now.replace(hour=h, minute=m, second=0, microsecond=0) + diff
        s = (future - local_now).total_seconds() % 86400 - 86400
        future = local_now + timedelta(seconds=s)
        trigger.append(future)
    update = sorted(trigger)[-1]
    return update


def nearest_future(future, interval=120):
    """
    Get the neatest future time.
    Return the last one if two things will finish within `interval`.

    Args:
        future (list[datetime.datetime]):
        interval (int): Seconds

    Returns:
        datetime.datetime:
    """
    future = [datetime.fromisoformat(f) if isinstance(f, str) else f for f in future]
    future = sorted(future)
    next_run = future[0]
    for finish in future:
        if finish - next_run < timedelta(seconds=interval):
            next_run = finish

    return next_run



def dict_to_kv(dictionary, allow_none=True):
    """
    Args:
        dictionary: Such as `{'path': 'Scheduler.ServerUpdate', 'value': True}`
        allow_none (bool):

    Returns:
        str: Such as `path='Scheduler.ServerUpdate', value=True`
    """
    return ', '.join([f'{k}={repr(v)}' for k, v in dictionary.items() if allow_none or v is not None])


def parse_tomorrow_server(server_update: time, delay_date: int = 1, float_seconds: int = 0) -> datetime:
    """
    获取明天的日期，给这个日期加上server_update的时间，返回datetime
    :param server_update:
    :param float_seconds: 浮动的秒数，可为正或负值
    :return:
    """
    if isinstance(server_update, str):
        server_update = time.fromisoformat(server_update)
    now = datetime.now()
    tomorrow = now + timedelta(days=delay_date)
    next_run = datetime.combine(tomorrow, server_update)
    
    # 应用浮动时间
    if float_seconds !=0:
        next_run += timedelta(seconds=float_seconds)

        # 确保时间在第二天内，不回退到前一天，不跨越到第三天（考虑任务时间，最早 00:00，最晚 23:50）
        start_of_tomorrow = datetime.combine(tomorrow, time.min)
        end_of_tomorrow = datetime.combine(tomorrow, time(hour=23, minute=50))
    
        if next_run < start_of_tomorrow:
            next_run = start_of_tomorrow
        elif next_run > end_of_tomorrow:
            next_run = end_of_tomorrow
    
    return next_run

def deep_get(d, keys, default=None):
    """
    Get values in dictionary safely.
    https://stackoverflow.com/questions/25833613/safe-method-to-get-value-of-nested-dictionary

    Args:
        d (dict):
        keys (str, list): Such as `Scheduler.NextRun.value`
        default: Default return if key not found.

    Returns:

    """
    if isinstance(keys, str):
        keys = keys.split('.')
    assert type(keys) is list
    if d is None:
        return default
    if not keys:
        return d
    return deep_get(d.get(keys[0]), keys[1:], default)


def deep_set(d, keys, value):
    """
    Set value into dictionary safely, imitating deep_get().
    """
    if isinstance(keys, str):
        keys = keys.split('.')
    assert type(keys) is list
    if not keys:
        return value
    if not isinstance(d, dict):
        d = {}
    d[keys[0]] = deep_set(d.get(keys[0], {}), keys[1:], value)
    return d


def deep_pop(d, keys, default=None):
    """
    Pop value from dictionary safely, imitating deep_get().
    """
    if isinstance(keys, str):
        keys = keys.split('.')
    assert type(keys) is list
    if not isinstance(d, dict):
        return default
    if not keys:
        return default
    elif len(keys) == 1:
        return d.pop(keys[0], default)
    return deep_pop(d.get(keys[0]), keys[1:], default)






if __name__ == '__main__':
    print(parse_tomorrow_server("09:01:00"))
