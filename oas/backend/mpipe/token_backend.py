import time

from oas.backend.mpipe.mpipe_backend import mpipe_backend

# Header carrying the electron token on http/ws requests (injected by the
# Electron main process webRequest). Centralized here so callers never
# need to spell out the header name.
ELECTRON_TOKEN_HEADER = 'X-Alasio-Token'


def read_token_header(obj):
    """
    Extract the electron token header from a starlette Request / WebSocket
    (`.headers` mapping, case-insensitive) or a raw ASGI scope dict
    (headers as a lowercase-bytes pair list).

    Args:
        obj (Request | WebSocket | dict): starlette request-like object,
            or a raw ASGI scope dict

    Returns:
        str: The header value, or '' when absent
    """
    if isinstance(obj, dict):
        # raw ASGI scope: headers are a list of (bytes, bytes), names lowercase
        for name, value in obj.get('headers', []):
            if name == b'x-alasio-token':
                return value.decode('latin-1')
        return ''
    headers = getattr(obj, 'headers', None)
    if headers is None:
        return ''
    return headers.get(ELECTRON_TOKEN_HEADER, '')


class BackendTokenTable:
    """
    Backend-side token table. Global singleton in the backend process.

    Lock-free by design:
      1. single writer: seed_from_supervisor must complete before the
         mpipe_recv_loop thread starts; afterwards only handle_token
         (recv thread) writes;
      2. readers only do `token in self._tokens`, never iterate;
      3. CPython dict setitem / contains / del are atomic under the GIL
         (implementation behavior, not language spec).
    """

    def __init__(self, max_tokens=2):
        """
        Args:
            max_tokens (int): Window size, the number of tokens kept.
                Defaults to 2.
        """
        self._tokens: 'dict[str, float]' = {}
        self._max_tokens = max_tokens

    def _add(self, token):
        """
        Add a token with a timestamp, evicting the oldest entry when the
        table exceeds max_tokens (add-then-remove: the freshly added key
        is excluded from eviction so a tied timestamp can never evict the
        new token right after enqueue).

        Args:
            token (str):
        """
        self._tokens[token] = time.time()
        if len(self._tokens) > self._max_tokens:
            oldest = min((k for k in self._tokens if k != token), key=self._tokens.get)
            del self._tokens[oldest]

    def seed_from_supervisor(self, tokens):
        """
        Backend startup: seed the table from the spawn args. Must complete
        before hypercorn serve and before the recv thread starts
        (single-writer constraint).

        Args:
            tokens (tuple[str]): Initial token window from the supervisor
        """
        for token in tokens:
            self._add(token)

    def handle_token(self, token):
        """
        Called by mpipe_recv_loop on a token:<token> message: add the
        token and acknowledge it back to the supervisor (through
        MPipeBackend, which owns the backend-side send lock).

        Args:
            token (str): The new token from the supervisor rotation
        """
        self._add(token)
        mpipe_backend.send(b'token_ack:' + token.encode())

    def current(self):
        """
        Latest token in the table (by enqueue time), used to update
        per-connection auth_token after a successful renewal.

        Returns:
            str: The most recent token, or '' if the table is empty
        """
        if not self._tokens:
            return ''
        return max(self._tokens, key=self._tokens.get)

    def verify(self, token):
        """
        Membership check used by require_electron (GIL atomic, lock-free).

        Args:
            token (str):

        Returns:
            bool: True if the token is in the table
        """
        return token in self._tokens

    def verify_header(self, obj):
        """
        Verify the electron token carried by a request: reads the
        ELECTRON_TOKEN_HEADER (the caller does not need to know the
        header name) and checks membership. Accepts a starlette
        Request / WebSocket or a raw ASGI scope dict.

        Args:
            obj (Request | WebSocket | dict): starlette request-like
                object, or a raw ASGI scope dict

        Returns:
            bool: True when the request carries a valid token
        """
        return read_token_header(obj) in self._tokens


token_table = BackendTokenTable()
