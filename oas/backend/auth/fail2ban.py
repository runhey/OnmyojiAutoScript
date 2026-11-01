import time

import anyio
from starlette import status
from starlette.requests import Request

from oas.backend.auth.errors import HTTPExceptionJson
from oas.ext.singleton import SingletonNamed


def get_client_ip(request: Request) -> str:
    """
    Get the TCP peer IP of the request.

    Only request.client.host is trusted: the backend is a direct service
    (the app / browser connect straight to the port, no reverse proxy),
    and the TCP peer address is given by the kernel so it cannot be
    spoofed within a single connection, while X-Forwarded-For /
    X-Real-IP are application headers anyone can forge. Per-IP banning
    would degrade to "shared counting per proxy IP" if a proxy is ever
    introduced.

    Args:
        request (Request):

    Returns:
        str: The peer IP, or '127.0.0.1' when the client is unknown
    """
    client = request.client
    if client is None or client.host is None:
        return '127.0.0.1'
    return client.host


class Fail2BanManager(metaclass=SingletonNamed):
    """Manages IP banning based on failed login attempts"""

    def __init__(self, name):
        """
        Args:
            name (str): name for different fail2ban manager
                name is used for SingletonNamed
        """
        self.name = name
        # fail2ban configuration
        # maximum failed attempts before ban, must > 1
        self.max_attempts = 5
        # ban duration in seconds (10 minutes)
        self.ban_duration = 600
        # failure counting window in seconds (10 minutes)
        self.failure_window = 600

        # storage: {ip: (attempts, first_attempt_time)}
        self.failed_attempts: 'dict[str, tuple[int, float]]' = {}
        # ban storage: {ip: ban_end_time}
        self.banned_ips: 'dict[str, float]' = {}

        # Global failure throttling: last line of defense when per-IP
        # banning is bypassed by a distributed attack (many real IPs).
        # The threshold is far above normal use (a few typos) and far
        # below brute-force throughput; an attacker can deliberately
        # trigger the global cooldown to block everyone's login, but that
        # also stops the attack itself. "Throttling can be used to DoS
        # itself" is an inherent boundary of rate limiting.
        # window: failure timestamps within this many seconds count
        self.global_window = 300
        # more than this many global failures in the window triggers
        self.global_threshold = 100
        # the login endpoint returns 429 for this many seconds
        self.global_cooldown = 60
        # timestamps of recent global failures
        self.global_failures: 'list[float]' = []
        # wall time until which the global cooldown lasts (0 = inactive)
        self.global_cool_until = 0.0

    def global_blocked(self):
        """
        Returns:
            bool: True when the global cooldown is active
        """
        return time.time() < self.global_cool_until

    def record_global_failure(self):
        """
        Record a failure in the global window; activate the cooldown when
        the threshold is exceeded.
        """
        now = time.time()
        self.global_failures.append(now)
        window_start = now - self.global_window
        self.global_failures = [t for t in self.global_failures if t >= window_start]
        if len(self.global_failures) > self.global_threshold:
            self.global_cool_until = now + self.global_cooldown

    async def gc(self):
        """
        Periodically clean up expired data
        """
        while True:
            # cleanup every 5 minutes
            await anyio.sleep(300)
            now = time.time()

            # clean expired ban records
            ip_list = list(self.banned_ips)
            for ip in ip_list:
                try:
                    end_time = self.banned_ips[ip]
                except KeyError:
                    continue
                if now > end_time:
                    try:
                        del self.banned_ips[ip]
                    except KeyError:
                        pass

            # clean expired failure attempt records
            ip_list = list(self.failed_attempts)
            window = now - self.failure_window
            for ip in ip_list:
                try:
                    attempts, first_time = self.failed_attempts[ip]
                except KeyError:
                    continue
                if window > first_time:
                    try:
                        del self.failed_attempts[ip]
                    except KeyError:
                        pass


