"""Generate the JSON Schema of the deploy settings.

``schema.json`` is a build artifact: it is exported verbatim from the Pydantic
JSON Schema of ``Settings`` and committed, so consumers that cannot run Pydantic
(the Electron main process, the web UI) read the static file instead of
importing the model.  The consuming side parses this file itself, nothing here
reshapes the export.

Regenerate with::

    python -m oas.deploy.settings.schema
"""

from pathlib import Path

from oas.deploy.settings.models import Settings
from oas.ext.file.jsonfile import write_json

SCHEMA_FILE = str(Path(__file__).resolve().with_name('schema.json'))


def generate_schema() -> dict:
    """
    Returns:
        dict: JSON Schema of ``Settings``, as exported by Pydantic.
    """
    return Settings.model_json_schema()


def write_schema(file=SCHEMA_FILE, skip_same=True) -> bool:
    """
    Args:
        file (str): Target file path.
        skip_same (bool): True to skip writing when the file is unchanged.

    Returns:
        bool: If write
    """
    return write_json(file, generate_schema(), skip_same=skip_same)


if __name__ == '__main__':
    print(f'{SCHEMA_FILE}: {"written" if write_schema() else "up-to-date"}')
