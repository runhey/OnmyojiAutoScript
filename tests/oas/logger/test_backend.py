import re
import time
from datetime import date
from unittest.mock import MagicMock

import pytest

from oas.ext import env
from oas.ext.cache import cached_property_threadsafe
from oas.ext.path import PathStr
from oas.logger.logger import LogWriter, logger


class MockBackendBridge:
    """
    Mock BackendBridge for testing backend logging
    """

    def __init__(self):
        self.inited = True
        self.config_name = 'test_config'
        self.log_events = []  # Store all log events
        self.send_log_calls = []  # Store all send_log calls

    def send_log(self, event: dict):
        """
        Mock send_log that captures events
        """
        # Store the event
        self.log_events.append(event.copy())
        self.send_log_calls.append(event)

        # Return a mock job that can be acquired
        job = MagicMock()
        job.acquire = MagicMock(return_value=None)
        return job

    def clear(self):
        """
        Clear stored events
        """
        self.log_events.clear()
        self.send_log_calls.clear()


class BaseLoggerTest:
    """
    Test that logger correctly sends messages to backend
    """

    @pytest.fixture(autouse=True)
    def setup_teardown(self):
        """
        Setup and cleanup for each test
        """
        # Store original env values
        original_root = env.PROJECT_ROOT

        # Create temp directory for test logs
        self.test_dir = PathStr.new(__file__).uppath(1)
        env.PROJECT_ROOT = self.test_dir
        # OAS has no Electron shell; LogWriter.is_electron is a plain False
        # attribute, so there is no env.ELECTRON to reset here.

        # Create mock backend
        self.mock_backend = MockBackendBridge()

        # Patch BackendBridge class to return our mock
        writer = LogWriter()
        cached_property_threadsafe.set(writer, 'backend', self.mock_backend)

        # Clear any initialization events
        self.mock_backend.clear()

        # Use the existing logger instance
        self.logger = logger
        logger.set_level('DEBUG')

        yield

        writer = LogWriter()
        writer.close()

        env.PROJECT_ROOT = original_root

        log_dir = self.test_dir / 'log'
        log_dir.folder_rmtree()


