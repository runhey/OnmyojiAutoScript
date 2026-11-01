import http.cookies
import ipaddress
import re

import jwt
from starlette import status
from starlette.datastructures import URL
from starlette.responses import RedirectResponse, Response

from oas.backend.auth.errors import error_detail
from oas.backend.auth.password import is_weak_password
from oas.backend.mpipe.token_backend import token_table
from oas.deploy.settings.runtime import SettingsRuntime
from oas.ext.cache import cached_property

# Rule C: when SSL is configured, plaintext schemes are upgraded to
# their TLS counterparts and never reach the business logic.
_REDIRECT_SCHEMES = {'http': 'https', 'ws': 'wss'}

# HSTS value injected into https responses. One year, no
# includeSubDomains (subdomains may host non-https services).
_HSTS_VALUE = b'max-age=31536000'

# A host header the redirect may use: a reg-name or a bracketed ipv6 address,
# with an optional port. The value becomes the Location of the response, so it
# must not carry a path, a userinfo or a unicode host (a browser would
# punycode the last one), see the reg-name of RFC 3986
_HOST_RE = re.compile(r'^(\[[0-9A-Fa-f:.]+\]|[A-Za-z0-9._-]+)(:[0-9]{1,5})?$')

# Default port of a scheme, the port of a server address on it is left out of
# the authority, like the url of the scope leaves it out
_DEFAULT_PORTS = {'http': 80, 'ws': 80, 'https': 443, 'wss': 443}

# LAN source whitelist (rule B). Explicit network objects instead of the
# ipaddress `is_private` / `is_ula` convenience flags: their exact
# coverage differs across python versions (is_ula only exists on 3.9+,
# IPv6 is_private changed meaning), the explicit list is version-proof.
_LAN_NETS = [
    # RFC1918 private segments
    ipaddress.ip_network('10.0.0.0/8'),
    ipaddress.ip_network('172.16.0.0/12'),
    ipaddress.ip_network('192.168.0.0/16'),
    # link-local
    ipaddress.ip_network('169.254.0.0/16'),
    ipaddress.ip_network('fe80::/10'),
    # unique local addresses (ULA)
    ipaddress.ip_network('fc00::/7'),
]

# loopback host names accepted by the source check
_LOOPBACK_HOSTS = ('127.0.0.1', '::1', 'localhost')


def _is_lan_source(host):
    """
    Check whether a client source belongs to the trusted lan set:
    loopback + RFC1918 + link-local + ULA. There is no configurable
    exception whitelist: the set is fixed.

    Args:
        host (str): The TCP peer address (request.client.host)

    Returns:
        bool: True when the source is allowed in lan mode
    """
    if host in _LOOPBACK_HOSTS:
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        # not an ip address (e.g. a hostname), refuse to be safe
        return False
    if ip.is_loopback:
        return True
    for net in _LAN_NETS:
        if ip in net:
            return True
    return False


def _server_netloc(scope):
    """
    The authority of the redirect target built from the server address.

    Args:
        scope (Scope):

    Returns:
        str | None: "host", "host:port" or "[ipv6]:port", None when the scope
            carries no server address
    """
    server = scope.get('server')
    if not server:
        return None
    host, port = server
    if ':' in host and not host.startswith('['):
        # a bare ipv6 address, an url authority needs the brackets, starlette
        # only brackets it since 1.7.0
        host = f'[{host}]'
    if port == _DEFAULT_PORTS.get(scope['scheme'], 80):
        return host
    return f'{host}:{port}'


def _host_header_netloc(host):
    """
    The authority of a host header, None when the value is not an authority.

    Args:
        host (str): The decoded value of the host header

    Returns:
        str | None: "host[:port]" or "[ipv6][:port]", None when the value
            carries anything else: a path, a userinfo, a query, a unicode host
            or a port out of range
    """
    match = _HOST_RE.match(host)
    if not match:
        return None
    port = match.group(2)
    if port and int(port[1:]) > 65535:
        return None
    return host


