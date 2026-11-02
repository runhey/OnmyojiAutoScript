# =============================================================================
# PROCESS BOUNDARY
#
# This module is imported by the SUPERVISOR process only (gui.py __main__
# block). The backend child reaches the web stack through
# entry.backend_entry (oas.backend.entry), never through this file.
# Keep heavy backend imports (app.py / starlette / anyio / uvicorn) OUT of
# this module: a module-level import here would pull the whole web stack
# into the supervisor process.
# =============================================================================

# Backend entry file should not have any heavy global import
# otherwise every child process will import them in spawn mode.
# The two module-level imports below are light: entry.py is stdlib-only,
# supervisor.py is stdlib-only. The actual backend entry (app.py, starlette,
# anyio, uvicorn) is imported lazily in oas.backend.entry.backend_entry.

import sys

from oas.backend.entry import backend_entry
from oas.backend.supervisor import Supervisor


class BackendWithSupervisor(Supervisor):
    # staticmethod wrapper is required: a plain function assigned as a class
    # attribute becomes a bound method on instance access, and pickling the
    # bound method would carry the Supervisor instance (with its
    # _thread.lock fields) into the backend child. `self.backend_entry` is
    # pickled into the backend child as spawn args, and the function lives
    # in oas.backend.entry (stdlib-only), so the child process never
    # imports this file nor supervisor.py.
    backend_entry = staticmethod(backend_entry)

    def run_gui(self, root, args=None):
        """
        Collect sys.argv and run the supervisor loop, passing the project
        root down to the backend through --root.

        Args:
            root (str): Absolute project root, e.g.
                os.path.dirname(os.path.abspath(__file__)) in the entry file
            args (list[str] | None): Extra command line args, appended after
                sys.argv[1:]
        """
        gui_args = sys.argv[1:]
        if args:
            gui_args += args
        gui_args += ['--root', root]
        self.run(gui_args)
