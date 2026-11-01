import hashlib
import hmac
import time
from typing import Annotated

import anyio
import jwt
from fastapi import APIRouter, Cookie, Depends, Request, Response
from pydantic import BaseModel
from starlette import status

from oas.backend.auth.errors import HTTPExceptionJson
from oas.backend.auth.fail2ban import Fail2Ban
from oas.backend.mpipe.token_backend import token_table
from oas.config.table.key import KeyTable
from oas.deploy.settings.runtime import SettingsRuntime
from oas.ext.cache import cached_property

# Name of the cookie carrying the login JWT: the single source of truth for
# the auth router, the gate middleware and the ws handshake, and a contract
# of the Flutter client (its http client stores it and its ws client sends
# it on the handshake).
LOGIN_COOKIE = 'oas_token'


class JwtManager:
    def __init__(self):
        self.algorithm = 'HS256'
        # expire after 168 hours (7 days)
        self.expire_hours = 168
        # renew tokens that has issued at 1 hour ago
        self.renew_hours = 1

    @property
    def pwd(self) -> str:
        """
        The web ui password from the deploy settings (backend.password),
        as configured, so it may be weak (see auth.password for the
        rule). Empty string means no password is configured; an empty or
        weak password is treated as unset by the
        DeploymentGateMiddleware: every web access is refused except
        requests carrying a valid local token.

        Not cached, unlike Alasio (whose JwtManager caches it and
        therefore requires a backend restart for a password change to
        take effect): SettingsRuntime re-reads and re-validates the
        deploy settings on every access, so a password change applies to
        the next request. The cost is one file read plus one validation
        per access, which is the trade the settings runtime is built
        around.
        """
        return SettingsRuntime().data.backend.password or ''

    @cached_property
    def secret(self):
        """
        Returns:
            bytes:
        """
        return KeyTable('gui').jwt_secret

    @property
    def _sub(self):
        """
        JWT subject: never the plaintext password (the payload is base64
        readable, e.g. in DevTools). '' when no password is configured,
        otherwise a versioned sha256 digest of the password.

        Derives from the live `pwd`, so it follows the same
        no-restart-to-apply semantics.

        Returns:
            str:
        """
        pwd = self.pwd
        if not pwd:
            return ''
        return 'v1:' + hashlib.sha256(pwd.encode()).hexdigest()

    def create(self):
        """
        Returns:
            str:
        """
        # cache secret first
        secret = self.secret
        # create
        now = int(time.time())
        exp = now + 3600 * self.expire_hours
        data = {'sub': self._sub, 'iat': now, 'exp': exp}
        token = jwt.encode(data, secret, algorithm=self.algorithm)
        return token

    def validate_pwd(self, pwd):
        """
        Args:
            pwd (str):

        Returns:
            str: New token

        Raises:
            jwt.PyJWTError: If password incorrect
        """
        # constant-time comparison to avoid a timing side channel
        if not hmac.compare_digest(pwd, self.pwd):
            raise jwt.PyJWTError('Password incorrect')
        return self.create()

    def validate_token(self, token):
        """
        Args:
            token (str):

        Returns:
            str: The renewed token, or '' to keep using current token
                if no password and no token, create new token

        Raises:
            jwt.PyJWTError: If token invalid
        """
        if not token and not self.pwd:
            return self.create()

        # cache secret first
        secret = self.secret
        # may raise jwt.PyJWTError
        data = jwt.decode(token, secret, algorithms=self.algorithm)
        try:
            data['exp']
        except KeyError:
            raise jwt.PyJWTError('Missing exp') from None
        try:
            iat = data['iat']
        except KeyError:
            raise jwt.PyJWTError('Missing iat') from None
        try:
            sub = data['sub']
        except KeyError:
            raise jwt.PyJWTError('Missing sub') from None

        # check password
        if sub != self._sub:
            raise jwt.PyJWTError('Password incorrect')

        # renew token
        now = time.time()
        if now - iat > 3600 * self.renew_hours:
            return self.create()
        else:
            return ''


JWT_MANAGER = JwtManager()

# FastAPI router: Alasio mounts the starapi 'auth' router under /api,
# OAS includes this one with the same /api prefix
router = APIRouter(prefix='/auth')


class LoginRequest(BaseModel):
    pwd: str = ''


def _secure_cookie(request: Request) -> bool:
    """
    Cookie secure flag formula: secure = (https or loopback).

    secure is a browser behavior constraint only (the browser refuses to
    store a Secure cookie sent over a plaintext non-loopback origin); it
    is not a security mechanism, the local app layer is the real defense.
    Remote plaintext http logins need secure=False to be usable.

    Args:
        request (Request):

    Returns:
        bool: True when the request came over https or from a loopback host
    """
    if request.url.scheme == 'https':
        return True
    host = request.url.hostname or ''
    return host in ('127.0.0.1', '::1', 'localhost')


@router.post('/login')
async def auth_login(
    req: Request,
    request: LoginRequest,
    response: Response,
    fail2ban: Annotated[Fail2Ban, Depends(Fail2Ban('/login'))],
):
    fail2ban.check_ban()
    try:
        new = JWT_MANAGER.validate_pwd(request.pwd)
    except jwt.PyJWTError:
        # failure delay injection: slow single-point brute force down to
        # ~2 attempts/s, the async sleep does not block other requests
        await anyio.sleep(0.5)
        raise fail2ban.record_failure()

    # success
    fail2ban.record_success()
    response.set_cookie(
        key=LOGIN_COOKIE,
        value=new,
        max_age=JWT_MANAGER.expire_hours * 3600,
        httponly=True,
        samesite='strict',
        secure=_secure_cookie(req),
    )


@router.get('/renew')
async def auth_renew(
    request: Request,
    response: Response,
    token: Annotated[str, Cookie(alias=LOGIN_COOKIE)] = '',
):
    # local Flutter exemption: only the local app's network layer can supply
    # a token present in the backend token table (X-OAS-Token is
    # injected by the local app's network layer and never enters the page JS;
    # the Flutter client sets it in its own http client). A matching
    # token means the request necessarily comes from this machine, so the
    # password check is skipped entirely (login exists to defend remote
    # access, not to gate the local client). A stale/damaged JWT cookie
    # is simply overwritten by the freshly issued one.
    if token_table.verify_header(request):
        new = JWT_MANAGER.create()
    else:
        # Without a configured password a JWT is only ever issued through
        # the local Flutter exemption above (no password -> only the local app
        # network layer may authenticate). The no-password auto-issue
        # inside validate_token serves the login layer (ws handshake /
        # gate middleware) and must not mint tokens on this endpoint.
        if not JWT_MANAGER.pwd:
            raise HTTPExceptionJson(
                status.HTTP_401_UNAUTHORIZED,
                err='AUTH_TOKEN_INVALID',
                headers={'WWW-Authenticate': 'Bearer'},
            ) from None
        try:
            new = JWT_MANAGER.validate_token(token)
        except jwt.PyJWTError:
            raise HTTPExceptionJson(
                status.HTTP_401_UNAUTHORIZED,
                err='AUTH_TOKEN_INVALID',
                headers={'WWW-Authenticate': 'Bearer'},
            ) from None

    # success
    if new:
        response.set_cookie(
            key=LOGIN_COOKIE,
            value=new,
            max_age=JWT_MANAGER.expire_hours * 3600,
            httponly=True,
            samesite='strict',
            secure=_secure_cookie(request),
        )
