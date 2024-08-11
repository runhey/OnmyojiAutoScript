# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey


from datetime import datetime

from module.logger import logger


class usage_time:
    def __init__(self, name: str = None):
        self.name = 'Timer' if name is None else name

    def __enter__(self):
        self.start_time = datetime.now()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.end_time = datetime.now()
        execution_time = self.end_time - self.start_time
        logger.info(f'{str(self.name)}: {execution_time.total_seconds() * 1000 }ms')


if __name__ == '__main__':
    with usage_time('test'):
        print('test1')
    print('end')
