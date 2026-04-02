# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import re

from pathlib import Path

from filelock import FileLock


def remove_symbols(text):
    return re.sub(r'[^\w\s]', '', text)


class Debugger:

    def _log_file(self) -> Path:
        file: Path = Path(f'./log/quiz/supplement.txt')
        if not file.parent.exists():
            file.parent.mkdir(parents=True)
        if not file.exists():
            file.touch()
        return file

    def append_one(self, question: str, options: list[str]):
        question = remove_symbols(question)
        options = [remove_symbols(option) for option in options]
        file = self._log_file()
        lock = FileLock(f"{file}.lock")
        line = f'{question},{options[0]},{options[1]},{options[2]},{options[3]}\n'
        with lock:
            with open(file, 'a', encoding='utf-8') as f:
                f.write(line)
                f.flush()

    def close_fn(self):
        return


if __name__ == '__main__':
    a = Debugger()
    a.append_one('1', ['1', '2', '3', '4'])
    a.append_one('5', ['1', '2939/;.', '3', '4'])
    a.append_one('1', ['1', '2', '3', '4'])
    a.close_fn()
