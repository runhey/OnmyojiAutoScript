import asyncio
from typing import Callable, Optional


class AnyIO:
    """
    Backend runtime context: the event loop handle a plain thread needs in
    order to hand work back to the async side.

    Alasio used Trio's ``TrioToken`` for this (``current_trio_token()`` plus
    ``run_sync_soon()``). AnyIO publishes no such handle, so the backend
    keeps the loop itself here instead. Uvicorn serves the app on asyncio,
    so the handle is an ``asyncio.AbstractEventLoop``.

    Binding:
    - startup: FastAPI lifespan calls ``bind_loop(asyncio.get_running_loop())``;
    - no lifespan (tests / standalone scripts): the first call made from
      inside the loop registers it on the fly -- the lazy capture Alasio did
      with ``current_trio_token()`` on the first subscribe;
    - shutdown: ``unbind_loop()`` drops the handle.

    Everything is a classmethod, so a caller writes ``AnyIO.call_soon(fn)``
    without holding an instance and without checking state first.
    """

    # Loop of the current backend run. Private to this class: callers go
    # through loop(), which also covers the not-yet-bound / closed cases.
    _loop: 'Optional[asyncio.AbstractEventLoop]' = None

    @classmethod
    def bind_loop(cls, loop):
        """
        Register the loop of the current run (FastAPI lifespan startup).

        Args:
            loop (asyncio.AbstractEventLoop): The loop of the current run.
        """
        cls._loop = loop

    @classmethod
    def unbind_loop(cls):
        """
        Drop the loop handle (FastAPI lifespan shutdown).

        Afterwards call_soon() reports failure instead of touching a dead
        loop, and loop() re-captures when a later run asks from inside its
        own loop.
        """
        cls._loop = None

    @classmethod
    def loop(cls):
        """
        Return the loop of the current backend run.

        A stale handle (never bound, or left over from a run that already
        ended) is replaced by the running loop of the caller, so the same
        call site works with and without lifespan registration.

        Returns:
            asyncio.AbstractEventLoop:

        Raises:
            RuntimeError: Called from a thread that has no running loop
                while nothing is bound -- there is no loop to hand out.
        """
        loop = cls._loop
        if loop is None or loop.is_closed():
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                raise RuntimeError(
                    'AnyIO.loop(): no event loop is bound and the calling '
                    'thread has none. Bind it at startup with '
                    'AnyIO.bind_loop(asyncio.get_running_loop()).'
                ) from None
            cls._loop = loop
        return loop

    @classmethod
    def call_soon(cls, func: 'Callable[..., object]', *args):
        """
        Wake the loop from any thread: schedule a sync callback on it. This
        is the replacement of Trio's ``TrioToken.run_sync_soon()``.

        The callback always runs LATER, even when it is called from the loop
        thread itself, and it lands in the loop's own ready queue -- so it
        stays ordered against everything else scheduled on the loop
        (source.reinit depends on this to keep a queued full event behind
        the increments queued before it).

        The callback runs as a plain loop callback: it has the loop thread
        but no async task context. Sync work, ``Event.set()`` and a
        ``send_nowait()`` are fine there, and that is what the reactive
        drain and the ws outbox need; ``task_group.start_soon()``, a
        ``CancelScope()`` or ``get_cancelled_exc_class()`` are not, and
        have to be handed to the loop as a coroutine instead
        (``asyncio.run_coroutine_threadsafe()``).

        This is the single place that deals with a loop that is missing or
        already closed; call sites schedule and forget. Only "the loop is
        closed" is absorbed here: any other RuntimeError is not a shutdown
        and is re-raised.

        Returns:
            bool: True when the callback was scheduled, False when there is
                no usable loop (never bound, or closed) -- the replacement
                of Alasio's ``except trio.RunFinishedError: pass``.

        Raises:
            RuntimeError: A RuntimeError other than the closed loop itself
                came out of the scheduling call.
        """
        try:
            loop = cls.loop()
        except RuntimeError:
            # no loop at all: nothing can receive the callback
            return False
        if loop.is_closed():
            return False
        try:
            loop.call_soon_threadsafe(func, *args)
        except RuntimeError as exc:
            # The is_closed() check above races the delivery, so the closed
            # loop is recognized here as well -- and ONLY here, by the exact
            # message asyncio raises: anything else must not be mistaken for
            # a shutdown and has to surface.
            if loop.is_closed() or exc.args == ('Event loop is closed',):
                return False
            raise
        return True
