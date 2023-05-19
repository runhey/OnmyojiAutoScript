# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import os
import json
import yaml

from filelock import FileLock
from datetime import datetime, timedelta, timezone

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
