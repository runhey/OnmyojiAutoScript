"""Tests for the JWT manager, the auth endpoints and the auth dependencies."""

import hashlib
import time

import jwt
import pytest
from fastapi.testclient import TestClient
from starlette import status
from starlette.requests import Request

from oas.backend.app.app import create_app
from oas.backend.auth.auth import JWT_MANAGER
from oas.backend.auth.deps import require_local_flutter, require_login
from oas.backend.auth.errors import HTTPExceptionJson

pytestmark = pytest.mark.anyio

PASSWORD = 'test-password'
TEST_TOKEN = 'test-local-token'
COOKIE = 'oas_token'
# the key table is stubbed by tests/oas/backend/conftest.py
SECRET = b'test-jwt-secret-0123456789abcdef'


def digest(pwd=PASSWORD):
    """
    Args:
        pwd (str): The password to digest

    Returns:
        str: The versioned digest the manager puts in the JWT subject
    """
    return 'v1:' + hashlib.sha256(pwd.encode()).hexdigest()


def make_token(iat=None, pwd=PASSWORD, secret=SECRET):
    """
    Build a token by hand, to reach the states the manager itself never
    issues (an old iat, another password, another secret).

    Args:
        iat (int, optional): Issued-at stamp. Defaults to now.
        pwd (str): The password the subject digests
        secret (bytes): The signing key

    Returns:
        str: The encoded token
    """
    now = int(time.time())
    return jwt.encode(
        {'sub': digest(pwd), 'iat': iat or now, 'exp': now + 3600},
        secret,
        algorithm='HS256',
    )


def decode(token):
    """
    Args:
        token (str): A token issued by the manager

    Returns:
        dict: The decoded payload
    """
    return jwt.decode(token, JWT_MANAGER.secret, algorithms=['HS256'])


def make_request(header=None, cookie=None):
    """
    A minimal http request for the dependencies.

    Args:
        header (str, optional): Value of the X-OAS-Token header
        cookie (str, optional): Value of the oas_token cookie

    Returns:
        Request: The request
    """
    headers = []
    if header is not None:
        headers.append((b'x-oas-token', header.encode()))
    if cookie is not None:
        headers.append((b'cookie', f'{COOKIE}={cookie}'.encode()))
    scope = {
        'type': 'http',
        'method': 'GET',
        'path': '/api/test',
        'headers': headers,
        'query_string': b'',
        'scheme': 'http',
        'server': ('127.0.0.1', 22288),
        'client': ('127.0.0.1', 1234),
    }
    return Request(scope)


def test_create_stamps_the_password_digest_and_the_lifetime(deploy_config):
    deploy_config(backend={'password': PASSWORD})

    payload = decode(JWT_MANAGER.create())

    assert payload['sub'] == digest()
    assert payload['exp'] - payload['iat'] == 168 * 3600


def test_an_empty_password_leaves_the_subject_empty(deploy_config):
    deploy_config()

    assert decode(JWT_MANAGER.create())['sub'] == ''


def test_a_fresh_token_is_kept(deploy_config):
    deploy_config(backend={'password': PASSWORD})

    assert JWT_MANAGER.validate_token(JWT_MANAGER.create()) == ''


def test_a_token_issued_over_an_hour_ago_is_renewed(deploy_config):
    deploy_config(backend={'password': PASSWORD})
    old = make_token(iat=int(time.time()) - 3601)

    renewed = JWT_MANAGER.validate_token(old)

    assert renewed and renewed != old


def test_a_password_change_invalidates_an_issued_token(deploy_config):
    deploy_config(backend={'password': PASSWORD})
    token = JWT_MANAGER.create()

    # the settings are re-read on every access: no restart is needed for the
    # password change to apply (Alasio caches it and needs a restart)
    deploy_config(backend={'password': 'another-password'})

    with pytest.raises(jwt.PyJWTError):
        JWT_MANAGER.validate_token(token)


def test_no_password_issues_a_token_instead_of_refusing(deploy_config):
    deploy_config()

    assert JWT_MANAGER.validate_token('')


def test_validate_pwd_checks_the_configured_password(deploy_config):
    deploy_config(backend={'password': PASSWORD})

    assert JWT_MANAGER.validate_pwd(PASSWORD)

    with pytest.raises(jwt.PyJWTError):
        JWT_MANAGER.validate_pwd('wrong-password')


@pytest.mark.parametrize('token', ['', 'not-a-jwt'])
def test_a_malformed_token_is_refused(deploy_config, token):
    deploy_config(backend={'password': PASSWORD})

    with pytest.raises(jwt.PyJWTError):
        JWT_MANAGER.validate_token(token)


def test_a_token_signed_with_another_secret_is_refused(deploy_config):
    deploy_config(backend={'password': PASSWORD})
    forged = make_token(secret=b'another-secret-0123456789abcdefgh')

    with pytest.raises(jwt.PyJWTError):
        JWT_MANAGER.validate_token(forged)


