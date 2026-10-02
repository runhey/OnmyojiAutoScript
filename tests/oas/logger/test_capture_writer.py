from oas.logger import logger


class TestMockCaptureWriter:
    def test_mock_capture_writer(self):
        """
        Test that mock_capture_writer correctly captures all types of logs
        without writing to actual stdout, files, or backend.
        """
        with logger.mock_capture_writer() as capture:
            # 1. Test basic logging
            logger.info("Hello Info")
            assert capture.fd.any_contains("Hello Info")
            # backend is inited, logs are sent to backend + file only, not stdout
            assert not capture.stdout.any_contains("Hello Info")
            assert any(log['l'] == 'INFO' and log['m'] == 'Hello Info' for log in capture.backend.logs)
            capture.clear()

            # 2. Test raw logging
            logger.raw("Hello Raw")
            assert capture.fd.any_contains("Hello Raw\n")
            # backend is inited, logs are sent to backend + file only, not stdout
            assert not capture.stdout.any_contains("Hello Raw\n")
            assert any(log['r'] == 1 and log['m'] == 'Hello Raw' for log in capture.backend.logs)
            capture.clear()

            # 3. Test exception logging
            try:
                raise ValueError("Test Error")
            except ValueError:
                logger.exception("An exception occurred")

            # Verify exception is in text output
            assert capture.fd.any_contains("ValueError: Test Error")
            # Verify exception is in backend log
            assert capture.backend.any_contains("ValueError: Test Error")
            capture.clear()

            logger.info("Fresh log")
            assert capture.fd.any_contains("Fresh log")
            assert len(capture.backend.logs) == 1

    def test_mock_capture_writer_restoration(self):
        """
        Test that the original writer is restored after the context manager exits.
        """
        original_writer = logger._writer

        with logger.mock_capture_writer() as capture:
            assert logger._writer is capture
            assert logger._writer is not original_writer

        assert logger._writer is original_writer

    def test_mock_capture_writer_nested(self):
        """
        Test that mock_capture_writer can be nested and each context
        collects the logs printed within its own context correctly.
        """
        with logger.mock_capture_writer() as outer:
            logger.info("Outer 1")
            with logger.mock_capture_writer() as inner:
                logger.info("Inner")
                assert inner.fd.any_contains("Inner")
                assert not inner.fd.any_contains("Outer 1")

            logger.info("Outer 2")

            # Outer should have everything that happened in its context
            assert outer.fd.any_contains("Outer 1")
            assert outer.fd.any_contains("Inner")
            assert outer.fd.any_contains("Outer 2")

            # Inner should only have what happened in its context
            assert len(inner.fd.logs) == 1
            assert inner.fd.any_contains("Inner")

    def test_mock_capture_writer_nested_clear(self):
        """
        Test that clear() in nested contexts doesn't affect parents prematurely,
        but parents still collect the logs even if the child cleared them locally.
        """
        with logger.mock_capture_writer() as outer:
            logger.info("Outer 1")
            with logger.mock_capture_writer() as inner:
                logger.info("Inner 1")
                inner.clear()
                logger.info("Inner 2")

            # Inner and Outer are separate storages, but Inner passes logs to Outer
            # when they are emitted. Clearing Inner doesn't clear Outer.
            assert outer.fd.any_contains("Inner 1")
            assert outer.fd.any_contains("Inner 2")
            assert not inner.fd.any_contains("Inner 1")
            assert inner.fd.any_contains("Inner 2")
