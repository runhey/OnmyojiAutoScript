# =============================================================================
# FAKE BACKEND BRIDGE -- placeholder only.
#
# Alasio's oas/logger/writer.py imports BackendBridge from this exact path to
# decide whether log events should also be pushed to a backend process over a
# multiprocessing pipe. OAS has no backend process, so this stub keeps the
# import path alive and reports `inited = False`; the writer then falls back
# to file + stdout output.
#
# Only the members oas/logger touches are declared. Replace this file with the
# real bridge when OAS grows a backend.
# =============================================================================

from typing import Literal

from oas.ext.singleton import Singleton


class _Job:
    """
    Stands in for the real send job. Alasio's writer calls `job.acquire()`
    after flushing a log line; there is nothing to wait for here.
    """

    def acquire(self):
        pass


class BackendBridge(metaclass=Singleton):
    def __init__(self):
        self.inited = False
        self.mod_name = ''
        self.config_name = ''

    def send_log(self, value):
        return _Job()

    def send_worker_state(self, value: Literal['running', 'scheduler-waiting', 'error']):
        return _Job()