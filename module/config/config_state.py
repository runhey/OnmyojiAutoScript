# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey


class ConfigState:
    """
    这个类用于 先定义运行过程中所需要的变量
    """
    def __init__(self, config_name: str) -> None:
        self.config_name = config_name
        self.pending_task = []
        self.waiting_task = []
