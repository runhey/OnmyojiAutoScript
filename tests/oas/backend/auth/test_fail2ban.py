"""Tests for the login failure throttling (fail2ban)."""

import json
import time

import pytest
from starlette import status
from starlette.requests import Request

from oas.backend.auth.errors import HTTPExceptionJson, error_detail
from oas.backend.auth.fail2ban import Fail2Ban, Fail2BanManager, get_client_ip

IP = '203.0.113.7'
NAME = '/login'


@pytest.fixture(autouse=True)
def clean_managers():
    """
    Run every test on an empty ban / failure store.
    """
    Fail2BanManager.singleton_clear()
    yield
    Fail2BanManager.singleton_clear()


def make_fail2ban(ip=IP):
    """
    Args:
        ip (str): The peer address the dependency would have captured

    Returns:
        Fail2Ban: The login guard bound to that address
    """
    login = Fail2Ban(NAME)
    login.ip = ip
    return login


def test_the_first_failure_returns_the_remaining_attempts():
    login = make_fail2ban()

    failure = login.record_failure()

    assert failure.status_code == status.HTTP_401_UNAUTHORIZED
    assert failure.detail == error_detail('FAIL2BAN_LOGIN_FAILED', {'remain': 4})


def test_the_fifth_failure_bans_the_ip():
    login = make_fail2ban()

    for remain in (4, 3, 2, 1):
        failure = login.record_failure()
        assert failure.status_code == status.HTTP_401_UNAUTHORIZED
        assert failure.detail == error_detail(
            'FAIL2BAN_LOGIN_FAILED', {'remain': remain}
        )

    banned = login.record_failure()

    assert banned.status_code == status.HTTP_403_FORBIDDEN
    assert banned.detail == error_detail('FAIL2BAN_BANNED', {'after': 600})


def test_a_banned_ip_is_refused_before_the_password_is_checked():
    login = make_fail2ban()
    Fail2BanManager(NAME).banned_ips[IP] = time.time() + 600

    with pytest.raises(HTTPExceptionJson) as banned:
        login.check_ban()

    assert banned.value.status_code == status.HTTP_403_FORBIDDEN
    assert json.loads(banned.value.detail)['err'] == 'FAIL2BAN_BANNED'


def test_an_expired_ban_is_dropped_and_not_extended():
    login = make_fail2ban()
    manager = Fail2BanManager(NAME)
    manager.banned_ips[IP] = time.time() - 1

    assert login.check_ban() is None
    assert IP not in manager.banned_ips


def test_an_unknown_ip_is_never_banned():
    login = make_fail2ban(ip=None)

    assert login.check_ban() is None
    assert login.record_success() is None


def test_a_successful_login_clears_the_failure_record():
    login = make_fail2ban()
    login.record_failure()

    login.record_success()

    assert IP not in Fail2BanManager(NAME).failed_attempts


def test_the_global_cooldown_refuses_every_login():
    manager = Fail2BanManager(NAME)
    # one failure is enough to trip the cooldown
    manager.global_threshold = 0
    login = make_fail2ban()
    login.record_failure()

    with pytest.raises(HTTPExceptionJson) as throttled:
        login.check_ban()

    assert throttled.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert json.loads(throttled.value.detail)['err'] == 'FAIL2BAN_TOO_MANY_REQUEST'


def test_a_failure_outside_the_counting_window_starts_over():
    login = make_fail2ban()
    manager = Fail2BanManager(NAME)
    manager.failed_attempts[IP] = (3, time.time() - manager.failure_window - 1)

    failure = login.record_failure()

    assert failure.detail == error_detail('FAIL2BAN_LOGIN_FAILED', {'remain': 4})


def test_the_peer_address_of_an_unknown_client_is_loopback():
    scope = {
        'type': 'http',
        'method': 'GET',
        'path': '/',
        'headers': [],
        'query_string': b'',
    }

    assert get_client_ip(Request(scope)) == '127.0.0.1'


def test_error_detail_omits_empty_data():
    assert error_detail('AUTH_TOKEN_INVALID') == b'{"err":"AUTH_TOKEN_INVALID"}'
    assert error_detail('FAIL2BAN_BANNED', {'after': 1}) == (
        b'{"err":"FAIL2BAN_BANNED","data":{"after":1}}'
    )