async def test_require_local_flutter_admits_a_table_token():
    assert await require_local_flutter(make_request(header=TEST_TOKEN)) is None


@pytest.mark.parametrize('header', [None, 'not-a-table-token'])
async def test_require_local_flutter_refuses_a_missing_or_stale_token(header):
    with pytest.raises(HTTPExceptionJson) as refused:
        await require_local_flutter(make_request(header=header))

    assert refused.value.status_code == status.HTTP_403_FORBIDDEN
    assert refused.value.detail == b'{"err":"AUTH_LOCAL_FLUTTER_ONLY"}'


async def test_require_login_admits_a_valid_cookie(deploy_config):
    deploy_config(backend={'password': PASSWORD})

    assert await require_login(make_request(cookie=JWT_MANAGER.create())) is None


async def test_require_login_refuses_a_missing_or_invalid_cookie(deploy_config):
    deploy_config(backend={'password': PASSWORD})

    for cookie in (None, 'not-a-jwt'):
        with pytest.raises(HTTPExceptionJson) as refused:
            await require_login(make_request(cookie=cookie))
        assert refused.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert refused.value.detail == b'{"err":"AUTH_TOKEN_INVALID"}'
        assert refused.value.headers == {'WWW-Authenticate': 'Bearer'}


def test_login_sets_the_jwt_cookie(deploy_config, loopback_gate):
    deploy_config(backend={'password': PASSWORD})

    with TestClient(create_app()) as client:
        response = client.post('/api/auth/login', json={'pwd': PASSWORD})

    assert response.status_code == status.HTTP_200_OK
    cookie = response.headers['set-cookie']
    assert f'{COOKIE}=' in cookie
    assert 'HttpOnly' in cookie
    assert 'SameSite=strict' in cookie
    assert f'Max-Age={168 * 3600}' in cookie


def test_the_login_cookie_is_valid_for_the_api(deploy_config, loopback_gate):
    deploy_config(backend={'password': PASSWORD})

    with TestClient(create_app()) as client:
        client.post('/api/auth/login', json={'pwd': PASSWORD})
        issued = client.cookies[COOKIE]

    assert JWT_MANAGER.validate_token(issued) == ''
    assert decode(issued)['sub'] == digest()


def test_login_with_a_wrong_password_is_401_and_counted(deploy_config, loopback_gate):
    deploy_config(backend={'password': PASSWORD})

    with TestClient(create_app()) as client:
        response = client.post('/api/auth/login', json={'pwd': 'wrong-password'})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {'err': 'FAIL2BAN_LOGIN_FAILED', 'data': {'remain': 4}}


def test_login_without_a_configured_password_is_refused_by_rule_a(
    deploy_config, loopback_gate
):
    deploy_config()

    with TestClient(create_app()) as client:
        response = client.post('/api/auth/login', json={'pwd': PASSWORD})

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {'err': 'DEPLOY_PASSWORD_NOT_SET'}


def test_renew_issues_a_jwt_to_the_local_app(deploy_config, loopback_gate):
    deploy_config(backend={'password': PASSWORD})

    with TestClient(create_app()) as client:
        response = client.get('/api/auth/renew', headers={'X-OAS-Token': TEST_TOKEN})

    assert response.status_code == status.HTTP_200_OK
    assert f'{COOKIE}=' in response.headers['set-cookie']


def test_renew_issues_a_jwt_without_a_password_through_the_local_app(
    deploy_config, loopback_gate
):
    deploy_config()

    with TestClient(create_app()) as client:
        response = client.get('/api/auth/renew', headers={'X-OAS-Token': TEST_TOKEN})

    assert response.status_code == status.HTTP_200_OK
    assert f'{COOKIE}=' in response.headers['set-cookie']


def test_renew_without_a_token_and_without_a_password_is_refused_by_rule_a(
    deploy_config, loopback_gate
):
    deploy_config()

    with TestClient(create_app()) as client:
        response = client.get('/api/auth/renew')

    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert response.json() == {'err': 'DEPLOY_PASSWORD_NOT_SET'}


def test_renew_refreshes_the_cookie_of_a_stale_jwt(deploy_config, loopback_gate):
    deploy_config(backend={'password': PASSWORD})
    stale = make_token(iat=int(time.time()) - 3601)

    with TestClient(create_app()) as client:
        response = client.get('/api/auth/renew', cookies={COOKIE: stale})

    assert response.status_code == status.HTTP_200_OK
    assert f'{COOKIE}=' in response.headers['set-cookie']


def test_renew_with_an_invalid_jwt_is_401(deploy_config, loopback_gate):
    deploy_config(backend={'password': PASSWORD})

    with TestClient(create_app()) as client:
        response = client.get('/api/auth/renew', cookies={COOKIE: 'not-a-jwt'})

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {'err': 'AUTH_TOKEN_INVALID'}
    assert response.headers['www-authenticate'] == 'Bearer'
