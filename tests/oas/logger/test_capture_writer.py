import re

import pytest

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


class TestConcat:
    """
    Test concat(), the debug helper that renders captured logs as a multi-line
    string without timestamp, so tests can assert the whole log output.
    """

    @pytest.fixture(autouse=True)
    def logger_level(self):
        """
        concat() tests must not depend on the level left behind by other test files
        """
        original = logger._level
        logger.set_level('DEBUG')
        yield
        logger.set_level(original)

    def test_concat(self):
        """
        Normal logs render as `LEVEL | message`, raw logs render as the message itself
        """
        with logger.mock_capture_writer() as capture:
            logger.info('message')
            logger.warning('message')
            logger.raw('raw message')

        assert capture.concat() == """\
INFO | message
WARNING | message
raw message
"""

    @pytest.mark.parametrize('method, expected', [
        ('debug', 'DEBUG'),
        ('info', 'INFO'),
        ('warning', 'WARNING'),
        ('error', 'ERROR'),
        ('critical', 'CRITICAL'),
    ])
    def test_level(self, method, expected):
        """
        The level name is rendered uppercase, without padding
        """
        with logger.mock_capture_writer() as capture:
            getattr(logger, method)('message')

        assert capture.concat() == f'{expected} | message\n'

    def test_empty(self):
        """
        Nothing was logged, nothing is rendered
        """
        with logger.mock_capture_writer() as capture:
            pass

        assert capture.concat() == ''

    def test_clear(self):
        """
        clear() drops the logs rendered before it
        """
        with logger.mock_capture_writer() as capture:
            logger.info('message 1')
            capture.clear()
            logger.info('message 2')

        assert capture.concat() == 'INFO | message 2\n'

    def test_multiline_message(self):
        """
        Only the first line of a message carries the level prefix
        """
        with logger.mock_capture_writer() as capture:
            logger.info('line 1\nline 2')

        assert capture.concat() == 'INFO | line 1\nline 2\n'

    def test_message_format_and_context(self):
        """
        The rendered message is the same as the printed one, with the bound
        context appended
        """
        with logger.mock_capture_writer() as capture:
            logger.info('User {name} logged in', name='May')
            logger.bind(user='May', action='login').info('Hello')

        assert capture.concat() == """\
INFO | User May logged in
INFO | Hello, user='May', action='login'
"""

    def test_exception(self):
        """
        The exception traceback is rendered after the log message
        """
        with logger.mock_capture_writer() as capture:
            try:
                raise ValueError('Test Error')
            except ValueError:
                logger.exception('An exception occurred')

        text = capture.concat()
        head, _, traceback = text.partition('\n')
        assert head == 'ERROR | An exception occurred'
        assert 'ValueError: Test Error' in traceback
        # traceback is followed by a blank line
        assert text.endswith('\n\n')

    def test_nested(self):
        """
        Each capture renders the logs of its own context only
        """
        with logger.mock_capture_writer() as outer:
            logger.info('Outer 1')
            with logger.mock_capture_writer() as inner:
                logger.raw('Inner')
            logger.info('Outer 2')

        assert inner.concat() == 'Inner\n'
        assert outer.concat() == """\
INFO | Outer 1
Inner
INFO | Outer 2
"""

    def test_matches_printed_log(self):
        """
        concat() is exactly the text written to the log file, minus the timestamp
        """
        with logger.mock_capture_writer() as capture:
            logger.debug('Debug message')
            logger.info('Info message')
            logger.hr('Section', level=3)
            logger.raw('Raw message')
            logger.warning('Warning message')
            logger.error('Error message')
            try:
                raise ValueError('Test Error')
            except ValueError:
                logger.exception('An exception occurred')

        # strip the timestamp, keep `INFO | `, see `AlasioLogger._msg()`
        timestamp = re.compile(r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3} \| ')
        expected = ''.join(timestamp.sub('', log, count=1) for log in capture.fd.logs)
        assert capture.concat() == expected
