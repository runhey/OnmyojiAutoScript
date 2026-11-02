# =============================================================================
# PROCESS BOUNDARY -- ALL oas imports in this file must stay LOCAL
# (inside functions).
#
# This module is the backend child entry: the spawn target
# (backend_process_entry) and the entry callable (backend_entry) are
# pickled into the backend child by module path, and the supervisor process
# imports this module too (start_backend). The child therefore only imports
# THIS file plus stdlib. Module-level imports must stay stdlib-only;
# every oas import here must be a local import, or it leaks the web
# stack / backend business modules across the supervisor / backend process
# boundary.
# =============================================================================

# Backend process entry point.
#
# The spawn target and the backend entry callable live in their own module
# (stdlib imports only) so the backend child process only ever imports this
# file when multiprocessing deserializes the spawn arguments. supervisor.py
# and backend.py are supervisor-process modules: keeping them out of the
# backend process keeps the process boundary clean.

import os
import signal
import sys


def backend_entry(args):
    """
    Backend entry point, invoked by the supervisor through the spawn args.

    Runs in the backend child process, after backend_process_entry sets up
    the pipe connection.

    Args:
        args (list[str] | None): Command line args for the backend
    """
    # asgi (the server layer) instead of app: asgi imports the ASGI app
    # lazily, only after create_config() set PROJECT_ROOT -- the app chain
    # binds env.PROJECT_ROOT at import time (see asgi.py)
    from oas.backend.app.asgi import run

    run(args)


def backend_process_entry(conn, args, backend_entry_fn, tokens=()):
    """
    Entry point for the backend process.

    Runs in the child process. Sets up the pipe connection as a global
    variable that the backend code can access, then starts the actual backend
    application.

    A module-level function instead of a bound method: the process object is
    pickled into the child, and pickling the Supervisor instance (with its
    cyclic process/pipe references) makes spawn hang on Windows when stdin is
    a pipe.

    Args:
        conn (PipeConnection): Pipe connection to the supervisor
        args (list[str] | None): Command line args for the backend
        backend_entry_fn (Callable): The backend entry callable, usually a
            module-level function in this file
        tokens (tuple[str]): Initial token window from the supervisor
            (empty when not started with --flutter). Seeded into the
            backend token table before serve, so the table is populated
            before any request can arrive (single-writer constraint).
    """
    import builtins

    builtins.__mpipe_conn__ = conn

    # Tell the supervisor the spawn handshake is done. Running this target
    # means the child is already past Py_Initialize (its stdio was
    # initialized during boot), so the supervisor may start its stdin
    # listener now -- the listener only has to stay stopped while the
    # child initializes stdio (Windows constraint, see supervisor.py).
    # This is NOT a startup confirmation: the backend has not finished
    # starting, so recv_loop keeps its startup window running (a crash
    # later in the window, e.g. a bind conflict, must still count as a
    # startup failure instead of a restart loop).
    try:
        conn.send_bytes(b'command:spawned')
    except EOFError, OSError:
        # supervisor already gone, nothing to notify
        pass

    # ignore SIGINT on windows because signal is send to the entire process group
    # Supervisor should receive SIGINT and backend should ignore, then supervisor tell backend to stop
    if sys.platform == 'win32':
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        signal.signal(signal.SIGBREAK, signal.SIG_IGN)

    # The child inherits the stdin pipe from the supervisor (Windows spawn
    # inherits stdio regardless of bInheritHandles). The backend never reads
    # stdin, but point it at devnull anyway so it can never steal commands
    # meant for the supervisor's stdin listener.
    try:
        sys.stdin = open(os.devnull, 'r', encoding='utf-8')
    except OSError:
        pass

    # Seed the token table before the backend (and its mpipe_recv_loop
    # thread, started in the lifespan) runs: this is the single
    # writer of the lock-free BackendTokenTable.
    if tokens:
        from oas.backend.mpipe.token_backend import token_table

        token_table.seed_from_supervisor(tokens)

    try:
        backend_entry_fn(args)
    except Exception as e:
        # Unexpected error in backend
        print(f'[Backend] Fatal error: {e}')
        import traceback

        traceback.print_exc()
    # Note that it's parent's responsibility to close pipe
