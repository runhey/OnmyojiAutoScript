# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re
from pathlib import Path

from module.logger import logger

class ConfigManager:

    @staticmethod
    def all_script_files() -> list[str]:
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
        if len(result) == 0:
            # 如果没有脚本文件 则创建一个
            ConfigManager.copy(file='oas1', template='template')
            result.append('oas1')
        return result

    @staticmethod
    def all_json_file() -> list:
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

    @staticmethod
    def copy(file: str, template: str = 'template') -> None:
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


    @staticmethod
    def generate_script_name() -> str:
        """
        生成一个新的配置的名字
        :return:
        """
        all_script_files = ConfigManager.all_script_files()
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

    @staticmethod
    def rename(old_name: str, new_name: str) -> bool:
        """
        重命名一个配置文件
        :param old_name: 旧的配置文件名称
        :param new_name: 新的配置文件名称
        :return: True or False
        """
        config_path = Path.cwd() / 'config'
        old_path = config_path / f'{old_name}.json'
        new_path = config_path / f'{new_name}.json'
        if not old_path.exists():
            logger.error(f'{old_path} is not exists')
            return False
        if new_path.exists():
            logger.error(f'{new_path} is exists')
            return False
        try:
            old_path.rename(new_path)
            logger.info(f'rename {old_path} to {new_path}')
            return True
        except Exception as e:
            logger.error(f'rename {old_path} to {new_path} failed: {e}')
            return False

    @staticmethod
    def delete(file: str) -> bool:
        """
        删除一个配置文件
        :param file:  不带json后缀
        :return: True or False
        """
        config_path = Path.cwd() / 'config'
        file_path = config_path / f'{file}.json'
        if not file_path.exists():
            logger.error(f'{file_path} is not exists')
            return False
        try:
            file_path.unlink()
            logger.info(f'delete {file_path}')
            return True
        except Exception as e:
            logger.error(f'delete {file_path} failed: {e}')
            return False
