"""
Tests for the uvicorn server layer (``oas/backend/app/asgi.py``).

The serving chain itself is covered end to end by ``.portcheck/probe_entry.py``
(spawn -> bind -> announce -> token round trip -> stop). What is tested here is
the part that is easy to get quietly wrong: which values the config takes from
the args and the deploy settings, the SSL field names, and the win32 signal
policy that entry.py installed before the server starts.
"""

import sys
import types

import pytest
import uvicorn

from oas.backend.app import asgi
from oas.backend.auth.password import WEAK_PASSWORD_MESSAGE
from oas.backend.mpipe.token_backend import token_table
from oas.deploy.settings.runtime import SettingsRuntime
from oas.ext import env
from oas.logger import logger


@pytest.fixture(autouse=True)
def clean_globals():
    """
    Restore the process-wide values create_config sets.
    """
    project_root = env.PROJECT_ROOT
    tokens = token_table._tokens
    yield
    env.PROJECT_ROOT = project_root
    token_table._tokens = tokens


def stub_backend(monkeypatch, **fields):
    """
    Replace the deploy settings with a stub backend group.

    Args:
        monkeypatch (MonkeyPatch): Fixture
        **fields: Backend field overrides, e.g. password='short'

    Returns:
        SimpleNamespace: The stub that create_config will read
    """
    values = {
        'host': '',
        'port': 0,
        'password': None,
        'ssl_key': '',
        'ssl_cert': '',
    }
    values.update(fields)
    backend = types.SimpleNamespace(**values)
    monkeypatch.setattr(
        SettingsRuntime,
        'data',
        property(lambda self: types.SimpleNamespace(backend=backend)),
    )
    return backend


def test_create_config_takes_root_host_and_port_from_the_args(monkeypatch, tmp_path):
    """
    The supervisor passes --root / --host / --port down; the args win over the
    deploy settings, and --root also becomes the project root (the app chain
    resolves config/ paths against it).
    """
    monkeypatch.chdir(tmp_path)
    stub_backend(monkeypatch, host='0.0.0.0', port=22888)

    config = asgi.create_config(
        ['--root', str(tmp_path), '--host', '127.0.0.1', '--port', '23451']
    )

    assert config.host == '127.0.0.1'
    assert config.port == 23451
    # PathStr is a str subclass and normalizes to forward slashes
    assert env.PROJECT_ROOT.replace('\\', '/') == str(tmp_path).replace('\\', '/')
    assert config.is_ssl is False
    # 'auto' lets uvicorn drive the FastAPI lifespan, which is where the
    # shutdown event the MPipe loop signals lives (the probe asserts it runs)
    assert config.lifespan == 'auto'


def test_create_config_falls_back_to_the_deploy_settings(monkeypatch, tmp_path):
    """
    Without --host / --port the deploy settings decide, which is how a normal
    launch is configured.
    """
    monkeypatch.chdir(tmp_path)
    stub_backend(monkeypatch, host='0.0.0.0', port=22888)

    config = asgi.create_config(['--root', str(tmp_path)])

    assert config.host == '0.0.0.0'
    assert config.port == 22888


def test_create_config_wires_ssl_with_the_uvicorn_field_names(monkeypatch, tmp_path):
    """
    Both key and cert configured means https: the names must be uvicorn's
    (ssl_keyfile / ssl_certfile), a Hypercorn-shaped assignment would only set
    unused attributes and serve the port plaintext.
    """
    monkeypatch.chdir(tmp_path)
    stub_backend(monkeypatch, ssl_key='key.pem', ssl_cert='cert.pem')

    config = asgi.create_config(['--root', str(tmp_path)])

    assert config.ssl_keyfile == 'key.pem'
    assert config.ssl_certfile == 'cert.pem'
    assert config.is_ssl is True


def test_create_config_warns_on_a_weak_password(monkeypatch, tmp_path):
    """
    A weak password is refused by the admission gate, so the startup log is the
    only place the user learns why the local client is locked out.
    """
    monkeypatch.chdir(tmp_path)
    stub_backend(monkeypatch, password='short')

    with logger.mock_capture_writer() as capture:
        asgi.create_config(['--root', str(tmp_path)])

    assert capture.backend.any_contains(WEAK_PASSWORD_MESSAGE)


def test_create_config_does_not_warn_without_a_password(monkeypatch, tmp_path):
    """
    An empty password is not a weak one: a deployment without a password is
    warned about by the login page, not by a strength warning at startup.
    """
    monkeypatch.chdir(tmp_path)
    stub_backend(monkeypatch, password=None)

    with logger.mock_capture_writer() as capture:
        asgi.create_config(['--root', str(tmp_path)])

    assert not capture.backend.any_contains(WEAK_PASSWORD_MESSAGE)


def test_backend_server_keeps_the_win32_signal_ignore(monkeypatch):
    """
    entry.py ignored SIGINT / SIGBREAK on win32 so the supervisor owns the
    signal; uvicorn would install its own handler for both, so the server must
    not install one there. Elsewhere uvicorn's handling stays in place.
    """

    def boom(self):
        raise AssertionError('uvicorn installed its own signal handlers')

    monkeypatch.setattr(uvicorn.Server, 'capture_signals', boom)
    server = asgi.BackendServer(uvicorn.Config(lambda scope, receive, send: None))

    monkeypatch.setattr(sys, 'platform', 'win32')
    with server.capture_signals():
        pass

    monkeypatch.setattr(sys, 'platform', 'linux')
    with pytest.raises(AssertionError):
        with server.capture_signals():
            pass
