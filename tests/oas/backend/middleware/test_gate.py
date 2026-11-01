"""
Tests for DeploymentGateMiddleware (merged admission + login gate).

The middleware is the single web entrance: rule A (no usable password -> only
the local app token passes), rule B (lan mode -> lan sources only), rule C
(public mode -> TLS enforced) and the login layer (JWT cookie) run inside one
middleware in a fixed order. It must never be split or reordered.

The middleware is driven with hand-built ASGI scopes: the peer address, the
scheme and the raw headers are exactly what the rules read, and the test client
cannot produce all of them (it connects from the host name ``testclient``).
"""

import json

import pytest
from starlette import status

from oas.backend.auth.auth import JWT_MANAGER
from oas.backend.auth.errors import error_detail
from oas.backend.middleware.gate import DeploymentGateMiddleware, _request_netloc

pytestmark = pytest.mark.anyio

PASSWORD = 'test-password'
TEST_TOKEN = 'test-local-token'
COOKIE = 'oas_token'
LAN_HOST = '192.168.1.30'
PUBLIC_HOST = '203.0.113.7'
SERVER = ('127.0.0.1', 22288)


class CaptureApp:
    """Records whether the inner app was reached."""

    def __init__(self):
        self.called = False

    async def __call__(self, scope, receive, send):
        self.called = True
        await send({'type': 'http.response.start', 'status': 200, 'headers': []})
        await send({'type': 'http.response.body', 'body': b''})


def make_scope(
    scope_type,
    path='/api/test',
    host=LAN_HOST,
    headers=None,
    scheme='http',
    query_string=b'',
    server=SERVER,
):
    """
    Build a minimal ASGI scope.

    Args:
        scope_type (str): 'http', 'websocket' or 'lifespan'
        path (str):
        host (str): The TCP peer address
        headers (list): Raw header pairs
        scheme (str): 'http', 'https', 'ws' or 'wss'
        query_string (bytes):
        server (tuple | None): The ASGI server address

    Returns:
        Scope:
    """
    return {
        'type': scope_type,
        'method': 'GET',
        'path': path,
        'headers': headers or [],
        'client': (host, 12345),
        'query_string': query_string,
        'scheme': scheme,
        'server': server,
    }


def make_http_scope(**kwargs):
    return make_scope('http', **kwargs)


def make_ws_scope(**kwargs):
    return make_scope('websocket', **kwargs)


async def drive(scope, app=None):
    """
    Run the middleware against a scope and collect the sent messages.

    Args:
        scope (Scope):
        app (CaptureApp, optional): The inner app. Defaults to a fresh one.

    Returns:
        tuple: (CaptureApp, list of sent messages)
    """
    app = app or CaptureApp()
    gate = DeploymentGateMiddleware(app)
    sent = []

    async def send(message):
        sent.append(message)

    async def receive():
        return {'type': 'http.request', 'body': b'', 'more_body': False}

    await gate(scope, receive, send)
    return app, sent


def status_of(sent):
    """
    Args:
        sent (list): Messages sent by the middleware

    Returns:
        int: The http status code, 0 when no response was started
    """
    for message in sent:
        if message['type'] == 'http.response.start':
            return message['status']
    return 0


def headers_of(sent):
    """
    Args:
        sent (list): Messages sent by the middleware

    Returns:
        dict: The response headers, lower cased
    """
    for message in sent:
        if message['type'] == 'http.response.start':
            return {
                name.decode().lower(): value.decode()
                for name, value in message.get('headers') or []
            }
    return {}


def body_of(sent):
    """
    Args:
        sent (list): Messages sent by the middleware

    Returns:
        bytes: The response body
    """
    for message in sent:
        if message['type'] == 'http.response.body':
            return message['body']
    return b''


def error_of(sent):
    """
    Args:
        sent (list): Messages sent by the middleware

    Returns:
        dict: The decoded {"err": ..., "data": ...} body
    """
    return json.loads(body_of(sent))


def cookie_header(token):
    """
    Args:
        token (str): The JWT to put in the oas_token cookie

    Returns:
        tuple: The raw cookie header pair
    """
    return (b'cookie', f'{COOKIE}={token}'.encode())


def local_token_header():
    """
    Returns:
        tuple: The raw X-OAS-Token header pair of the test window
    """
    return (b'x-oas-token', TEST_TOKEN.encode())


def strong_password(deploy_config):
    """
    Args:
        deploy_config (callable): The isolated settings writer

    Returns:
        str: The JWT of the configured password, ready for a cookie
    """
    deploy_config(backend={'password': PASSWORD})
    return JWT_MANAGER.create()


async def test_rule_a_refuses_every_api_access_without_a_password(deploy_config):
    deploy_config()

    app, sent = await drive(make_http_scope())

    assert app.called is False
    assert status_of(sent) == status.HTTP_403_FORBIDDEN
    assert error_of(sent) == {'err': 'DEPLOY_PASSWORD_NOT_SET'}


async def test_rule_a_refuses_a_password_that_fails_the_strength_rule(deploy_config):
    deploy_config(backend={'password': 'short'})

    app, sent = await drive(make_http_scope())

    assert app.called is False
    assert status_of(sent) == status.HTTP_403_FORBIDDEN
    assert error_of(sent) == {'err': 'DEPLOY_PASSWORD_TOO_WEAK'}


async def test_rule_a_admits_the_local_app_token(deploy_config):
    deploy_config()

    app, sent = await drive(make_http_scope(headers=[local_token_header()]))

    assert app.called is True
    assert status_of(sent) == status.HTTP_200_OK


