"""Tests for the top level deploy settings model."""

import pytest
from pydantic import ValidationError

from oas.deploy.settings.groups import (
    AdbGroup,
    GitGroup,
    OcrGroup,
    PythonGroup,
    RemoteAccessGroup,
    UpdateGroup,
    WebuiGroup,
)
from oas.deploy.settings.models import Settings

GROUP_FIELDS = ('git', 'python', 'adb', 'ocr', 'update', 'remote_access', 'webui')
GROUP_CLASSES = (
    GitGroup,
    PythonGroup,
    AdbGroup,
    OcrGroup,
    UpdateGroup,
    RemoteAccessGroup,
    WebuiGroup,
)


def test_settings_declares_the_seven_groups_in_order():
    assert tuple(Settings.model_fields) == GROUP_FIELDS

    settings = Settings()
    for name, group_class in zip(GROUP_FIELDS, GROUP_CLASSES, strict=True):
        assert type(getattr(settings, name)) is group_class


def test_settings_covers_every_argument_of_its_groups():
    assert sum(len(cls.model_fields) for cls in GROUP_CLASSES) == 31


def test_settings_to_dict_holds_only_the_groups():
    assert tuple(Settings().to_dict()) == GROUP_FIELDS


def test_group_descriptions_are_i18n_keys():
    properties = Settings.model_json_schema()['properties']

    for name in GROUP_FIELDS:
        assert properties[name]['description'] == f'{name}_group_help'


def test_schema_refs_one_definition_per_group():
    schema = Settings.model_json_schema()

    assert set(schema['$defs']) == {cls.__name__ for cls in GROUP_CLASSES}
    for name in GROUP_FIELDS:
        assert schema['properties'][name]['$ref'].startswith('#/$defs/')


def test_settings_defaults_are_the_group_defaults():
    settings = Settings()

    assert settings.git.auto_update is True
    assert settings.python.pypi_mirror is None
    assert settings.adb.replace_adb is True
    assert settings.ocr.ocr_server_port == 22268
    assert settings.update.check_update_interval == 5
    assert settings.remote_access.ssh_executable == 'ssh'
    assert settings.webui.port == 22288


def test_settings_roundtrips_through_its_persisted_dict():
    assert Settings.from_dict(Settings().to_dict()) == Settings()


def test_settings_from_dict_applies_nested_values():
    settings = Settings.from_dict(
        {
            'git': {'branch': 'dev'},
            'webui': {'port': 12345, 'language': 'ja-JP'},
        }
    )

    assert settings.git.branch == 'dev'
    assert settings.webui.port == 12345
    assert settings.webui.language.value == 'ja-JP'
    # A Group the payload does not mention keeps its defaults.
    assert settings.adb == AdbGroup()
    assert settings.git.repository == GitGroup().repository


@pytest.mark.parametrize(
    'payload',
    [
        {'webui': {'port': 0}},
        {'ocr': {'ocr_server_port': 'not-a-port'}},
        {'git': {'ssl_verify': 'maybe'}},
        {'webui': {'language': 'en-GB'}},
    ],
)
def test_settings_from_dict_rejects_invalid_values(payload):
    with pytest.raises(ValidationError):
        Settings.from_dict(payload)


def test_settings_from_dict_ignores_unknown_arguments():
    settings = Settings.from_dict({'git': {'removed_argument': 1}, 'removed': {}})

    assert settings == Settings()
