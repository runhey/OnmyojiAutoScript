"""Tests for the one-time renewal codes of the ws handshake."""

import pytest
from fastapi.testclient import TestClient
from starlette import status

from oas.backend.app.app import create_app
from oas.backend.auth.auth import JWT_MANAGER
from oas.backend.ws.renew import (
    RenewalCodeManager,
    RenewalLimitExceeded,
    renewal_manager,
)

from ws_helpers import TEST_TOKEN

PASSWORD = 'test-password'
COOKIE = 'oas_token'


@pytest.fixture(autouse=True)
def clean_renewal_manager():
    """
    Run every test on an empty code table.
    """
    renewal_manager._codes.clear()
    yield
    renewal_manager._codes.clear()


@pytest.fixture
def clock():
    """
    Returns:
        callable: A hand-driven monotonic clock for the code ttl
    """

    class Clock:
        now = 1000.0

        def __call__(self):
            return self.now

    return Clock()


def test_a_code_is_redeemed_exactly_once(clock):
    manager = RenewalCodeManager(clock=clock)
    code = manager.issue()

    assert manager.redeem(code) is True
    assert manager.redeem(code) is False


def test_a_code_expires_after_its_ttl(clock):
    manager = RenewalCodeManager(ttl=20.0, clock=clock)

    at_the_limit = manager.issue()
    clock.now += 20.0
    # a code expires only when now - issued > ttl: == ttl is still valid
    assert manager.redeem(at_the_limit) is True

    too_late = manager.issue()
    clock.now += 20.1
    assert manager.redeem(too_late) is False


def test_a_full_table_refuses_to_issue(clock):
    manager = RenewalCodeManager(ttl=1000.0, max_codes=2, clock=clock)
    manager.issue()
    manager.issue()

    with pytest.raises(RenewalLimitExceeded):
        manager.issue()


def test_issue_of_a_full_table_reclaims_the_expired_codes(clock):
    manager = RenewalCodeManager(ttl=20.0, max_codes=1, clock=clock)
    manager.issue()

    clock.now += 30.0

    assert manager.issue()


def test_gc_removes_the_expired_codes(clock):
    manager = RenewalCodeManager(ttl=20.0, clock=clock)
    expired = manager.issue()
    clock.now += 30.0

    assert manager.gc() == 1
    assert manager.redeem(expired) is False


def test_a_fresh_issue_reclaims_the_expired_codes(clock):
    manager = RenewalCodeManager(ttl=20.0, clock=clock)
    expired = manager.issue()
    clock.now += 30.0

    live = manager.issue()

    # issue() sweeps the table before the capacity check, so the expired code
    # never counts against the cap
    assert manager.redeem(expired) is False
    assert manager.redeem(live) is True
    assert not manager._codes


def test_gc_of_an_empty_table_removes_nothing():
    assert RenewalCodeManager().gc() == 0


def test_the_endpoint_needs_both_layers(deploy_config, loopback_gate):
    """
    require_login proves the user is logged in, require_local_flutter proves the
    request comes from the local app: a remote logged-in user never gets a
    code, otherwise they could upgrade their connection to the local level.
    """
    deploy_config(backend={'password': PASSWORD})

    with TestClient(create_app()) as client:
        # no JWT: the login layer of the gate refuses the request
        assert client.post('/api/ws/renew').status_code == status.HTTP_401_UNAUTHORIZED

        refused = client.post('/api/ws/renew', cookies={COOKIE: JWT_MANAGER.create()})

    assert refused.status_code == status.HTTP_403_FORBIDDEN
    assert refused.json() == {'err': 'AUTH_LOCAL_FLUTTER_ONLY'}


def test_the_endpoint_issues_a_code_for_the_local_app(deploy_config, loopback_gate):
    deploy_config(backend={'password': PASSWORD})

    with TestClient(create_app()) as client:
        response = client.post(
            '/api/ws/renew',
            cookies={COOKIE: JWT_MANAGER.create()},
            headers={'X-OAS-Token': TEST_TOKEN},
        )

    assert response.status_code == status.HTTP_200_OK
    code = response.json()['code']
    assert len(code) == 64
    assert renewal_manager.redeem(code) is True


def test_the_endpoint_refuses_when_the_table_is_full(
    deploy_config, loopback_gate, monkeypatch
):
    deploy_config(backend={'password': PASSWORD})
    monkeypatch.setattr(renewal_manager, '_max_codes', 0)

    with TestClient(create_app()) as client:
        response = client.post(
            '/api/ws/renew',
            cookies={COOKIE: JWT_MANAGER.create()},
            headers={'X-OAS-Token': TEST_TOKEN},
        )

    assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert response.json() == {'err': 'WS_RENEWAL_LIMIT_EXCEEDED'}
