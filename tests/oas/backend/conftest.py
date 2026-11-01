"""
Fixtures shared by the backend test packages: an isolated deploy settings
file and an isolated JWT secret.

Both isolate the test process from the repository: the real settings file
(``config/deploy.json``) and the real key table (``config/gui.db``, an sqlite
file holding the JWT secret) live in the repository config directory, which a
test must neither read nor create.
"""

import pytest

from oas.backend.auth.auth import JwtManager
from oas.deploy.settings.runtime import SettingsRuntime
from oas.ext.file.jsonfile import write_json

# 32 bytes: the minimum PyJWT recommends for HS256
TEST_JWT_SECRET = b'test-jwt-secret-0123456789abcdef'


@pytest.fixture(autouse=True)
def test_jwt_secret(monkeypatch):
    """
    A fixed JWT secret instead of the key table of the repository.

    Replaces the ``JwtManager.secret`` cached property outright: the real
    one reads ``KeyTable('gui').jwt_secret``, an sqlite file created under
    the repository config directory on first use.
    """
    monkeypatch.setattr(JwtManager, 'secret', property(lambda self: TEST_JWT_SECRET))


@pytest.fixture(autouse=True)
def deploy_config(tmp_path):
    """
    Isolated deploy settings: SettingsRuntime reads a deploy.json under the
    pytest tmp dir, so a test never touches ``config/deploy.json``.

    Automatic: every backend test that reaches the deployment gate (through
    a request, a handshake or the JWT manager) would otherwise read the
    settings of the repository.

    Returns:
        callable: write(**sections) writes the file, clears the singleton
            and points SettingsRuntime at it. Called without arguments it
            writes the defaults (no password, no SSL), so the gate is in
            lan mode and rule A refuses every web access.
    """
    path = tmp_path / 'config' / 'deploy.json'
    path.parent.mkdir(parents=True, exist_ok=True)

    def write(**sections):
        write_json(str(path), sections)
        SettingsRuntime.singleton_clear()
        SettingsRuntime(file=str(path))
        return str(path)

    SettingsRuntime.singleton_clear()
    write()
    yield write
    SettingsRuntime.singleton_clear()


@pytest.fixture
def loopback_gate(monkeypatch):
    """
    Make the deployment gate see the test client as a loopback client.

    The test client connects from the host name ``testclient``, which is not
    an ip address, and rule B refuses every non-lan source in lan mode. The
    real peer address is given by the ASGI server, so pinning it here is the
    only seam needed to exercise the rules behind it.
    """
    from oas.backend.middleware.gate import DeploymentGateMiddleware

    monkeypatch.setattr(
        DeploymentGateMiddleware, '_client_host', lambda self, scope: '127.0.0.1'
    )
