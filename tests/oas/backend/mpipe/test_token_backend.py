import time

import pytest

from oas.backend.mpipe.mpipe_backend import mpipe_backend
from oas.backend.mpipe.token_backend import BackendTokenTable


class TestMPipeBackend:
    """MPipeBackend: __bool__ and the locked send to the supervisor."""

    def test_bool_false_without_conn(self, monkeypatch):
        import builtins

        monkeypatch.delattr(builtins, '__mpipe_conn__', raising=False)
        assert not mpipe_backend

    def test_bool_true_with_conn(self, monkeypatch):
        import builtins

        monkeypatch.setattr(builtins, '__mpipe_conn__', object(), raising=False)
        assert mpipe_backend

    def test_disconnect_reads_as_no_supervisor(self, monkeypatch):
        """
        The recv loop clears the pipe when the supervisor is gone or asked the
        backend to stop: every later check reads it as no supervisor, and the
        strict send of the restart / stop RPCs answers the accurate error
        """
        import builtins

        from oas.backend.mpipe.mpipe_backend import has_supervisor

        monkeypatch.setattr(builtins, '__mpipe_conn__', object(), raising=False)
        assert has_supervisor() is True
        mpipe_backend.disconnect()
        assert not mpipe_backend
        assert has_supervisor() is False
        with pytest.raises(PermissionError):
            mpipe_backend.send(b'command:restart', strict=True)

    def test_has_supervisor_without_a_pipe(self, monkeypatch):
        import builtins

        from oas.backend.mpipe.mpipe_backend import has_supervisor

        monkeypatch.delattr(builtins, '__mpipe_conn__', raising=False)
        assert has_supervisor() is False

    def test_send_without_conn_is_silent(self, monkeypatch):
        """No pipe (backend without supervisor): send() is a no-op."""
        import builtins

        monkeypatch.delattr(builtins, '__mpipe_conn__', raising=False)
        mpipe_backend.send(b'token_ack:x')  # should not raise

    def test_send_without_conn_strict_raises(self, monkeypatch):
        """strict=True must fail loudly without a pipe (lifespan RPCs)."""
        import builtins

        monkeypatch.delattr(builtins, '__mpipe_conn__', raising=False)
        with pytest.raises(PermissionError):
            mpipe_backend.send(b'command:stop', strict=True)

    def test_send_with_conn(self, monkeypatch):
        """send() writes through the pipe connection."""
        import builtins

        sent = []

        class FakeConn:
            def send_bytes(self, data):
                sent.append(bytes(data))

        monkeypatch.setattr(builtins, '__mpipe_conn__', FakeConn(), raising=False)
        mpipe_backend.send(b'hello')
        assert sent == [b'hello']

    def test_send_broken_pipe_silent(self, monkeypatch):
        """Pipe broken (supervisor gone): send() swallows the error."""
        import builtins

        class BrokenConn:
            def send_bytes(self, data):
                raise EOFError

        monkeypatch.setattr(builtins, '__mpipe_conn__', BrokenConn(), raising=False)
        mpipe_backend.send(b'hello')  # should not raise

    def test_send_broken_pipe_strict_raises(self, monkeypatch):
        """strict=True propagates pipe errors."""
        import builtins

        class BrokenConn:
            def send_bytes(self, data):
                raise EOFError

        monkeypatch.setattr(builtins, '__mpipe_conn__', BrokenConn(), raising=False)
        with pytest.raises(EOFError):
            mpipe_backend.send(b'hello', strict=True)


