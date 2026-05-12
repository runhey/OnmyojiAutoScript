import importlib
from pathlib import Path

from module.base.utils import load_module
from module.exception import TaskEnd, RequestHumanTakeover
from module.logger import logger
from tasks.Component.SwitchAccount.switch_account import SwitchAccount as SwitchAccountHandler
from tasks.Component.SwitchAccount.switch_account_config import AccountInfo
from tasks.GameUi.game_ui import GameUi
from tasks.SwitchAccount.config import SwitchAccountConfig


class ScriptTask(GameUi):

    def run(self):
        conf: SwitchAccountConfig = self.config.switch_account.switch_account_config
        account_list = self.config.switch_account.sup_account_list

        if not account_list:
            logger.warning("No account configured for SwitchAccount task")
            self.set_next_run(task='SwitchAccount', success=True, finish=True)
            raise TaskEnd('SwitchAccount')

        task_name = conf.task_after_switch
        if task_name:
            logger.info("Will run task [%s] after each account switch", task_name)

        for account_info in account_list:
            if not account_info.is_valid():
                logger.warning("Account info is invalid, skip: %s", account_info.character)
                continue

            logger.hr(f"Switch to {account_info.character}-{account_info.svr}", 1)
            handler = SwitchAccountHandler(self.config, self.device, account_info)
            success = handler.switchAccount()

            if not success:
                logger.warning("Switch to %s-%s failed", account_info.character, account_info.svr)
                continue

            logger.info("Switch to %s-%s success", account_info.character, account_info.svr)
            self.config.switch_account.update_account_login_history(account_info)
            self.save_config()

            if not task_name:
                continue

            logger.hr(f"Run task [{task_name}] for {account_info.character}", 1)
            try:
                self._run_task(task_name)
            except TaskEnd:
                logger.info("Task [%s] completed for %s", task_name, account_info.character)
            except RequestHumanTakeover:
                raise
            except Exception as e:
                logger.error("Task [%s] failed for %s: %s", task_name, account_info.character, e)

        self.set_next_run(task='SwitchAccount', success=True, finish=True)
        raise TaskEnd('SwitchAccount')

    def _run_task(self, task_name: str):
        module_name = 'script_task'
        module_path = str(Path.cwd() / 'tasks' / task_name / (module_name + '.py'))
        logger.info(f"Loading task module: {module_path}")
        task_module = load_module(module_name, module_path)
        task_module.ScriptTask(config=self.config, device=self.device).run()

    def save_config(self):
        self.config.save()
