# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re

from cached_property import cached_property
from pathlib import Path

from module.logger import logger


def remove_symbols(text):
    return re.sub(r'[^\w\s]', '', text)

class Debugger:

    @cached_property
    def fn(self):
        # 以添加方式打开一个文件
        file: Path = Path(f'./log/quiz/supplement.txt')
        if not file.parent.exists():
            file.parent.mkdir(parents=True)
        if not file.exists():
            file.touch()
        f = open(str(file), 'a', encoding='utf-8')
        return f

    def append_one(self, question: str, options: list[str]):
        question = remove_symbols(question)
        options = [remove_symbols(option) for option in options]
        self.fn.write(f'{question},{options[0]},{options[1]},{options[2]},{options[3]}\n')

    def close_fn(self):
        self.fn.close()


if __name__ == '__main__':
    a = Debugger()
    a.append_one('1', ['1', '2', '3', '4'])
    a.append_one('5', ['1', '2939/;.', '3', '4'])
    a.append_one('1', ['1', '2', '3', '4'])
    a.close_fn()
