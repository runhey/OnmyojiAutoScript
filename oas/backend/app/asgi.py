# =============================================================================
# SERVER LAYER -- the ASGI app is served with uvicorn.
#
# Ported from ``alasio/backend/app/asgi.py``, which serves the same app with
# Hypercorn on trio. The mapping:
#
# * Hypercorn ``Config`` -> uvicorn ``Config``. The field names differ:
#   Hypercorn takes a ``bind`` list and ``keyfile`` / ``certfile``, uvicorn
#   takes ``host`` / ``port`` and ``ssl_keyfile`` / ``ssl_certfile``.
#   Assigning the Hypercorn names to a uvicorn config would only create plain
#   instance attributes and leave the port plaintext, so the SSL log line reads
#   ``Config.is_ssl`` -- the config's own answer -- and a mismatch shows up
#   there instead of staying silent.
# * ``BackendConfig.create_sockets()`` (announce the pipe readiness once the
#   listeners are bound) -> ``BackendServer.startup()``: uvicorn creates its
#   listeners at the end of ``Server.startup``, so announcing right after that
#   call sees the same state. The announce must NOT move into the lifespan:
#   uvicorn runs the lifespan startup before it binds, so announcing there would
#   end the supervisor's startup window while the port is still unbound, and a
#   bind failure (port in use) would then crash after the window ended -- the
#   supervisor would restart-loop instead of treating it as a startup failure.
# * Hypercorn ``shutdown_trigger`` -> ``BackendServer._watch_shutdown``, which
#   sets ``should_exit`` on the loop (see backend/README.md section 8).
# * ``apply_hypercorn_exclusivity_patch()`` -> not ported. It replaced
#   Hypercorn's unconditional ``SO_REUSEADDR`` with ``SO_EXCLUSIVEADDRUSE`` on
#   Windows so a second backend could not steal the listening port. uvicorn's
#   standard path binds through ``loop.create_server()``, and asyncio sets
#   ``SO_REUSEADDR`` only when ``os.name == 'posix'``, so on Windows the port is
#   exclusive already and there is nothing to patch. (uvicorn's own
#   ``Config.bind_socket()`` does set ``SO_REUSEADDR``, but it is only used when
#   a parent hands a socket down, e.g. under gunicorn workers; OAS serves one
#   backend process.)
# * the Hypercorn ``WorkerContext`` patch -> not ported, OAS has no Hypercorn
#   worker context: the lifespan owns the shutdown event (section 8).
#
# The app chain must only be imported once ``PROJECT_ROOT`` is set: the chain
# resolves its ``config/`` paths against ``oas.ext.env.PROJECT_ROOT``, so
# ``create_config`` parses ``--root`` and calls ``env.set_project_root`` before
# it imports ``oas.backend.app.app``.
# =============================================================================

import argparse
import asyncio
import contextlib
import os
import sys

from uvicorn import Config, Server

from oas.backend.app.lifespan import SHUTDOWN_EVENT, announce_started
from oas.backend.auth.password import WEAK_PASSWORD_MESSAGE, is_weak_password
from oas.deploy.settings.runtime import SettingsRuntime
from oas.ext import env
from oas.logger import logger


class BackendServer(Server):
    """
    uvicorn Server subclass: the two hooks the Hypercorn serving had.

    * announce the pipe readiness once the listeners are bound (upstream:
      ``BackendConfig.create_sockets``)
    * stop serving when the supervisor asks (upstream: the ``shutdown_trigger``
      Hypercorn awaited): the watch task waits for the lifespan shutdown event
      and then sets ``should_exit``, which makes ``Server.serve()`` return and
      lets the FastAPI lifespan run its own cleanup.
    """

    def __init__(self, config):
        """
        Args:
            config (Config): The uvicorn config to serve
        """
        super().__init__(config)
        self._shutdown_watch = None

    async def startup(self, sockets=None):
        """
        Bind the listeners, announce the pipe readiness, watch for the shutdown.

        Args:
            sockets (list[socket.socket] | None): Listeners to serve on, None to
                bind host/port
        """
        try:
            await super().startup(sockets)
        except SystemExit:
            # uvicorn exits the process when the bind fails (uvicorn/server.py
            # Server.startup: logger.error + lifespan.shutdown + sys.exit(1)).
            # Upstream logged the failed bind with the backend logger before the
            # process died, and that log is where the user sees why the port
            # stayed closed: keep it, then let the exit through.
            logger.critical(f'Failed to bind {self.config.host}:{self.config.port}')
            raise

        # every listener is bound and about to serve: tell the supervisor
        # (no-op when running without a supervisor pipe)
        announce_started()

        # Armed only when the lifespan owns a shutdown event: the proxy's wait()
        # returns immediately without one (it only warns), and a watch armed in
        # that state would stop the server on its first pass. The lifespan
        # startup above created the event (oas/backend/app/app.py).
        if SHUTDOWN_EVENT.event is not None:
            self._shutdown_watch = asyncio.create_task(self._watch_shutdown())

    async def shutdown(self, sockets=None):
        """
        Drop the watch task, then shut the server down.

        Args:
            sockets (list[socket.socket] | None): Listeners to close
        """
        watch = self._shutdown_watch
        if watch is not None:
            self._shutdown_watch = None
            watch.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watch
        await super().shutdown(sockets)

    @contextlib.contextmanager
    def capture_signals(self):
        """
        Keep the backend signal policy of ``entry.backend_process_entry``.

        On win32 the backend child ignores SIGINT / SIGBREAK: the signal goes to
        the whole process group, the supervisor takes it and tells the backend to
        stop over the pipe. Hypercorn's serve does not override that ignore,
        uvicorn would install its own ``handle_exit`` for both, so no handler is
        installed here. Elsewhere the signals were never ignored (upstream
        neither) and uvicorn's default handling is left in place.
        """
        if sys.platform == 'win32':
            yield
            return
        with super().capture_signals():
            yield

    async def _watch_shutdown(self):
        """
        Set ``should_exit`` once the supervisor asked the backend to stop.
        """
        await SHUTDOWN_EVENT.wait()
        self.should_exit = True


