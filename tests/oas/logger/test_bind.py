from oas.logger import logger


def test_logger_bind():
    """
    Test logger.bind() behavior.
    """
    with logger.mock_capture_writer() as capture:
        # 1. Base logger should not have bound values
        logger.info("Message 1")
        assert capture.fd.any_contains("Message 1")
        assert not capture.fd.any_contains("user=")
        capture.clear()

        # 2. Bound logger should have the value
        bound = logger.bind(user="alice")
        bound.info("Message 2")
        # Note: If this fails, it means bind() did not preserve the mock writer
        assert capture.fd.any_contains("Message 2")
        assert capture.fd.any_contains("user='alice'")
        capture.clear()

        # 3. Base logger should still not have the value
        logger.info("Message 3")
        assert capture.fd.any_contains("Message 3")
        assert not capture.fd.any_contains("user=")
        capture.clear()

        # 4. Multiple binds
        deeper = bound.bind(action="login")
        deeper.info("Message 4")
        assert capture.fd.any_contains("Message 4")
        assert capture.fd.any_contains("user='alice'")
        assert capture.fd.any_contains("action='login'")
        capture.clear()

        # 5. Overwriting bound values
        overwritten = deeper.bind(user="bob")
        overwritten.info("Message 5")
        assert capture.fd.any_contains("Message 5")
        assert capture.fd.any_contains("user='bob'")
        assert capture.fd.any_contains("action='login'")
        assert not capture.fd.any_contains("user='alice'")
        capture.clear()


def test_logger_unbind():
    """
    Test logger.unbind() behavior.
    """
    with logger.mock_capture_writer() as capture:
        bound = logger.bind(user="alice", action="login", session=123)
        bound.info("Message 1")
        assert capture.fd.any_contains("user='alice'")
        assert capture.fd.any_contains("action='login'")
        assert capture.fd.any_contains("session=123")
        capture.clear()

        # 1. Unbind one key
        unbound_one = bound.unbind("session")
        unbound_one.info("Message 2")
        assert capture.fd.any_contains("user='alice'")
        assert capture.fd.any_contains("action='login'")
        assert not capture.fd.any_contains("session=")
        capture.clear()

        # 2. Unbind multiple keys
        unbound_multi = bound.unbind("user", "action")
        unbound_multi.info("Message 3")
        assert not capture.fd.any_contains("user=")
        assert not capture.fd.any_contains("action=")
        assert capture.fd.any_contains("session=123")
        capture.clear()

        # 3. Unbind non-existent key (should not raise error)
        unbound_none = bound.unbind("non_existent")
        unbound_none.info("Message 4")
        assert capture.fd.any_contains("user='alice'")
        capture.clear()


def test_bind_affects_backend():
    """
    Test that bound values are correctly passed to the backend.
    """
    with logger.mock_capture_writer() as capture:
        bound = logger.bind(user="alice", status="active")
        bound.info("System check")

        # Verify backend log
        assert len(capture.backend.logs) == 1
        assert capture.backend.any_contains("System check")
        assert capture.backend.any_contains("user='alice'")
        assert capture.backend.any_contains("status='active'")


def test_bind_with_formatting():
    """
    Test bind() together with positional formatting.
    """
    with logger.mock_capture_writer() as capture:
        bound = logger.bind(app="alasio")
        bound.info("User {name} logged in", name="alice")

        assert capture.fd.any_contains("User alice logged in")
        assert capture.fd.any_contains("app='alasio'")
