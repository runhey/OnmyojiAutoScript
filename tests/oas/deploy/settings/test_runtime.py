"""Tests for the deploy settings runtime."""

import importlib
import os
from json import JSONDecodeError
from pathlib import Path

import pytest
from pydantic import ValidationError

from oas.deploy.settings import runtime
from oas.deploy.settings.groups import AdbGroup
from oas.deploy.settings.models import Settings
from oas.deploy.settings.runtime import DEPLOY_CONFIG, SettingsRuntime
from oas.ext.file.jsonfile import json_loads, write_json
from oas.ext.path import PathStr
from oas.ext.path.atomic import atomic_read_bytes, atomic_write
from oas.testing.filesystem import fs  # noqa: F401


@pytest.fixture
def settings_file(fs):
    """A settings path inside the fake filesystem, with a clean singleton."""
    SettingsRuntime.singleton_clear()
    yield str(PathStr.new(fs.root_dir.path) / 'config' / 'deploy.json')
    SettingsRuntime.singleton_clear()


def test_deploy_config_points_at_config_deploy_json():
    assert Path(DEPLOY_CONFIG).is_absolute()
    assert Path(DEPLOY_CONFIG).parent.name == 'config'
    assert Path(DEPLOY_CONFIG).name == 'deploy.json'


def test_deploy_config_does_not_follow_the_working_directory(fs):
    # The old './config/deploy.json' was resolved against the process cwd.
    elsewhere = str(PathStr.new(fs.root_dir.path) / 'elsewhere')
    fs.create_dir(elsewhere)
    os.chdir(elsewhere)

    reloaded = importlib.reload(runtime)
    try:
        assert reloaded.DEPLOY_CONFIG == DEPLOY_CONFIG
    finally:
        importlib.reload(runtime)


def test_default_file_is_the_module_constant(settings_file):
    assert SettingsRuntime().file == DEPLOY_CONFIG


def test_default_file_is_created_from_defaults(fs):
    SettingsRuntime.singleton_clear()
    try:
        assert SettingsRuntime().data == Settings()
        assert json_loads(atomic_read_bytes(DEPLOY_CONFIG)) == Settings().to_dict()
    finally:
        SettingsRuntime.singleton_clear()


def test_missing_file_is_created_from_defaults(settings_file):
    data = SettingsRuntime(file=settings_file).data

    assert data == Settings()
    assert json_loads(atomic_read_bytes(settings_file)) == Settings().to_dict()


def test_existing_file_is_validated_and_read(settings_file):
    write_json(settings_file, {'webui': {'port': 12345}, 'git': {'branch': 'dev'}})

    data = SettingsRuntime(file=settings_file).data

    assert data.webui.port == 12345
    assert data.git.branch == 'dev'
    # A Group the file does not mention keeps its defaults.
    assert data.adb == AdbGroup()


def test_every_access_re_reads_the_file(settings_file):
    settings = SettingsRuntime(file=settings_file)

    assert settings.data.webui.port == 22288

    write_json(settings_file, {'webui': {'port': 12345}}, skip_same=False)

    assert settings.data.webui.port == 12345


def test_corrupt_json_raises_and_keeps_the_file(settings_file):
    atomic_write(settings_file, b'not json')

    with pytest.raises(JSONDecodeError):
        SettingsRuntime(file=settings_file).data
    assert atomic_read_bytes(settings_file) == b'not json'


def test_invalid_value_raises_and_keeps_the_file(settings_file):
    write_json(settings_file, {'webui': {'port': 0}})
    before = atomic_read_bytes(settings_file)

    with pytest.raises(ValidationError):
        SettingsRuntime(file=settings_file).data
    assert atomic_read_bytes(settings_file) == before


def test_singleton_keeps_the_first_file(settings_file, fs):
    first = SettingsRuntime(file=settings_file)
    other = f'{fs.root_dir.path}/other.json'

    assert SettingsRuntime(file=other) is first
    assert SettingsRuntime(file=other).file == settings_file

    SettingsRuntime.singleton_clear()

    assert SettingsRuntime(file=other).file == other
