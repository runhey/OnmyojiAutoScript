"""Tests for the deploy settings Groups."""

import pytest
from pydantic import ValidationError

from oas.config.models.args import Time
from oas.deploy.settings.groups import (
    AdbGroup,
    GitGroup,
    Language,
    OcrGroup,
    PythonGroup,
    RemoteAccessGroup,
    Theme,
    UpdateGroup,
    WebuiGroup,
)

ARG_COUNTS = (
    (GitGroup, 7),
    (PythonGroup, 1),
    (AdbGroup, 4),
    (OcrGroup, 4),
    (UpdateGroup, 3),
    (RemoteAccessGroup, 4),
    (WebuiGroup, 8),
)
GROUPS = tuple(group_class for group_class, _count in ARG_COUNTS)
COMPONENTS = ('Input', 'Switch', 'Option', 'Time')


@pytest.mark.parametrize(('group_class', 'arg_count'), ARG_COUNTS)
def test_group_declares_the_expected_argument_count(group_class, arg_count):
    assert len(group_class.model_fields) == arg_count


@pytest.mark.parametrize('group_class', GROUPS)
def test_every_argument_is_a_component_with_an_i18n_description(group_class):
    properties = group_class.model_json_schema()['properties']

    assert properties
    for name, prop in properties.items():
        assert prop['type'] in COMPONENTS
        assert prop['description'] == f'{name}_help'


@pytest.mark.parametrize('group_class', GROUPS)
def test_group_roundtrips_through_its_persisted_dict(group_class):
    group = group_class()

    assert group_class.from_dict(group.to_dict()) == group


def test_git_group_defaults():
    group = GitGroup()

    assert (
        group.repository
        == 'https://gitcode.com/OnmyojiAutoScript/OnmyojiAutoScript.git'
    )
    assert group.branch == 'master'
    assert group.git_executable == './toolkit/Git/mingw64/bin/git.exe'
    assert group.git_proxy is None
    assert group.ssl_verify is False
    assert group.auto_update is True
    assert group.keep_local_changes is False


def test_python_group_defaults():
    assert PythonGroup().pypi_mirror is None


def test_adb_group_defaults():
    group = AdbGroup()

    assert (
        group.adb_executable == './toolkit/Lib/site-packages/adbutils/binaries/adb.exe'
    )
    assert group.replace_adb is True
    assert group.auto_connect is True
    assert group.install_uiautomator2 is True


@pytest.mark.parametrize(
    ('group_class', 'name'),
    [(GitGroup, 'git_executable'), (AdbGroup, 'adb_executable')],
)
def test_executable_arguments_use_the_path_component(group_class, name):
    prop = group_class.model_json_schema()['properties'][name]

    assert prop['type'] == 'Input'
    assert prop['input'] == 'path'


def test_ocr_group_defaults():
    group = OcrGroup()

    assert group.use_ocr_server is False
    assert group.start_ocr_server is False
    assert group.ocr_server_port == 22268
    assert group.ocr_client_address == '127.0.0.1:22268'


@pytest.mark.parametrize('port', [1, 22268, 65535])
def test_ocr_server_port_accepts_the_port_range(port):
    assert OcrGroup(ocr_server_port=port).ocr_server_port == port


@pytest.mark.parametrize('port', [0, -1, 65536])
def test_ocr_server_port_rejects_a_value_out_of_range(port):
    with pytest.raises(ValidationError):
        OcrGroup(ocr_server_port=port)


def test_update_group_defaults():
    group = UpdateGroup()

    assert group.enable_reload is True
    assert group.check_update_interval == 5
    assert group.auto_restart_time == Time(3, 50)


def test_restart_time_is_persisted_as_an_iso_string():
    # The updater parses this value with ``time.fromisoformat``.
    assert UpdateGroup().to_dict()['auto_restart_time'] == '03:50:00'
    assert UpdateGroup.from_dict(
        {'auto_restart_time': '03:50:00'}
    ).auto_restart_time == Time(3, 50)


def test_restart_time_can_be_disabled():
    assert UpdateGroup(auto_restart_time=None).to_dict()['auto_restart_time'] is None
    assert UpdateGroup.from_dict({'auto_restart_time': None}).auto_restart_time is None


def test_restart_time_uses_the_time_component():
    prop = UpdateGroup.model_json_schema()['properties']['auto_restart_time']

    assert prop['type'] == 'Time'
    assert prop['default'] == '03:50:00'


def test_check_update_interval_rejects_a_negative_value():
    with pytest.raises(ValidationError):
        UpdateGroup(check_update_interval=-1)


def test_remote_access_group_defaults():
    group = RemoteAccessGroup()

    assert group.enable_remote_access is False
    assert group.ssh_user is None
    assert group.ssh_server is None
    assert group.ssh_executable == 'ssh'


def test_webui_group_defaults():
    group = WebuiGroup()

    assert group.host == '0.0.0.0'
    assert group.port == 22288
    assert group.language is Language.ZH_CN
    assert group.theme is Theme.DEFAULT
    assert group.dpi_scaling is True
    assert group.password is None
    assert group.cdn is False
    assert group.run is None


@pytest.mark.parametrize('port', [0, 65536])
def test_webui_port_rejects_a_value_out_of_range(port):
    with pytest.raises(ValidationError):
        WebuiGroup(port=port)


def test_webui_password_uses_the_secret_component():
    prop = WebuiGroup.model_json_schema()['properties']['password']

    assert prop['type'] == 'Input'
    assert prop['input'] == 'secret_str'
    assert prop['writeOnly'] is True


@pytest.mark.parametrize('cdn', ['http://cdn.example.com', True, False])
def test_webui_cdn_accepts_a_string_or_a_bool(cdn):
    assert WebuiGroup(cdn=cdn).cdn == cdn


def test_language_and_theme_members():
    assert Language.ZH_CN.value == 'zh-CN'
    assert Language.ZH_CN.option_item.field_info.title == '简体中文'
    assert [member.value for member in Language] == [
        'zh-CN',
        'en-US',
        'ja-JP',
        'zh-TW',
    ]
    assert [member.value for member in Theme] == ['default', 'dark']


def test_webui_language_exports_every_item():
    prop = WebuiGroup.model_json_schema()['properties']['language']

    assert prop['type'] == 'Option'
    assert [item['const'] for item in prop['oneOf']] == [
        'zh-CN',
        'en-US',
        'ja-JP',
        'zh-TW',
    ]
    assert [item['title'] for item in prop['oneOf']] == [
        '简体中文',
        'English',
        '日本語',
        '繁體中文',
    ]


def test_webui_rejects_an_unknown_language_and_theme():
    with pytest.raises(ValidationError):
        WebuiGroup(language='en-GB')
    with pytest.raises(ValidationError):
        WebuiGroup(theme='dark-blue')