class TestBackendLogging(BaseLoggerTest):
    """
    Test that logger correctly sends messages to backend
    """

    def _get_last_event(self):
        """
        Get the last event sent to backend

        Returns:
            dict: Last event sent to backend
        """
        if not self.mock_backend.log_events:
            return None
        return self.mock_backend.log_events[-1]

    def _get_all_events(self):
        """
        Get all events sent to backend

        Returns:
            list[dict]: All events sent to backend
        """
        return self.mock_backend.log_events

    def test_basic_info_log_to_backend(self):
        """
        Test that basic info log is correctly sent to backend
        """
        # Log a message
        self.logger.info('Test backend message')

        # Get the event sent to backend
        event = self._get_last_event()

        # Verify event structure
        assert event is not None
        assert 't' in event  # timestamp
        assert 'l' in event  # level
        assert 'm' in event  # message

        # Verify event content
        assert event['l'] == 'INFO'
        assert event['m'] == 'Test backend message'

        # Verify timestamp is reasonable (within last second)
        assert isinstance(event['t'], (int, float))
        assert abs(time.time() - event['t']) < 1.0

    def test_different_log_levels_to_backend(self):
        """
        Test that different log levels are correctly sent to backend
        """
        # Log at different levels
        self.logger.debug('Debug message')
        self.logger.info('Info message')
        self.logger.warning('Warning message')
        self.logger.error('Error message')
        self.logger.critical('Critical message')

        # Get all events
        events = self._get_all_events()

        # Verify we have 5 events
        assert len(events) == 5

        # Verify levels
        assert events[0]['l'] == 'DEBUG'
        assert events[1]['l'] == 'INFO'
        assert events[2]['l'] == 'WARNING'
        assert events[3]['l'] == 'ERROR'
        assert events[4]['l'] == 'CRITICAL'

        # Verify messages
        assert events[0]['m'] == 'Debug message'
        assert events[1]['m'] == 'Info message'
        assert events[2]['m'] == 'Warning message'
        assert events[3]['m'] == 'Error message'
        assert events[4]['m'] == 'Critical message'

    def test_formatted_message_to_backend(self):
        """
        Test that formatted messages are correctly processed before being sent to backend
        """
        # Log with formatting
        self.logger.info('User {name} logged in from {location}', name='Alice', location='Singapore')

        # Get the event
        event = self._get_last_event()

        # Verify formatted message is sent to backend
        assert event['m'] == 'User Alice logged in from Singapore'
        assert event['l'] == 'INFO'

    def test_exception_to_backend(self):
        """
        Test that exceptions are correctly sent to backend with exception info
        """
        # Log an exception
        try:
            raise ValueError('Test exception')
        except ValueError:
            self.logger.exception('An error occurred')

        # Get the event
        event = self._get_last_event()

        # Verify event has exception field
        assert event is not None
        assert 'e' in event
        assert event['l'] == 'ERROR'
        assert event['m'] == 'An error occurred'

        # Verify exception content
        exception_text = event['e']
        assert 'ValueError' in exception_text
        assert 'Test exception' in exception_text
        assert 'Traceback' in exception_text

    def test_raw_log_to_backend(self):
        """
        Test that raw logs are correctly marked in backend events
        """
        # Log a raw message
        self.logger.raw('Raw backend message')

        # Get the event
        event = self._get_last_event()

        # Verify raw flag is set
        assert event is not None
        assert 'r' in event
        assert event['r'] == 1
        assert event['m'] == 'Raw backend message'
        # Raw logs use INFO level internally
        assert event['l'] == 'INFO'

    def test_hr_logs_to_backend(self):
        """
        Test that hr logs generate multiple events to backend
        """
        # Clear existing events
        self.mock_backend.clear()

        # Log hr0 which generates 4 events (3 raw + 1 info)
        self.logger.hr0('Test Title')

        # Get all events
        events = self._get_all_events()

        # hr0 generates 4 events
        assert len(events) == 4

        # First 3 should be raw (with 'r' field)
        assert 'r' in events[0]
        assert 'r' in events[1]
        assert 'r' in events[2]

        # Last one should be info without 'r' field
        assert 'r' not in events[3]
        assert events[3]['l'] == 'INFO'
        assert events[3]['m'] == 'TEST TITLE'

    def test_error_with_exception_object(self):
        """
        Test that logging an Exception object directly is correctly formatted
        """
        # Create an exception
        error = ValueError('Something went wrong')

        # Log the exception object
        self.logger.error(error)

        # Get the event
        event = self._get_last_event()

        # Verify the message is formatted
        assert event is not None
        assert event['l'] == 'ERROR'
        assert event['m'] == 'ValueError: Something went wrong'

    def test_exception_with_exception_object(self):
        """
        Test that logger.exception() with Exception object includes traceback
        """
        # Create and catch an exception
        try:
            raise RuntimeError('Runtime error occurred')
        except RuntimeError as e:
            self.logger.exception(e)

        # Get the event
        event = self._get_last_event()

        # Verify message format
        assert event is not None
        assert event['l'] == 'ERROR'
        assert event['m'] == 'RuntimeError: Runtime error occurred'

        # Verify exception traceback is included
        assert 'e' in event
        assert 'RuntimeError' in event['e']
        assert 'Runtime error occurred' in event['e']
        assert 'Traceback' in event['e']

    def test_multiple_logs_order(self):
        """
        Test that multiple logs are sent to backend in correct order
        """
        # Clear existing events
        self.mock_backend.clear()

        # Log multiple messages
        messages = ['First', 'Second', 'Third', 'Fourth', 'Fifth']
        for msg in messages:
            self.logger.info(msg)

        # Get all events
        events = self._get_all_events()

        # Verify order
        assert len(events) == 5
        for i, msg in enumerate(messages):
            assert events[i]['m'] == msg

        # Verify timestamps are increasing
        for i in range(len(events) - 1):
            assert events[i]['t'] <= events[i + 1]['t']

    def test_backend_receives_no_file_formatting(self):
        """
        Test that backend receives clean messages without file formatting
        """
        # Log a message
        self.logger.info('Clean message')

        # Get the event
        event = self._get_last_event()

        # Backend should receive clean message without timestamp/level prefix
        assert event['m'] == 'Clean message'
        # Should not contain file format
        assert '|' not in event['m']
        assert re.match(r'\d{4}-\d{2}-\d{2}', event['m']) is None

    def test_config_name_in_log_filename(self):
        """
        Test that when backend is initialized, log filename includes config name
        """
        # Log something to initialize file
        self.logger.info('Test message')

        # Get log file
        log_dir = self.test_dir / 'log'
        log_files = list(log_dir.iter_files(ext='.txt'))

        # Should have one log file
        assert len(log_files) == 1

        # Filename should include config name from backend
        today = date.today()
        expected_filename = f'{today}_{self.mock_backend.config_name}.txt'
        assert log_files[0].name == expected_filename


class TestBackendLoggingWithElectron(BaseLoggerTest):
    """
    Test backend logging behavior in Electron mode
    """

    def test_electron_mode_logs_to_backend(self):
        """
        Test that logs are still sent to backend in Electron mode
        """
        # Log a message
        self.logger.info('Electron mode message')

        # Get the event
        events = self.mock_backend.log_events
        assert len(events) == 1
        assert events[0]['m'] == 'Electron mode message'
        assert events[0]['l'] == 'INFO'


class TestBackendNoInit(BaseLoggerTest):
    """
    Test logging behavior when backend is not initialized
    """

    def test_no_backend_no_events(self):
        """
        Test that when backend is not initialized, no events are sent
        """
        self.mock_backend.inited = False

        # Log a message
        self.logger.info('Message without backend')

        # Verify no events were sent to backend
        events = self.mock_backend.log_events

        # send_log should not be called
        assert len(events) == 0

    def test_exception_without_backend(self):
        """
        Test that exceptions can still be logged when backend is not initialized
        """
        self.mock_backend.inited = False

        # Log an exception
        try:
            raise ValueError('Test exception')
        except ValueError:
            self.logger.exception('Error without backend')

        events = self.mock_backend.log_events

        # send_log should not be called
        assert len(events) == 0