async def test_rule_a_refuses_a_weak_password_even_with_many_api_paths(deploy_config):
    deploy_config(backend={'password': '1234'})

    for path in ('/api/test', '/api/ws', '/api/auth/login'):
        app, sent = await drive(make_http_scope(path=path))
        assert app.called is False
        assert error_of(sent) == {'err': 'DEPLOY_PASSWORD_TOO_WEAK'}


async def test_rule_b_refuses_a_public_source_in_lan_mode(deploy_config):
    cookie = strong_password(deploy_config)

    app, sent = await drive(
        make_http_scope(host=PUBLIC_HOST, headers=[cookie_header(cookie)])
    )

    assert app.called is False
    assert status_of(sent) == status.HTTP_403_FORBIDDEN
    assert error_of(sent) == {'err': 'DEPLOY_CERT_NOT_SET'}


@pytest.mark.parametrize('host', ['127.0.0.1', '192.168.1.30', '10.1.2.3'])
async def test_rule_b_admits_the_lan_sources(deploy_config, host):
    cookie = strong_password(deploy_config)

    app, sent = await drive(make_http_scope(host=host, headers=[cookie_header(cookie)]))

    assert app.called is True


async def test_the_source_is_not_checked_in_public_mode(deploy_config):
    deploy_config(
        backend={
            'password': PASSWORD,
            'ssl_key': 'server.key',
            'ssl_cert': 'server.crt',
        }
    )
    cookie = JWT_MANAGER.create()

    app, sent = await drive(
        make_http_scope(
            host=PUBLIC_HOST, scheme='https', headers=[cookie_header(cookie)]
        )
    )

    assert app.called is True


async def test_public_mode_redirects_a_plaintext_request(deploy_config):
    deploy_config(backend={'ssl_key': 'server.key', 'ssl_cert': 'server.crt'})

    app, sent = await drive(make_http_scope(path='/api/test'))

    assert app.called is False
    assert status_of(sent) == status.HTTP_308_PERMANENT_REDIRECT
    assert headers_of(sent)['location'] == 'https://127.0.0.1:22288/api/test'


async def test_public_mode_adds_hsts_to_a_secure_response(deploy_config):
    deploy_config(
        backend={
            'password': PASSWORD,
            'ssl_key': 'server.key',
            'ssl_cert': 'server.crt',
        }
    )
    cookie = JWT_MANAGER.create()

    app, sent = await drive(
        make_http_scope(scheme='https', headers=[cookie_header(cookie)])
    )

    assert app.called is True
    assert headers_of(sent)['strict-transport-security'] == 'max-age=31536000'


async def test_lan_mode_adds_no_hsts(deploy_config):
    cookie = strong_password(deploy_config)

    app, sent = await drive(make_http_scope(headers=[cookie_header(cookie)]))

    assert app.called is True
    assert 'strict-transport-security' not in headers_of(sent)


async def test_the_login_layer_refuses_a_missing_cookie(deploy_config):
    strong_password(deploy_config)

    app, sent = await drive(make_http_scope())

    assert app.called is False
    assert status_of(sent) == status.HTTP_401_UNAUTHORIZED
    assert error_of(sent) == {'err': 'AUTH_TOKEN_INVALID'}
    assert headers_of(sent)['www-authenticate'] == 'Bearer'


async def test_the_login_layer_refuses_an_invalid_cookie(deploy_config):
    strong_password(deploy_config)

    app, sent = await drive(make_http_scope(headers=[cookie_header('not-a-jwt')]))

    assert app.called is False
    assert status_of(sent) == status.HTTP_401_UNAUTHORIZED
    assert error_of(sent) == {'err': 'AUTH_TOKEN_INVALID'}


async def test_the_login_layer_admits_a_valid_cookie(deploy_config):
    cookie = strong_password(deploy_config)

    app, sent = await drive(make_http_scope(headers=[cookie_header(cookie)]))

    assert app.called is True


@pytest.mark.parametrize('path', ['/api/auth/login', '/api/auth/renew'])
async def test_the_auth_endpoints_are_exempt_from_the_login_layer(deploy_config, path):
    strong_password(deploy_config)

    app, sent = await drive(make_http_scope(path=path))

    assert app.called is True


async def test_a_non_api_path_passes_without_a_password(deploy_config):
    deploy_config()

    app, sent = await drive(make_http_scope(path='/index.html'))

    assert app.called is True


async def test_a_websocket_is_refused_with_4001(deploy_config):
    deploy_config()

    app, sent = await drive(make_ws_scope())

    assert app.called is False
    assert sent == [{'type': 'websocket.close', 'code': 4001}]


async def test_a_websocket_is_admitted_when_the_rules_pass(deploy_config):
    cookie = strong_password(deploy_config)

    app, sent = await drive(make_ws_scope(headers=[cookie_header(cookie)]))

    assert app.called is True


async def test_a_lifespan_scope_is_not_gated(deploy_config):
    deploy_config()

    app, sent = await drive(make_scope('lifespan', path=''))

    assert app.called is True


def test_request_netloc_prefers_a_valid_host_header():
    scope = make_http_scope(headers=[(b'host', b'example.com:8443')])

    assert _request_netloc(scope) == 'example.com:8443'


def test_request_netloc_falls_back_to_the_server_address():
    # a host header that is not an authority is never reflected into a location
    scope = make_http_scope(headers=[(b'host', b'example.com/evil')])

    assert _request_netloc(scope) == '127.0.0.1:22288'


def test_error_detail_of_the_gate_is_the_frontend_contract():
    assert error_detail('DEPLOY_CERT_NOT_SET') == b'{"err":"DEPLOY_CERT_NOT_SET"}'
