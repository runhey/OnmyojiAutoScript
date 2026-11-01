import secrets
import threading
import time

from fastapi import APIRouter, Depends
from starlette import status

from oas.backend.auth.deps import require_local_flutter, require_login
from oas.backend.auth.errors import HTTPExceptionJson


class RenewalLimitExceeded(Exception):
    """
    Raised by issue() when the code table is at capacity (anti-DoS
    backstop: an XSS script could otherwise flood the table through
    POST /api/ws/renew).
    """


class RenewalCodeManager:
    """
    One-time renewal code manager for ws connection renewal.

    Codes are issued through POST /api/ws/renew (the request must
    carry a valid JWT cookie and a valid X-OAS-Token from the local
    app's network layer) and redeemed through the ws 'auth' message.
    A code is valid for ttl seconds and can be used exactly once; expired
    codes are removed by gc().

    Thread safety: issue (HTTP request threads), redeem (ws task) and gc
    (sync_task_gc thread pool) are concurrent writers, so all operations
    take the lock (unlike BackendTokenTable which has a single writer).
    """

    def __init__(self, ttl=20.0, max_codes=1024, clock=time.monotonic):
        """
        Args:
            ttl (float): Code validity in seconds. Defaults to 20.0.
            max_codes (int): Capacity cap; issue() refuses beyond it.
            clock (callable): Injectable clock for tests. Defaults to time.monotonic.
        """
        self._codes: 'dict[str, float]' = {}  # code -> issued timestamp
        self._ttl = ttl
        self._max_codes = max_codes
        self._clock = clock
        self._lock = threading.Lock()

    def issue(self):
        """
        Issue a new one-time renewal code.

        Returns:
            str: The renewal code

        Raises:
            RenewalLimitExceeded: When the table is at capacity
        """
        with self._lock:
            # lazy cleanup of expired codes before the capacity check
            # (issue is already holding the lock, use the locked variant)
            self._gc_locked()
            if len(self._codes) >= self._max_codes:
                raise RenewalLimitExceeded
            code = secrets.token_hex(32)
            self._codes[code] = self._clock()
            return code

    def redeem(self, code):
        """
        Redeem a code (one-time).

        Args:
            code (str): The renewal code

        Returns:
            bool: True if the code existed and was not expired
        """
        with self._lock:
            try:
                issued = self._codes.pop(code)
            except KeyError:
                return False
            # a code expires only when now - issued > ttl (== ttl is valid)
            if self._clock() - issued > self._ttl:
                return False
            return True

    def gc(self):
        """
        Remove expired codes (thread-safe: takes the lock; the
        sync_task_gc thread pool runs concurrently with issue / redeem
        writers).

        Returns:
            int: Number of codes removed
        """
        with self._lock:
            if not self._codes:
                return 0
            return self._gc_locked()

    def _gc_locked(self):
        """
        Remove expired codes. Caller must hold the lock (issue() calls it
        while already inside the lock; a second acquisition would deadlock
        on the non-reentrant threading.Lock).

        Collects the expired codes first, then deletes: deleting while
        iterating a dict raises RuntimeError even under the lock (same
        thread), and the lock serializes concurrent writers during the
        collection pass.

        Returns:
            int: Number of codes removed
        """
        now = self._clock()
        expired = [
            code for code, issued in self._codes.items() if now - issued > self._ttl
        ]
        for code in expired:
            try:
                del self._codes[code]
            except KeyError:
                # defensive: the lock serializes writers, this cannot happen
                pass
        return len(expired)


renewal_manager = RenewalCodeManager()

# FastAPI router: Alasio mounts the starapi 'ws' router under /api,
# OAS includes this one with the same /api prefix
router = APIRouter(prefix='/ws')


@router.post('/renew')
async def ws_renew(
    _login: None = Depends(require_login),
    _local_flutter: None = Depends(require_local_flutter),
):
    """
    Issue a one-time renewal code R' for the ws 'auth' message.

    Both dependencies are required: require_login proves the user
    is logged in, require_local_flutter proves the request comes from the
    local app's network layer. A remote logged-in user holds a JWT but
    no local token, so they can never obtain R' (otherwise they could
    upgrade their ws connection to the local level).

    Returns:
        dict: {'code': R'}

    Raises:
        HTTPExceptionJson: 401 without a valid JWT (require_login),
            403 without a valid local token (require_local_flutter),
            429 when the code table is at capacity
    """
    try:
        code = renewal_manager.issue()
    except RenewalLimitExceeded:
        raise HTTPExceptionJson(
            status.HTTP_429_TOO_MANY_REQUESTS,
            err='WS_RENEWAL_LIMIT_EXCEEDED',
        ) from None
    return {'code': code}
