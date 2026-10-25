"""Top level deploy configuration model.

``Settings`` is the single deploy settings object: a Task whose fields are the
reusable Groups from :mod:`oas.deploy.settings.groups`.  It is deliberately
modelled as a Task so the deploy settings reuse the Group composition, JSON
Schema export and registry machinery already built for task configuration.
"""

from pydantic import Field

from oas.config.models.tasks import TaskBase
from oas.deploy.settings.groups import (
    AdbGroup,
    GitGroup,
    OcrGroup,
    PythonGroup,
    RemoteAccessGroup,
    UpdateGroup,
    WebuiGroup,
)


class Settings(TaskBase):
    """Deploy settings, formerly the flat ``ConfigModel`` of deploy.yaml."""

    git: GitGroup = Field(
        default_factory=GitGroup,
        description='git_group_help',
    )
    python: PythonGroup = Field(
        default_factory=PythonGroup,
        description='python_group_help',
    )
    adb: AdbGroup = Field(
        default_factory=AdbGroup,
        description='adb_group_help',
    )
    ocr: OcrGroup = Field(
        default_factory=OcrGroup,
        description='ocr_group_help',
    )
    update: UpdateGroup = Field(
        default_factory=UpdateGroup,
        description='update_group_help',
    )
    remote_access: RemoteAccessGroup = Field(
        default_factory=RemoteAccessGroup,
        description='remote_access_group_help',
    )
    webui: WebuiGroup = Field(
        default_factory=WebuiGroup,
        description='webui_group_help',
    )
