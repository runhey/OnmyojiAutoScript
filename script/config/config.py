from oas.config.runtime.config_task import ConfigTask


class Config(ConfigTask):
    def __init__(self, config_name: str, task: str = ''):
        super().__init__(config_name, task)