def _request_netloc(scope):
    """
    The authority of the redirect target: the host header when it is an
    authority, the server address otherwise.

    A host header that is not an authority is not reflected into the Location
    of the redirect: it is dropped, like starlette 1.0.1+ drops it (0.44.0
    would reflect the raw value).

    Args:
        scope (Scope):

    Returns:
        str | None: The authority, None when neither the host header nor the
            server address gives one
    """
    for key, value in scope.get('headers') or ():
        if key == b'host':
            # the first host header decides
            return _host_header_netloc(value.decode('latin-1')) or _server_netloc(scope)
    return _server_netloc(scope)


class DeploymentGateMiddleware:
    """
    Global admission + login middleware covering both http and
    websocket scopes.

    The middleware merges four layers that must always run together,
    in this fixed order (they must never be split or reordered):

    0. Rule C (SSL enforcement): when SSL is configured (public mode),
       every plaintext connection (http/ws) is upgraded to https/wss
       with a redirect and never reaches the business logic. It runs
       before everything else, so no rule below can ever serve
       business over plaintext. The TCP layer already rejects plaintext
       (uvicorn serves the port TLS-only when ssl is configured);
       this rule is the application-layer enforcement for any plaintext
       that does reach the app, and the HSTS header it injects into
       https responses makes the browser upgrade http itself after the
       first https visit.

    1. Rule A (no usable password → refuse all web access): when the
       password is empty, or is set but fails the strength rule, only
       requests carrying a valid local token (X-OAS-Token
       verified against the backend token table) pass; all other
       business access (/api/*, /api/ws, /api/preview) → 403, with the
       error key telling the login page whether a password is missing
       or the configured one is too weak. Static resources (non-/api
       prefix) pass so the config guidance page renders.
    2. Rule B (lan mode refuses public sources): in lan mode business
       access is source-checked with `ipaddress`: loopback, RFC1918,
       link-local and ULA pass; everything else (including CGNAT
       100.64/10 and public IPv6) → 403. The lan set is fixed, there is
       no configurable exception whitelist. public mode does not check
       sources.
    3. Login layer (JWT cookie): /api http routes require a valid JWT
       in the login cookie (LOGIN_COOKIE) → 401, except the endpoints that
       perform the authentication themselves (/api/auth/login,
       /api/auth/renew). Websocket scopes are NOT login-gated here: the
       handshake validates the JWT inside serve() so it can close(4001)
       after accept (a refused handshake only surfaces as 1006 to the
       browser, the frontend cannot read the close code).

    The order matters: rule C runs first, then rule A before the login
    layer, so without a password the rejection is a 403 from rule A
    (never a 401), and the login layer's no-password leniency
    (validate_token issues a fresh token when no password is
    configured) is only reachable behind rule A — the merged middleware
    makes this ordering structural instead of depending on
    add_middleware order.

    Mode detection: both backend.ssl_cert and backend.ssl_key configured
    → public; otherwise → lan. The two modes behave identically except
    SSL.

    Relationship between the rules: rule A only trusts the local token
    (source-independent → an XFF-forged 127.0.0.1 carries no privilege,
    a reverse proxy disguising the source gains nothing); rule B only
    trusts the source. They stack independently.

    Boundaries: a local TCP forwarder (frp / ngrok / unencrypted reverse
    proxy) presents a loopback source and bypasses rule B → the user is
    actively exposing the service on their own machine, risk is theirs;
    router NAT port forwarding presents a public source and is rejected
    in lan mode (the difference from frp is whether the forwarding
    happens on this machine); CGNAT users are rejected in lan mode →
    configure SSL for real remote access.
    """

    # endpoints that perform the authentication themselves
    EXEMPT = {'/api/auth/login', '/api/auth/renew'}

    def __init__(self, app):
        """
        Args:
            app (ASGIApp):
        """
        self.app = app

    @staticmethod
    def _deploy_backend():
        return SettingsRuntime().data.backend

    @property
    def _is_public(self):
        """
        Returns:
            bool: True when SSL is configured (public mode)

        Not cached, unlike Alasio: SettingsRuntime re-reads the deploy
        settings on every access, so configuring (or clearing) the SSL
        pair applies to the next request instead of requiring a backend
        restart.
        """
        backend = self._deploy_backend()
        return bool(backend.ssl_cert and backend.ssl_key)

    @property
    def _password_state(self):
        """
        Returns:
            str: 'strong' when a usable password is configured, 'weak'
                when one is configured but fails the strength rule (it
                is treated as unset: remote access is refused, only the
                local token passes), 'none' when none is configured

        Not cached, unlike Alasio: it mirrors JwtManager.pwd, which is
        itself live, so a password change applies to the next request.
        """
        from oas.backend.auth.auth import JWT_MANAGER

        # no local ever holds the plaintext: the logger renders tracebacks
        # with show_locals=True, a frame of this middleware included
        if not JWT_MANAGER.pwd:
            return 'none'
        if is_weak_password(JWT_MANAGER.pwd):
            return 'weak'
        return 'strong'

    def _has_local_token(self, scope):
        """
        Args:
            scope (Scope):

        Returns:
            bool: True when the request carries a valid local token
        """
        return token_table.verify_header(scope)

    def _client_host(self, scope):
        """
        Args:
            scope (Scope):

        Returns:
            str: The TCP peer address, or '' when unavailable
        """
        client = scope.get('client')
        if client:
            host = client[0]
            return host if isinstance(host, str) else str(host)
        return ''

    def _is_plaintext(self, scope):
        """
        Args:
            scope (Scope):

        Returns:
            bool: True when the connection arrived without TLS
        """
        return scope.get('scheme') in _REDIRECT_SCHEMES

    def _redirect_url(self, scope):
        """
        Build the https/wss url that mirrors the current plaintext
        request, keeping the host header (with port), path and query.

        The authority is decided here: the host header when it is a valid
        host, the server address otherwise, and a bare ipv6 address of the
        server is bracketed. starlette only brackets it since 1.7.0, and
        0.44.0 keeps the raw host header, so the url is built from a scope
        carrying the authority above: the path and the query are still the
        ones of the request, escaped like starlette escapes them.

        Args:
            scope (Scope):

        Returns:
            str | None: The redirect target, or None when there is nothing to
                redirect to: neither a usable host header nor a server address
        """
        netloc = _request_netloc(scope)
        if not netloc:
            return None
        url = URL(
            scope={
                'type': scope['type'],
                'scheme': scope['scheme'],
                'path': scope.get('path', '/'),
                'query_string': scope.get('query_string', b''),
                'headers': [(b'host', netloc.encode('latin-1'))],
            }
        )
        return str(url.replace(scheme=_REDIRECT_SCHEMES[url.scheme]))

    async def _redirect_plaintext(self, scope, receive, send):
        """
        Upgrade a plaintext connection in public mode: 308 for http
        (permanent, cached by the browser), 307 for websocket (the
        browser re-handshakes over wss after the redirect). When the
        redirect target cannot be determined the connection is refused
        with 400 instead.

        Args:
            scope (Scope):
            receive (Receive):
            send (Send):
        """
        url = self._redirect_url(scope)
        if url is None:
            response = Response(status_code=status.HTTP_400_BAD_REQUEST)
            await response(scope, receive, send)
            return
        if scope['type'] == 'http':
            status_code = status.HTTP_308_PERMANENT_REDIRECT
        else:
            status_code = status.HTTP_307_TEMPORARY_REDIRECT
        response = RedirectResponse(url, status_code=status_code)
        await response(scope, receive, send)

    @staticmethod
    def _with_hsts(send):
        """
        Wrap `send` to inject the Strict-Transport-Security header into
        every http response (only reachable over https, see __call__).

        Args:
            send (Send):

        Returns:
            Send: The wrapped send callable
        """

        async def wrapped(message):
            if message['type'] == 'http.response.start':
                message = dict(message)
                headers = list(message.get('headers') or [])
                if not any(
                    name.lower() == b'strict-transport-security' for name, _ in headers
                ):
                    headers.append((b'strict-transport-security', _HSTS_VALUE))
                message['headers'] = headers
            await send(message)

        return wrapped

    def _check(self, scope):
        """
        Apply rule A then rule B.

        Args:
            scope (Scope):

        Returns:
            tuple[str, dict]: (err key, data) when rejected, or
                ('', {}) when allowed
        """
        # Rule A: no usable password → only local token passes
        state = self._password_state
        if state != 'strong' and not self._has_local_token(scope):
            if state == 'weak':
                # the error key alone says why: no extra data is needed
                return 'DEPLOY_PASSWORD_TOO_WEAK', {}
            return 'DEPLOY_PASSWORD_NOT_SET', {}
        # Rule B: lan mode → source check
        if not self._is_public:
            host = self._client_host(scope)
            if not _is_lan_source(host):
                # never expose the rejected source to the client
                return 'DEPLOY_CERT_NOT_SET', {}
        return '', {}

    def _read_cookie(self, scope):
        """
        Read the login JWT cookie (LOGIN_COOKIE) from the raw scope headers.

        Args:
            scope (Scope):

        Returns:
            str: The cookie value, or '' when absent / unparsable
        """
        from oas.backend.auth.auth import LOGIN_COOKIE

        for name, value in scope.get('headers', []):
            if name != b'cookie':
                continue
            cookie = http.cookies.SimpleCookie()
            try:
                cookie.load(value.decode('latin-1'))
            except http.cookies.CookieError:
                return ''
            morsel = cookie.get(LOGIN_COOKIE)
            if morsel is not None:
                return morsel.value
        return ''

    def _check_login(self, scope):
        """
        Validate the login layer (JWT cookie) for an http scope.

        Args:
            scope (Scope):

        Returns:
            bool: True when the JWT cookie is valid
        """
        from oas.backend.auth.auth import JWT_MANAGER

        token = self._read_cookie(scope)
        try:
            JWT_MANAGER.validate_token(token)
        except jwt.PyJWTError:
            return False
        return True

    async def _reject_http(self, scope, receive, send, err, data=None):
        """
        Send a 403 json response for an http scope.

        Args:
            scope (Scope):
            receive (Receive):
            send (Send):
            err (str): Error key for frontend translation
            data (dict, optional): Extra error data
        """
        response = Response(
            error_detail(err, data),
            status_code=status.HTTP_403_FORBIDDEN,
            media_type='application/json',
        )
        await response(scope, receive, send)

    async def _reject_ws(self, scope, receive, send, message):
        """
        Reject a websocket handshake. The browser only surfaces 1006 for
        a refused handshake; the frontend reconnect loop stops after its
        attempts are exhausted, so a persistently rejected ws settles
        into the login / guidance page instead of looping forever.

        Args:
            scope (Scope):
            receive (Receive):
            send (Send):
            message (str):
        """
        await send({'type': 'websocket.close', 'code': 4001})

    async def __call__(self, scope, receive, send):
        """
        Args:
            scope (Scope):
            receive (Receive):
            send (Send):
        """
        scope_type = scope['type']
        if scope_type not in ('http', 'websocket'):
            await self.app(scope, receive, send)
            return

        # Rule C (SSL enforcement): public mode never serves plaintext.
        # Plaintext connections are upgraded to https/wss, secure http
        # responses get the HSTS header so the browser upgrades http
        # itself on subsequent visits. Only http scopes are wrapped:
        # HSTS is carried by ordinary http responses, a websocket
        # handshake (101) has no HSTS semantics, so ws scopes pass
        # through unwrapped.
        if self._is_public:
            if self._is_plaintext(scope):
                await self._redirect_plaintext(scope, receive, send)
                return
            if scope_type == 'http':
                send = self._with_hsts(send)

        path = scope.get('path', '')
        if not path.startswith('/api'):
            # static resources and the guidance page pass through
            await self.app(scope, receive, send)
            return

        # Rules A + B (admission) first: 403 / 4001
        err, data = self._check(scope)
        if err:
            if scope_type == 'http':
                await self._reject_http(scope, receive, send, err, data)
            else:
                await self._reject_ws(scope, receive, send, err)
            return

        # Login layer (http only; the ws handshake validates inside
        # serve() so it can close(4001) after accept)
        if scope_type == 'http' and path not in self.EXEMPT:
            if not self._check_login(scope):
                response = Response(
                    error_detail('AUTH_TOKEN_INVALID'),
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    headers={'WWW-Authenticate': 'Bearer'},
                    media_type='application/json',
                )
                await response(scope, receive, send)
                return

        await self.app(scope, receive, send)
