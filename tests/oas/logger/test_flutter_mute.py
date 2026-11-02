"""
Tests for the env.FLUTTER driven stdout mute (``oas/logger/writer.py``).

The supervisor sets ``FLUTTER=1`` before it spawns the backend, whose stdout is
the protocol channel the local Flutter host reads ([Supervisor] announcements,
stdin commands the other way). Log lines written there would sit in that
channel, so ``LogWriter`` snapshots the flag at construction and
``AlasioLogger._emit()`` then writes the log file only -- upstream's
``is_electron`` / ``ELECTRON`` semantics under the OAS names.
"""

import os
import subprocess
import sys

import pytest

from oas.ext import env
from oas.ext.cache import cached_property_threadsafe
from oas.ext.path import PathStr
from oas.logger import logger
from oas.logger.writer import CaptureStream, LogWriter

REPO_ROOT = PathStr.new(__file__).uppath(4)


@pytest.fixture
def writer(tmp_path, monkeypatch):
    """
    Point the log file at a temp folder and restore the writer afterwards.
    """
    instance = LogWriter()
    original_flag = instance.is_local_flutter
    original_root = env.PROJECT_ROOT
    monkeypatch.setattr(env, 'PROJECT_ROOT', PathStr.new(str(tmp_path)))
    instance.close_fd()
    logger.set_level('DEBUG')
    yield instance
    instance.is_local_flutter = original_flag
    env.PROJECT_ROOT = original_root
    cached_property_threadsafe.pop(instance, 'stdout')
    instance.close_fd()


def log_file_text(writer):
    """
    Text of the writer's log file.

    Args:
        writer (LogWriter): The writer whose file is read

    Returns:
        str: Log file content
    """
    return open(writer.file, encoding='utf-8').read()


def test_flag_off_writes_stdout_and_file(writer):
    """
    Without the flag the backend was started by hand, so a human reads stdout.
    """
    stream = CaptureStream()
    cached_property_threadsafe.set(writer, 'stdout', stream)
    writer.is_local_flutter = False

    logger.info('visible line')

    assert stream.any_contains('visible line')
    assert 'visible line' in log_file_text(writer)


def test_flag_on_writes_the_file_only(writer):
    """
    With FLUTTER=1 the host owns stdout: the line must reach the log file and
    never the channel the host reads commands from.
    """
    stream = CaptureStream()
    cached_property_threadsafe.set(writer, 'stdout', stream)
    writer.is_local_flutter = True

    logger.info('muted line')

    assert not stream.any_contains('muted line')
    assert 'muted line' in log_file_text(writer)


@pytest.mark.parametrize('value, expected', [('1', 'True'), ('', 'False')])
def test_the_flag_is_read_from_env_at_construction(value, expected):
    """
    The snapshot comes from env.FLUTTER, like upstream's env.ELECTRON: the
    supervisor sets it before process.start(), so the child reads it once.
    """
    code = (
        'from oas.logger.writer import LogWriter; print(LogWriter().is_local_flutter)'
    )
    result = subprocess.run(
        [sys.executable, '-c', code],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        env={**os.environ, 'FLUTTER': value},
        check=True,
    )
    assert result.stdout.strip() == expected
