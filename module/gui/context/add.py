# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
#
import re
from pathlib import Path
from PySide6.QtCore import QObject, Slot, Signal

from module.logger import logger

# 震惊到我姥姥家 除了第一个函数all_script_files是我自己写的
# 后面的都是github copilot写的
class Add(QObject):
    
    def __init__(self) -> None:
        super(Add, self).__init__()


    @Slot(result="QVariantList")
    def all_script_files(self) -> list:
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

    @Slot(result="QVariantList")
    def all_json_file(self) -> list:
        """
        获取所有的json文件
        :return: ['oas1', 'oas2']
        """
        # 获取某个路径的所有json文件名
        config_path = Path.cwd() / 'config'
        json_files = config_path.glob('*.json')
        result = []
        for json in json_files:
            if json.stem == 'template':
                result.insert(0, json.stem)
            else:
                result.append(json.stem)
        return result


    @Slot(str, str)
    def copy(self, file: str, template: str = 'template') -> None:
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

        with open(template_path, 'r', encoding='utf-8') as f:
            template_content = f.read()
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(template_content)
        logger.info(f'copy {template_path} to {file_path}')


    @Slot(result="QString")
    def generate_script_name(self) -> str:
        """
        生成一个新的配置的名字
        :return:
        """
        all_script_files = self.all_script_files()
        if not all_script_files:
            return 'oas1'

        script_numbers = []
        for script_file in all_script_files:
            match = re.search(r'\d+', script_file)
            if match:
                script_number = int(match.group())
                script_numbers.append(script_number)

        if not script_numbers:
            return 'oas1'
        script_numbers.sort()
        new_script_number = script_numbers[-1] + 1
        return f'oas{new_script_number}'

if __name__ == "__main__":
    a = Add()
    print(a.all_script_files())
    print(a.all_json_file())
    print(a.generate_script_name())