class Fail2Ban:
    def __init__(self, name):
        """
        Args:
            name (str): Endpoint
        """
        self.name = name
        self.ip: 'str | None' = None

    def check_ban(self):
        """
        Raises:
            HTTPExceptionJson: HTTP_403_FORBIDDEN if IP banned,
                HTTP_429_TOO_MANY_REQUESTS during the global cooldown
        """
        if self.ip is None:
            return
        manager = Fail2BanManager(self.name)

        # global cooldown: block all logins briefly
        if manager.global_blocked():
            raise HTTPExceptionJson(
                status.HTTP_429_TOO_MANY_REQUESTS,
                err='FAIL2BAN_TOO_MANY_REQUEST',
                data={'after': int(manager.global_cool_until - time.time()) or 1},
            )

        # No ban
        if self.ip not in manager.banned_ips:
            return

        try:
            end_time = manager.banned_ips[self.ip]
        except KeyError:
            # No ban, race condition that record is clean up
            return
        now = time.time()
        if now < end_time:
            # still in ban. Note that the ban is NOT extended on access:
            # a fixed duration, expired records are removed by gc().
            # Extending here would let an attacker keep the ban alive
            # forever by visiting once per ban period (login DoS).
            raise HTTPExceptionJson(
                status.HTTP_403_FORBIDDEN,
                err='FAIL2BAN_BANNED',
                data={'after': int(end_time - now) or 1},
            )
        else:
            # unban expired IP
            # ignore KeyError to handle race condition that record is clean up
            try:
                del manager.banned_ips[self.ip]
            except KeyError:
                pass

    def record_failure(self) -> HTTPExceptionJson:
        """
        Record a failed login attempt

        Returns:
            HTTPExceptionJson: HTTP_401_UNAUTHORIZED (login failed) or
                HTTP_403_FORBIDDEN (IP banned)
        """
        # this shouldn't happen
        assert self.ip is not None
        manager = Fail2BanManager(self.name)
        now = time.time()

        # record the failure in the global window and maybe trigger the
        # global cooldown
        manager.record_global_failure()

        # first failure
        if self.ip not in manager.failed_attempts:
            manager.failed_attempts[self.ip] = (1, now)
            return HTTPExceptionJson(
                status.HTTP_401_UNAUTHORIZED,
                err='FAIL2BAN_LOGIN_FAILED',
                data={'remain': manager.max_attempts - 1},
            )

        # within failure window
        attempts, first_time = manager.failed_attempts[self.ip]
        if now - first_time <= manager.failure_window:
            attempts += 1
            if attempts >= manager.max_attempts:
                # ban IP
                manager.banned_ips[self.ip] = now + manager.ban_duration
                try:
                    del manager.failed_attempts[self.ip]
                except KeyError:
                    pass
                return HTTPExceptionJson(
                    status.HTTP_403_FORBIDDEN,
                    err='FAIL2BAN_BANNED',
                    data={'after': manager.ban_duration},
                )
            else:
                # increase attempt count
                manager.failed_attempts[self.ip] = (attempts, first_time)
                return HTTPExceptionJson(
                    status.HTTP_401_UNAUTHORIZED,
                    err='FAIL2BAN_LOGIN_FAILED',
                    data={'remain': manager.max_attempts - attempts},
                )
        else:
            # reset count outside window
            manager.failed_attempts[self.ip] = (1, now)
            return HTTPExceptionJson(
                status.HTTP_401_UNAUTHORIZED,
                err='FAIL2BAN_LOGIN_FAILED',
                data={'remain': manager.max_attempts - 1},
            )

    def record_success(self):
        """
        Record successful login and clear failure records
        """
        if self.ip is None:
            return
        manager = Fail2BanManager(self.name)

        if self.ip in manager.failed_attempts:
            try:
                del manager.failed_attempts[self.ip]
            except KeyError:
                # race condition that record is clean up
                pass

    async def __call__(self, request: Request):
        self.ip = get_client_ip(request)
        return self
