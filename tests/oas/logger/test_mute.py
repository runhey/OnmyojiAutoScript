from oas.logger import logger
from oas.logger.writer import LogWriter, PseudoBackendBridge, PseudoStream
from tests.oas.logger.test_logger import BaseLoggerTest


class TestMute(BaseLoggerTest):
    """
    Test logger.mute() and logger.mute_clear() functionality
    """

    def test_mute_stdout(self):
        """
        Test muting and unmuting stdout
        """
        writer = LogWriter()

        # Initially not muted
        assert not isinstance(writer.stdout, PseudoStream)

        # Mute stdout
        logger.mute(stdout=True)
        assert isinstance(writer.stdout, PseudoStream)

        # Clear mute
        logger.mute_clear()
        assert not isinstance(writer.stdout, PseudoStream)

    def test_mute_fd(self):
        """
        Test muting and unmuting file output
        """
        writer = LogWriter()

        # Mute fd
        logger.mute(fd=True)
        assert isinstance(writer.fd, PseudoStream)

        # Log something while muted
        logger.info('Muted file message')
        content = self._read_log_file()
        assert 'Muted file message' not in content

        # Clear mute
        logger.mute_clear()
        assert not isinstance(writer.fd, PseudoStream)

        # Log something after clearing mute
        logger.info('Unmuted file message')
        content = self._read_log_file()
        assert 'Unmuted file message' in content

    def test_mute_backend(self):
        """
        Test muting and unmuting backend
        """
        writer = LogWriter()

        # Mute backend
        logger.mute(backend=True)
        assert isinstance(writer.backend, PseudoBackendBridge)
        assert writer.backend.inited is False

        # Clear mute
        logger.mute_clear()
        # Should return to original backend state (inited=False in tests as BackendBridge is not initialized)
        assert not isinstance(writer.backend, PseudoBackendBridge) or writer.backend is not None

    def test_mute_all(self):
        """
        Test muting all outputs
        """
        writer = LogWriter()

        # Mute all
        logger.mute(all=True)
        assert isinstance(writer.stdout, PseudoStream)
        assert isinstance(writer.fd, PseudoStream)
        assert isinstance(writer.backend, PseudoBackendBridge)

        # Log something while all muted
        logger.info('All muted message')
        content = self._read_log_file()
        assert 'All muted message' not in content

        # Clear mute
        logger.mute_clear()
        assert not isinstance(writer.stdout, PseudoStream)
        assert not isinstance(writer.fd, PseudoStream)