class TestBackendTokenTable:
    def test_seed_from_supervisor(self):
        """Seeding fills the table with the spawn-args window."""
        table = BackendTokenTable()
        table.seed_from_supervisor(('t1', 't2'))
        assert table.verify('t1')
        assert table.verify('t2')

    def test_seed_empty(self):
        """Empty seed leaves the table empty (non-electron lock state)."""
        table = BackendTokenTable()
        table.seed_from_supervisor(())
        assert not table.verify('anything')

    def test_handle_token_adds_and_evicts_oldest(self):
        """handle_token adds a token; > max evicts the oldest entry."""
        table = BackendTokenTable(max_tokens=2)
        table.seed_from_supervisor(('t1', 't2'))
        table.handle_token('t3')
        assert table.verify('t2')
        assert table.verify('t3')
        assert not table.verify('t1')

    def test_handle_token_never_evicts_fresh_token(self, monkeypatch):
        """The freshly added token is never evicted by a tied timestamp."""
        table = BackendTokenTable(max_tokens=2)
        table.seed_from_supervisor(('t1',))
        # force a tied timestamp: same clock value for both entries
        monkeypatch.setattr(time, 'time', lambda: 100.0)
        table.handle_token('t2')
        table.handle_token('t3')
        assert table.verify('t3')
        assert len(table._tokens) == 2

    def test_current_returns_latest(self, monkeypatch):
        """current() returns the most recently added token."""
        clock = iter([1.0, 2.0])
        monkeypatch.setattr(time, 'time', lambda: next(clock))
        table = BackendTokenTable()
        table.seed_from_supervisor(('t1', 't2'))
        assert table.current() == 't2'
        monkeypatch.setattr(time, 'time', lambda: 3.0)
        table.handle_token('t3')
        assert table.current() == 't3'

    def test_current_empty_table(self):
        """current() on an empty table returns ''."""
        table = BackendTokenTable()
        assert table.current() == ''

    def test_verify_miss(self):
        """verify() returns False for unknown tokens."""
        table = BackendTokenTable()
        table.seed_from_supervisor(('t1',))
        assert not table.verify('t2')
        assert not table.verify('')


class TestHandleTokenAck:
    """handle_token acknowledges back through MPipeBackend."""

    def test_handle_token_acks_back(self, monkeypatch):
        """handle_token adds the token and sends token_ack through the pipe."""
        import builtins

        sent = []

        class FakeConn:
            def send_bytes(self, data):
                sent.append(bytes(data))

        monkeypatch.setattr(builtins, '__mpipe_conn__', FakeConn(), raising=False)
        table = BackendTokenTable()
        table.handle_token('tok1')
        assert table.verify('tok1')
        assert sent == [b'token_ack:tok1']

    def test_handle_token_without_conn_is_silent(self, monkeypatch):
        """No pipe (backend without supervisor): the ack is dropped."""
        import builtins

        monkeypatch.delattr(builtins, '__mpipe_conn__', raising=False)
        table = BackendTokenTable()
        table.handle_token('tok1')  # should not raise
        assert table.verify('tok1')


class TestVerifyHeader:
    """verify_header: the header name is centralized, Request/scope compatible."""

    @staticmethod
    def make_scope(headers):
        return {
            'type': 'http',
            'method': 'GET',
            'path': '/api/x',
            'headers': headers,
            'client': ('127.0.0.1', 1),
            'query_string': b'',
            'scheme': 'http',
            'server': ('127.0.0.1', 22267),
        }

    def test_request_with_valid_header(self):
        """A starlette Request with the electron token header verifies."""
        from starlette.requests import Request

        table = BackendTokenTable()
        table.seed_from_supervisor(('tok1',))
        request = Request(self.make_scope([(b'x-alasio-token', b'tok1')]))
        assert table.verify_header(request)

    def test_request_mixed_case_header(self):
        """ASGI mandates lowercase header names: a mixed-case scope header
        does not match (starlette compares the lowercased lookup key against
        the raw stored name). Real requests from hypercorn are always
        lowercase, so this documents the invariant."""
        from starlette.requests import Request

        table = BackendTokenTable()
        table.seed_from_supervisor(('tok1',))
        request = Request(self.make_scope([(b'X-Alasio-Token', b'tok1')]))
        assert not table.verify_header(request)

    def test_request_without_header(self):
        """A request without the header does not verify."""
        from starlette.requests import Request

        table = BackendTokenTable()
        table.seed_from_supervisor(('tok1',))
        request = Request(self.make_scope([]))
        assert not table.verify_header(request)

    def test_raw_scope_dict(self):
        """A raw ASGI scope dict (lowercase bytes headers) verifies."""
        table = BackendTokenTable()
        table.seed_from_supervisor(('tok1',))
        assert table.verify_header({'headers': [(b'x-alasio-token', b'tok1')]})
        assert not table.verify_header({'headers': []})
        assert not table.verify_header({})

    def test_invalid_token_false(self):
        """A token not in the table does not verify."""
        table = BackendTokenTable()
        table.seed_from_supervisor(('tok1',))
        assert not table.verify_header({'headers': [(b'x-alasio-token', b'other')]})

    def test_empty_table_false(self):
        """An empty table (non-electron lock state) never verifies."""
        table = BackendTokenTable()
        assert not table.verify_header({'headers': [(b'x-alasio-token', b'tok1')]})