def create_config(args=None):
    """
    Args:
        args (list[str] | None): Commandline args from supervisor level
            Use this `args` input instead of `sys.args`, as backend is a sub-process

    Returns:
        Config: uvicorn config carrying the app and the listeners described by
            the deploy settings and the args
    """
    logger.hr('Start', level=0)

    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=str, default='')
    parser.add_argument('--host', type=str, default='')
    parser.add_argument('--port', type=int, default=0)
    parsed_args, _ = parser.parse_known_args(args)

    # set project root, so we have the right path to save ./config
    if parsed_args.root:
        env.set_project_root(parsed_args.root)
        os.chdir(parsed_args.root)
    else:
        env.set_project_root(os.getcwd())
    logger.attr('PROJECT_ROOT', env.PROJECT_ROOT)
    logger.attr('FLUTTER', bool(env.FLUTTER))

    # OAS reads the deploy settings through SettingsRuntime, and that runtime
    # writes config/deploy.json from the model defaults on the first access
    # (upstream called DeployConfig().config.show() / .write() here and dumped
    # the loaded config; the runtime folds the write in and has no dump).
    deploy = SettingsRuntime().data.backend

    # Password strength: the flag is a property of the settings, and the
    # plaintext never becomes a variable of this long-lived frame -- the logger
    # renders exception tracebacks with show_locals=True. A weak password is
    # refused by the admission gate (only the local Flutter client passes), warn
    # about it at startup where the user still sees the logs. An empty password
    # is not weak, it is simply no password (upstream: bool(Password) and
    # is_weak_password(...)).
    if deploy.password and is_weak_password(deploy.password):
        logger.warning(WEAK_PASSWORD_MESSAGE)

    # build host port
    if parsed_args.host:
        host = parsed_args.host
    elif deploy.host:
        host = deploy.host
    else:
        host = '0.0.0.0'
    if parsed_args.port:
        port = parsed_args.port
    elif deploy.port:
        port = deploy.port
    else:
        port = 22888
    logger.attr('Bind', f'{host}:{port}')

    # local import, after set_project_root(): the app chain resolves its
    # config/ paths against PROJECT_ROOT (see the module header). The Hypercorn
    # WorkerContext patch upstream ran next to it has no counterpart here.
    from oas.backend.app.app import create_app

    app = create_app()

    # SSL wiring: when both key and cert are configured the deployment
    # auto-enters public mode (DeploymentGateMiddleware mode detection) and
    # https is served. Note the field names: uvicorn Config takes `ssl_keyfile`
    # / `ssl_certfile`, where upstream's Hypercorn took `keyfile` / `certfile`;
    # assigning the wrong names would silently create plain instance attributes
    # and leave the port plaintext.
    ssl_keyfile = deploy.ssl_key if deploy.ssl_key and deploy.ssl_cert else None
    ssl_certfile = deploy.ssl_cert if deploy.ssl_key and deploy.ssl_cert else None
    config = Config(
        app,
        host=host,
        port=port,
        ssl_keyfile=ssl_keyfile,
        ssl_certfile=ssl_certfile,
    )
    logger.attr('SSL', config.is_ssl)

    # To enable access log
    # config.access_log = True

    return config


async def serve_app(args=None):
    config = create_config(args)

    server = BackendServer(config)
    await server.serve()


def run(args=None):
    """
    Backend entry point
    """
    # asyncio.run takes the coroutine object itself: upstream's
    # ``trio.run(functools.partial(serve_app, args=args))`` works because
    # trio.run accepts a callable, asyncio.run does not.
    asyncio.run(serve_app(args))
