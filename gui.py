# =============================================================================
# PROCESS BOUNDARY -- heavy imports must stay inside the `if __name__ ==
# '__main__':` block.
#
# This entry script is re-executed by EVERY spawn child (as __mp_main__):
# backend and worker children run the module level of this file. Module
# level must stay minimal (patch_startup only); the BackendWithSupervisor
# import must stay inside the __main__ block, or the children would import
# the whole supervisor stack.
# =============================================================================

from oas.backport.patch import patch_startup

patch_startup()

if __name__ == '__main__':
    import os

    # run
    from oas.backend.backend import BackendWithSupervisor

    supervisor = BackendWithSupervisor().multiprocessing_freeze_support()
    # --root is passed down to the backend (and then the worker) so the
    # process chain works even when gui.py is started from another cwd
    supervisor.run_gui(root=os.path.dirname(os.path.abspath(__file__)))
