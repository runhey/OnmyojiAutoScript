import datetime
import subprocess
import threading
import time
import requests
from typing import Generator, List, Tuple

from deploy.config import ExecutionError
from deploy.git import GitManager
from deploy.pip import PipManager
from deploy.utils import DEPLOY_CONFIG
from module.logger import logger
from module.base.retry import retry
from module.server.config import DeployConfig


class Updater(DeployConfig, GitManager, PipManager):
    def __init__(self, file=DEPLOY_CONFIG):
        super().__init__(file=file)
        self.state = 0

    @property
    def delay(self):
        self.read()
        return int(self.CheckUpdateInterval) * 60

    @property
    def schedule_time(self):
        self.read()
        t = self.AutoRestartTime
        if t is not None:
            return datetime.time.fromisoformat(t)
        else:
            return None

    def execute_output(self, command) -> str:
        command = command.replace(r"\\", "/").replace("\\", "/").replace('"', '"')
        log = subprocess.run(
            command, capture_output=True, text=True, encoding="utf8", shell=True
        ).stdout
        return log

    def get_commit(self, revision="", n=1, short_sha1=False) -> Tuple:
        """
        Return:
            (sha1, author, isotime, message,)
        """
        ph = "h" if short_sha1 else "H"

        log = self.execute_output(
            f'"{self.git}" log {revision} --pretty=format:"%{ph}---%an---%ad---%s" --date=iso -{n}'
        )

        if not log:
            return None, None, None, None

        logs = log.split("\n")
        logs = list(map(lambda log: tuple(log.split("---")), logs))

        if n == 1:
            return logs[0]
        else:
            return logs

    def current_branch(self) -> str:
        return self.Branch

    def current_commit(self) -> str:
        return self.get_commit()

    def latest_commit(self) -> str:
        source = "origin"
        return self.get_commit(f"{source}/{self.Branch}")

    def check_update(self) -> bool:
        self.state = "checking"

        # if State.deploy_config.GitOverCdn:
        #     status = self.goc_client.get_status()
        #     if status == "uptodate":
        #         logger.info(f"No update")
        #         return False
        #     elif status == "behind":
        #         logger.info(f"New update available")
        #         return True
        #     else:
        #         # failed, should fallback to `git pull`
        #         pass

        source = "origin"
        for _ in range(3):
            if self.execute(
                    f'"{self.git}" fetch {source} {self.Branch}', allow_failure=True
            ):
                break
        else:
            logger.warning("Git fetch failed")
            return False

        log = self.execute_output(
            f'"{self.git}" log --not --remotes={source}/* -1 --oneline'
        )
        if log:
            logger.info(
                f"Cannot find local commit {log.split()[0]} in upstream, skip update"
            )
            return False

        sha1, _, _, message = self.get_commit(f"..{source}/{self.Branch}")

        if sha1:
            logger.info(f"New update available")
            logger.info(f"{sha1[:8]} - {message}")
            return True
        else:
            logger.info(f"No update")
            return False

    def execute_pull(self) -> bool:
        source = "origin"
        for _ in range(3):
            if self.execute(
                    f'"{self.git}" pull {source} {self.Branch} --no-rebase', allow_failure=True
            ):
                break
        else:
            logger.warning("Git fetch failed")
            return False



if __name__ == "__main__":
    updater = Updater()
    print(updater.latest_commit())



