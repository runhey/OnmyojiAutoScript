from threading import Lock
from time import time


class SafeIDGenerator:
    """
    Generate a unique ID that is safe in current process.

    Usage:
        # create a global generator
        CONN_ID_GENERATOR = SafeIDGenerator()
        # generate on call
        for _ in range(5):
            print(CONN_ID_GENERATOR.get())
    """

    def __init__(self, prefix=''):
        """
        Args:
            prefix (str):
        """
        self._prefix = prefix
        self._lock = Lock()
        self._last_time = -1
        self._last_seq = 0

    def get(self):
        """
        Returns:
            str: {prefix}_{timestamp_ms}_{seq}
        """
        with self._lock:
            now = int(time() * 1000)
            if now > self._last_time:
                self._last_time = now
                self._last_seq = 0
                prefix = self._prefix
                if prefix:
                    return f'{prefix}_{now}_0'
                else:
                    return f'{now}_0'
            else:
                # If within the same millisecond, increase seq
                # If we somehow get back to past, treat as same millisecond
                self._last_seq += 1
                prefix = self._prefix
                if prefix:
                    return f'{prefix}_{now}_{self._last_seq}'
                else:
                    return f'{now}_{self._last_seq}'
