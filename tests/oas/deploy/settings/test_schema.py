"""Tests for the deploy settings schema generator."""

from pathlib import Path

from oas.deploy.settings import schema as schema_module
from oas.deploy.settings.models import Settings
from oas.deploy.settings.schema import SCHEMA_FILE, generate_schema, write_schema
from oas.ext.file.jsonfile import json_loads
from oas.ext.path.atomic import atomic_read_bytes
from oas.testing.filesystem import fs  # noqa: F401


def test_generate_schema_is_the_pydantic_export():
    assert generate_schema() == Settings.model_json_schema()


def test_schema_file_sits_next_to_the_generator():
    assert Path(SCHEMA_FILE) == Path(schema_module.__file__).resolve().with_name(
        'schema.json'
    )


def test_committed_schema_json_is_in_sync():
    # ``schema.json`` is a committed artifact; regenerate it with
    # ``python -m oas.deploy.settings.schema`` whenever the model changes.
    assert json_loads(atomic_read_bytes(SCHEMA_FILE)) == generate_schema()


def test_write_schema_writes_and_skips_an_identical_file(fs):
    target = f'{fs.root_dir.path}/schema.json'

    assert write_schema(file=target) is True
    assert json_loads(atomic_read_bytes(target)) == generate_schema()
    # The content did not change, so a rewrite is skipped.
    assert write_schema(file=target) is False
    assert write_schema(file=target, skip_same=False) is True
