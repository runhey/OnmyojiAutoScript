"""
Tests for the logger / fake filesystem interaction.

The logger caches its log file fd on the LogWriter singleton
(cached_property_threadsafe). When the fake filesystem is active, the
first log write opens the log file inside the fake filesystem and
caches that fake fd. After deactivation the singleton would keep the
fake fd and write later real logs into the fake filesystem memory,
losing them. The fs fixture closes the cached fd around the fake
filesystem, these tests verify the interaction and the combination
with logger.mock_capture_writer().
"""
import pytest

pytest.importorskip('oas.logger')

from oas.ext.cache import cached_property_threadsafe
from oas.logger import logger
from oas.logger.writer import LogWriter
from oas.testing.filesystem import FakeFilesystem, fs  # noqa: F401
from oas.testing.filesystem.file_object import FakeFileObject


class TestLoggerFakeFs:
    """The logger fd is cached inside the fake filesystem and closed after it."""

    def test_logger_fd_is_fake_inside_fakefs(self):
        fake = FakeFilesystem()
        fake.activate()
        try:
            logger.info('inside fakefs')
            # The first log write opens the log file inside the fake filesystem
            assert isinstance(LogWriter().fd, FakeFileObject)
        finally:
            fake.deactivate()
            LogWriter().close_fd()

    def test_close_fd_clears_cached_fd(self):
        fake = FakeFilesystem()
        fake.activate()
        try:
            logger.info('inside fakefs')
        finally:
            fake.deactivate()
        # Without the close the singleton would keep the fake fd
        writer = LogWriter()
        assert isinstance(writer.fd, FakeFileObject)
        # close_fd() drops the cached file and fd, the next write reopens a real one
        writer.close_fd()
        assert cached_property_threadsafe.get(writer, 'file') is None
        assert cached_property_threadsafe.get(writer, 'fd') is None

    def test_close_fd_idempotent(self):
        # Closing with no cached fd is a no-op
        writer = LogWriter()
        cached_property_threadsafe.pop(writer, 'fd', None)
        writer.close_fd()
        assert cached_property_threadsafe.get(writer, 'fd') is None

    def test_fs_fixture_clears_logger_fd(self, fs):
        # The fixture setup closes the logger fd, so no fd is cached on entry
        writer = LogWriter()
        assert cached_property_threadsafe.get(writer, 'fd') is None
        # Logging inside the fake filesystem opens a fake fd as expected
        logger.info('inside fakefs fixture')
        assert isinstance(writer.fd, FakeFileObject)


class TestLoggerFakeFsMockCapture:
    """fake filesystem and logger.mock_capture_writer() used together."""

    def test_fakefs_wraps_mock_capture_writer(self, fs):
        # fake filesystem active around logger.mock_capture_writer()
        with logger.mock_capture_writer() as capture:
            logger.info('captured')
            assert capture.fd.any_contains('captured')
            # the mock writer replaces logger._writer, the LogWriter fd is untouched
            assert cached_property_threadsafe.get(LogWriter(), 'fd') is None
        # mock exited, still inside the fake filesystem: logs go to a fake fd,
        # which the fixture teardown closes
        logger.info('after mock')
        assert isinstance(LogWriter().fd, FakeFileObject)

    def test_mock_capture_writer_wraps_fakefs(self):
        # logger.mock_capture_writer() active around the fake filesystem
        fake = FakeFilesystem()
        with logger.mock_capture_writer() as capture:
            fake.activate()
            try:
                logger.info('inside fakefs')
            finally:
                fake.deactivate()
            logger.info('after fakefs')
            # capture collects both, the LogWriter fd is never opened
            assert capture.fd.any_contains('inside fakefs')
            assert capture.fd.any_contains('after fakefs')
            assert cached_property_threadsafe.get(LogWriter(), 'fd') is None
        # after the mock exits, closing the fd keeps real logging working
        writer = LogWriter()
        writer.close_fd()
        assert cached_property_threadsafe.get(writer, 'fd') is None
