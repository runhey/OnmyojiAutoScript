# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
#
import re
from pathlib import Path

from module.logger import logger

# 震惊到我姥姥家 除了第一个函数all_script_files是我自己写的
# 后面的都是github copilot写的
class Add:

    @classmethod
    def all_script_files(cls) -> list:
        """
        获取所有的脚本文件 除了tmplate
        :return: ['oas1', 'oas2']
        """
        # 获取某个路径的所有json文件名
        config_path = Path.cwd() / 'config'
        json_files = config_path.glob('*.json')
        result = []
        for json in json_files:
            if json.stem == 'template':
                continue
            result.append(json.stem)
        return result

    @classmethod
    def all_json_file(cls) -> list:
        """
        获取所有的json文件
        :return: ['oas1', 'oas2']
        """
        # 获取某个路径的所有json文件名
        config_path = Path.cwd() / 'config'
        json_files = config_path.glob('*.json')
        result = []
        for json in json_files:
            result.append(json.stem)
        return result

    @classmethod
    def copy(cls, file: str, template: str = 'template') -> None:
        """
        复制一个配置文件
        :param file:  不带json后缀
        :param template:
        :return:
        """
        config_path = Path.cwd() / 'config'
        template_path = config_path / f'{template}.json'
        file_path = config_path / f'{file}.json'
        if file_path.exists():
            logger.error(f'{file_path} is exists')
            return
        with open(template_path, 'r') as f:
            template_content = f.read()
        with open(file_path, 'w') as f:
            f.write(template_content)
        logger.info(f'copy {template_path} to {file_path}')

    @classmethod
    def generate_script_name(cls) -> str:
        """
        生成一个新的配置的名字
        :return:
        """
        all_script_files = cls.all_script_files()
        if not all_script_files:
            return 'oas1'
        all_script_files.sort()
        last_script = all_script_files[-1]
        last_script_number = re.findall(r'\d+', last_script)[0]
        new_script_number = int(last_script_number) + 1
        return f'oas{new_script_number}'

if __name__ == "__main__":
    a = Add()
    print(a.all_script_files())
    print(a.all_json_file())
    print(a.generate_script_name())


