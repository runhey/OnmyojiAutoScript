import jwt
from starlette import status
from starlette.requests import Request

from oas.backend.auth.errors import HTTPExceptionJson
from oas.backend.mpipe.token_backend import token_table


async def require_local_flutter(request: Request):
    """
    Local-layer dependency: the request must carry a valid X-OAS-Token
    (injected by the local app's network layer, verified against the
    backend token table). Orthogonal to require_login: this checks the
    local token only, not the JWT.

    Args:
        request (Request):

    Raises:
        HTTPExceptionJson: 403 when the token is missing or invalid
    """
    if not token_table.verify_header(request):
        raise HTTPExceptionJson(
            status_code=status.HTTP_403_FORBIDDEN,
            err='AUTH_LOCAL_FLUTTER_ONLY',
        )


async def require_login(request: Request):
    """
    Login-layer dependency: the request must carry a valid JWT in the
    login cookie (LOGIN_COOKIE). Orthogonal to require_local_flutter: this
    checks the JWT only, not the local token.

    Args:
        request (Request):

    Raises:
        HTTPExceptionJson: 401 when the JWT cookie is missing or invalid
    """
    from oas.backend.auth.auth import JWT_MANAGER, LOGIN_COOKIE

    token = request.cookies.get(LOGIN_COOKIE, '')
    try:
        JWT_MANAGER.validate_token(token)
    except jwt.PyJWTError:
        raise HTTPExceptionJson(
            status_code=status.HTTP_401_UNAUTHORIZED,
            err='AUTH_TOKEN_INVALID',
            headers={'WWW-Authenticate': 'Bearer'},
        ) from None
