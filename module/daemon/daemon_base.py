from tasks.base_task import BaseTask


class DaemonBase(BaseTask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.device.disable_stuck_detection()
