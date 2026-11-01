"""
The JSON error contract of the auth layer and the deployment gate.

Ported from Alasio's ``alasio/ext/starapi/param.py``: the two pieces
that are contract rather than framework glue (Alasio's starapi request /
response injectors are replaced by FastAPI's own ``Depends``, ``Cookie``
and ``Response.set_cookie``, but the error body shape is what the
frontend translates and must not change).
"""

from typing import Any, Mapping

import msgspec
from starlette.exceptions import HTTPException


def error_detail(err: str, data: Any = None) -> bytes:
    """
    Build the json error detail: {"err": ..., "data": ...}

    `err` is the error key, e.g. FAIL2BAN_TOO_MANY_REQUEST, the
    frontend translates the key to a localized message. `data` holds
    extra error data and is omitted from the detail when empty. Shared
    by HTTPExceptionJson and middlewares that build the response
    themselves (the gate middleware cannot raise HTTPException).

    Args:
        err (str): Error key for frontend translation
        data (Any, optional): Extra error data. Defaults to None,
            omitted from the detail when empty.

    Returns:
        bytes: The json-encoded detail
    """
    detail = {'err': err}
    if data:
        detail['data'] = data
    return msgspec.json.encode(detail)


class HTTPExceptionJson(HTTPException):
    """
    HTTPException with a json detail: {"err": ..., "data": ...}

    The detail is bytes, so the exception carries a pre-encoded body:
    the app registers a handler for this exception that renders those
    bytes with the json media type (Alasio leaned on starlette's
    PlainTextResponse falling through for a bytes detail, which sends
    the json body with a text/plain content type).
    """

    def __init__(
        self,
        status_code: int,
        err: str,
        data: Any = None,
        headers: Mapping[str, str] | None = None,
    ):
        """
        Args:
            status_code (int): HTTP status code
            err (str): Error key for frontend translation
            data (Any, optional): Extra error data. Defaults to None,
                omitted from the detail when empty.
            headers (Mapping[str, str], optional): Response headers.
        """
        super().__init__(status_code, detail=error_detail(err, data), headers=headers)
