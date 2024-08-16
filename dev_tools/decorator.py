# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
import timeit
import time
from datetime import datetime
from module.logger import logger


class usage_time:
    """
    Test the time of the code block
    Use example:
    with usage_time('test'):
        print('running')
    """

    def __init__(self, name: str = 'Timer'):
        self.name = name

    def __enter__(self):
        self.start_time = datetime.now()
        self.start_time = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.end_time = datetime.now()
        self.end_time = time.perf_counter()
        execution_time = self.end_time - self.start_time
        execution_time = (self.end_time - self.start_time) * 1000000  # 微秒
        logger.info(f'Execute[{str(self.name)}]: {execution_time:.2f} microseconds')


if __name__ == '__main__':
    with usage_time('test'):
        print('test1')
    print('end')
