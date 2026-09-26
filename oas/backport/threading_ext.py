import threading


class PreemptiveEvent(threading.Event):
    def get_and_clear(self):
        """
        Safely preempt an event and clear it

        It's a thread-safe version of:
            if event.is_set():
                event.clear()
        """
        with self._cond:
            flag = self._flag
            self._flag = False
        return flag
