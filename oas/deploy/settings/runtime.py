"""Runtime access to the deploy settings file.

``SettingsRuntime`` is the single entry point for reading ``config/deploy.json``.
Every access re-reads and re-validates the file, so a write made by another
process (the web UI, the updater, a worker) is visible on the next read without a
restart.  That costs one file read and one validation per access, so code that
needs several values should bind ``data`` to a local variable once.

A missing file is created from the model defaults on the first access.  A file
that exists but cannot be parsed or validated raises instead of being replaced by
the defaults: silently dropping the user's values is worse than a loud failure.
"""

from oas.deploy.settings.models import Settings
from oas.ext import env
from oas.ext.file.jsonfile import json_loads, write_json
from oas.ext.path.atomic import atomic_read_bytes
from oas.ext.singleton import Singleton


DEPLOY_CONFIG = env.OAS_ROOT / 'oas' /'config' / 'deploy.json'


class SettingsRuntime(metaclass=Singleton):
    """File backed deploy settings, re-read and validated on every access."""

    def __init__(self, file: str = DEPLOY_CONFIG):
        """
        Args:
            file (str): Deploy settings file.  Defaults to ``deploy.json``
                under :data:`oas.ext.env.PROJECT_ROOT`.
        """
        self.file = file

    @property
    def data(self) -> Settings:
        """
        Returns:
            Settings: Validated deploy settings of the file at this moment.
        """
        try:
            raw = atomic_read_bytes(self.file)
        except FileNotFoundError:
            # First access, or the user deleted the file: write model defaults.
            data = Settings()
            write_json(self.file, data.to_dict(), skip_same=True)
            return data

        # JSONDecodeError and ValidationError propagate on purpose.
        return Settings.from_dict(json_loads(raw))
