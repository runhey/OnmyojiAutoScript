"""Deploy configuration Groups.

These Groups describe the deploy settings that used to live in
``config/deploy.yaml``.  Every field is declared with an
:mod:`oas.config.models.args` factory, so the deploy settings export the same
component markers (``Input``, ``Switch``, ``Option`` ...) as Task Groups and
can be rendered by the same schema driven GUI pipeline.

Field names are snake_case, following the ``oas.config`` convention.  The
mapping to the legacy ``deploy/template`` keys is documented in ``README.md``.
Descriptions are i18n keys, following ``SchedulerGroup``.
"""

from oas.config.models.args import Input, Option, OptionItem, Switch, Time
from oas.config.models.groups import GroupBase


class Language(Option):
    """Web UI language."""

    ZH_CN = OptionItem.str('zh-CN', title='简体中文')
    EN_US = OptionItem.str('en-US', title='English')
    JA_JP = OptionItem.str('ja-JP', title='日本語')
    ZH_TW = OptionItem.str('zh-TW', title='繁體中文')


class Theme(Option):
    """Web UI theme."""

    DEFAULT = OptionItem.str('default', title='浅色')
    DARK = OptionItem.str('dark', title='深色')


class GitGroup(GroupBase):
    """Git repository and update policy."""

    repository: str = Input.str(
        default='https://gitcode.com/OnmyojiAutoScript/OnmyojiAutoScript.git',
        description='repository_help',
    )
    branch: str = Input.str(
        default='master',
        description='branch_help',
    )
    git_executable: str = Input.path(
        default='./toolkit/Git/mingw64/bin/git.exe',
        description='git_executable_help',
    )
    git_proxy: str | None = Input.str(
        default=None,
        description='git_proxy_help',
    )
    ssl_verify: bool = Switch.field(
        default=False,
        description='ssl_verify_help',
    )
    auto_update: bool = Switch.field(
        default=True,
        description='auto_update_help',
    )
    keep_local_changes: bool = Switch.field(
        default=False,
        description='keep_local_changes_help',
    )


class PythonGroup(GroupBase):
    """Python dependency download source."""

    pypi_mirror: str | None = Input.str(
        default=None,
        description='pypi_mirror_help',
    )


class AdbGroup(GroupBase):
    """ADB executable and emulator connection behaviour."""

    adb_executable: str = Input.path(
        default='./toolkit/Lib/site-packages/adbutils/binaries/adb.exe',
        description='adb_executable_help',
    )
    replace_adb: bool = Switch.field(
        default=True,
        description='replace_adb_help',
    )
    auto_connect: bool = Switch.field(
        default=True,
        description='auto_connect_help',
    )
    install_uiautomator2: bool = Switch.field(
        default=True,
        description='install_uiautomator2_help',
    )


class OcrGroup(GroupBase):
    """OCR server mode and address."""

    use_ocr_server: bool = Switch.field(
        default=False,
        description='use_ocr_server_help',
    )
    start_ocr_server: bool = Switch.field(
        default=False,
        description='start_ocr_server_help',
    )
    ocr_server_port: int = Input.int(
        default=22268,
        ge=1,
        le=65535,
        description='ocr_server_port_help',
    )
    ocr_client_address: str = Input.str(
        default='127.0.0.1:22268',
        description='ocr_client_address_help',
    )


class UpdateGroup(GroupBase):
    """Self update and scheduled restart."""

    enable_reload: bool = Switch.field(
        default=True,
        description='enable_reload_help',
    )
    check_update_interval: int = Input.int(
        default=5,
        ge=0,
        description='check_update_interval_help',
    )
    auto_restart_time: Time | None = Time.field(
        default=Time(3, 50),
        description='auto_restart_time_help',
    )


class RemoteAccessGroup(GroupBase):
    """SSH reverse tunnel remote access."""

    enable_remote_access: bool = Switch.field(
        default=False,
        description='enable_remote_access_help',
    )
    ssh_user: str | None = Input.str(
        default=None,
        description='ssh_user_help',
    )
    ssh_server: str | None = Input.str(
        default=None,
        description='ssh_server_help',
    )
    ssh_executable: str | None = Input.str(
        default='ssh',
        description='ssh_executable_help',
    )


class WebuiGroup(GroupBase):
    """Local server, web UI presentation and startup behaviour."""

    host: str = Input.str(
        default='0.0.0.0',
        description='host_help',
    )
    port: int = Input.int(
        default=22288,
        ge=1,
        le=65535,
        description='port_help',
    )
    language: Language = Option.field(
        default=Language.ZH_CN,
        description='language_help',
    )
    theme: Theme = Option.field(
        default=Theme.DEFAULT,
        description='theme_help',
    )
    dpi_scaling: bool = Switch.field(
        default=True,
        description='dpi_scaling_help',
    )
    password: str | None = Input.secret_str(
        default=None,
        description='password_help',
    )
    cdn: str | bool = Input.str(
        default=False,
        description='cdn_help',
    )
    run: str | None = Input.str(
        default=None,
        description='run_help',
    )
