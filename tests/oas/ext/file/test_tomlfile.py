"""
Tests for oas.ext.file.tomlfile.

Covers the adaptive parser lookup (get_tomllib) and the parsing helper
(toml_loads).
"""

import pytest

from oas.ext.file.tomlfile import toml_loads


class TestTomlLoads:
    """Test cases for the toml_loads function"""

    def test_uses_stdlib_tomllib(self):
        """The parser is the standard library tomllib of Python 3.11+"""
        import tomllib

        assert toml_loads('[a]\nb = 1\n') == tomllib.loads('[a]\nb = 1\n')

    @pytest.mark.parametrize(
        'data',
        [
            '[project]\nname = "oas"\n',
            b'[project]\nname = "oas"\n',
            bytearray(b'[project]\nname = "oas"\n'),
        ],
    )
    def test_input_types(self, data):
        """A document is parsed from str, bytes and bytearray"""
        assert toml_loads(data) == {'project': {'name': 'oas'}}

    def test_nested(self):
        assert toml_loads("""\
[project]
name = "oas"
dependencies = ["msgspec", "starlette"]

[project.optional-dependencies]
image = ["numpy", "opencv-python-headless"]

[[tool.poetry.source]]
name = "pypi"
priority = "primary"
""") == {
            'project': {
                'name': 'oas',
                'dependencies': ['msgspec', 'starlette'],
                'optional-dependencies': {
                    'image': ['numpy', 'opencv-python-headless'],
                },
            },
            'tool': {
                'poetry': {
                    'source': [{'name': 'pypi', 'priority': 'primary'}],
                },
            },
        }

    def test_unicode_bytes(self):
        """Bytes are decoded as UTF-8, as the TOML specification requires"""
        assert toml_loads('[project]\ndescription = "测试"\n'.encode('utf-8')) == {
            'project': {'description': '测试'},
        }

    def test_empty_document(self):
        assert toml_loads('') == {}

    @pytest.mark.parametrize(
        'data',
        [
            '[project',
            b'[project',
            'name = "oas"\nname = "other"\n',
        ],
    )
    def test_invalid_document_raises_value_error(self, data):
        """TOMLDecodeError is a ValueError, callers decide how to handle it"""
        with pytest.raises(ValueError):
            toml_loads(data)

    def test_invalid_utf8_raises(self):
        with pytest.raises(UnicodeDecodeError):
            toml_loads(b'[project]\nname = "\xff"\n')
