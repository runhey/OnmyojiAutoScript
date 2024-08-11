# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey


from tasks.base_task import BaseTask
from tasks.Script.config_device import ScreenshotMethod, ControlMethod

class FastDevice(BaseTask):

    def fast_screenshot(self):
        if self.config.model.script.device.screenshot_method != ScreenshotMethod.WINDOW_BACKGROUND:
            raise
        self.device.image = self.device.screenshot_window_background()
        return self.device.image
