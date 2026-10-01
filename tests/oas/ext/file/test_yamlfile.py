"""
Tests for oas.ext.file.yamlfile.

Covers the low level serialization helpers (yaml_loads / yaml_dumps)
and the file IO helpers (read_yaml / write_yaml / format_yaml).

The str_presenter is exercised through yaml_dumps: multiline strings are
emitted as literal block scalars, single-line strings stay plain.
"""
import pytest
import yaml

from oas.ext.file.yamlfile import format_yaml, read_yaml, write_yaml, yaml_dumps, yaml_loads
from oas.testing.filesystem import fs  # noqa: F401


class TestYamlLoads:
    """Test cases for the yaml_loads function"""

    def test_loads_dict(self):
        assert yaml_loads(b"a: 1\n") == {"a": 1}

    def test_loads_nested(self):
        assert yaml_loads(b"a:\n  b:\n  - 1\n  - 2\n") == {"a": {"b": [1, 2]}}

    def test_loads_unicode_bytes(self):
        assert yaml_loads("name: 测试\n".encode()) == {"name": "测试"}

    def test_loads_list(self):
        assert yaml_loads(b"- 1\n- 2\n- 3\n") == [1, 2, 3]

    @pytest.mark.parametrize("data, expected", [
        (b"42\n", 42),
        (b"true\n", True),
        (b"null\n", None),
        (b"hello\n", "hello"),
    ])
    def test_loads_scalars(self, data, expected):
        assert yaml_loads(data) == expected

    @pytest.mark.parametrize("data", [b"", b"\n", b"# comment only\n"])
    def test_loads_empty(self, data):
        """Empty and comment-only streams parse to None"""
        assert yaml_loads(data) is None

    def test_loads_invalid_raises(self):
        """Invalid yaml raises yaml.YAMLError, callers decide how to handle it"""
        with pytest.raises(yaml.YAMLError):
            yaml_loads(b"a: [unclosed")

    def test_loads_non_utf8_raises(self):
        with pytest.raises(yaml.YAMLError):
            yaml_loads(b"a: \xff\xfe\n")

    def test_loads_multiple_documents_raises(self):
        """yaml_dumps() of a list produces multiple documents,
        yaml_loads() accepts a single document only"""
        with pytest.raises(yaml.YAMLError):
            yaml_loads(yaml_dumps([1, 2, 3]))


class TestYamlDumps:
    """Test cases for the yaml_dumps function"""

    def test_returns_bytes(self):
        assert isinstance(yaml_dumps({"a": 1}), bytes)

    def test_simple_dict(self):
        assert yaml_dumps({"a": 1}) == b"a: 1\n"

    def test_nested(self):
        assert yaml_dumps({"a": {"b": [1, 2]}, "c": None, "flag": True}) == (
            b"a:\n"
            b"  b:\n"
            b"  - 1\n"
            b"  - 2\n"
            b"c: null\n"
            b"flag: true\n"
        )

    def test_sort_keys_false(self):
        """Insertion order is kept"""
        assert yaml_dumps({"b": 1, "a": 2, "c": 3}) == b"b: 1\na: 2\nc: 3\n"

    def test_unicode(self):
        """BMP unicode characters are kept unescaped"""
        assert yaml_dumps({"name": "测试"}) == "name: 测试\n".encode()

    def test_emoji_round_trip(self):
        """Non-BMP characters are escaped when dumped but load back correctly"""
        data = {"emoji": "🚀"}
        assert yaml_loads(yaml_dumps(data)) == data

    def test_round_trip(self):
        data = {
            "name": "test",
            "values": [1, 2, 3],
            "nested": {"flag": True, "none": None},
            "unicode": "测试",
        }
        assert yaml_loads(yaml_dumps(data)) == data

    @pytest.mark.parametrize("value, expected", [
        (42, b"42\n"),
        ("hello", b"hello\n"),
        (True, b"true\n"),
        (None, b"null\n"),
    ])
    def test_non_list_object_wrapped(self, value, expected):
        """Non-list objects are wrapped into a single document"""
        assert yaml_dumps(value) == expected

    def test_empty_dict(self):
        assert yaml_dumps({}) == b"{}\n"

    def test_empty_list(self):
        """A list is dumped as multiple documents, an empty list has none"""
        assert yaml_dumps([]) == b""

    def test_list_dumped_as_multiple_documents(self):
        assert yaml_dumps([1, 2, 3]) == b"1\n--- 2\n--- 3\n"

    def test_list_of_dicts_dumped_as_multiple_documents(self):
        assert yaml_dumps([{"a": 1}, {"b": 2}]) == b"a: 1\n---\nb: 2\n"

    @pytest.mark.parametrize("value, expected", [
        ("a\nb", b"s: |-\n  a\n  b\n"),
        ("a\nb\n", b"s: |\n  a\n  b\n"),
        ("a\n\nb", b"s: |-\n  a\n\n  b\n"),
        ("a\nb\n\n", b"s: |+\n  a\n  b\n\n...\n"),
        ("single", b"s: single\n"),
        ("", b"s: ''\n"),
    ])
    def test_multiline_string_literal_block(self, value, expected):
        """Multiline strings are emitted as literal block scalars"""
        assert yaml_dumps({"s": value}) == expected

    @pytest.mark.parametrize("value", [
        "a\nb",
        "a\nb\n",
        "a\n\nb",
        "a\nb\n\n",
        "single",
        "",
        "with unicode 测试\nsecond line",
    ])
    def test_multiline_round_trip(self, value):
        assert yaml_loads(yaml_dumps({"s": value})) == {"s": value}


class TestReadYaml:
    """Test cases for the read_yaml function"""

    def test_read_existing_file(self, fs):
        fs.create_file("/data.yaml", contents="name: test\nvalue: 42\n")
        assert read_yaml("/data.yaml") == {"name": "test", "value": 42}

    def test_read_unicode(self, fs):
        fs.create_file("/data.yaml", contents="name: 测试\n")
        assert read_yaml("/data.yaml") == {"name": "测试"}

    def test_read_top_level_list(self, fs):
        fs.create_file("/data.yaml", contents="- 1\n- 2\n- 3\n")
        assert read_yaml("/data.yaml") == [1, 2, 3]

    def test_read_missing_file_returns_default(self, fs):
        assert read_yaml("/missing.yaml") == {}

    def test_read_missing_file_custom_factory(self, fs):
        assert read_yaml("/missing.yaml", default_factory=list) == []

    def test_read_invalid_yaml_returns_default(self, fs):
        fs.create_file("/data.yaml", contents="port: [unclosed\n")
        assert read_yaml("/data.yaml") == {}

    def test_read_invalid_yaml_custom_factory(self, fs):
        fs.create_file("/data.yaml", contents="port: [unclosed\n")
        assert read_yaml("/data.yaml", default_factory=list) == []

    def test_read_non_utf8_returns_default(self, fs):
        # Invalid utf-8 bytes raise yaml.ReaderError, a yaml.YAMLError subclass
        fs.create_file("/data.yaml", contents=b"port: \xff\xfe\n")
        assert read_yaml("/data.yaml") == {}

    def test_read_multiple_documents_returns_default(self, fs):
        # A multi-document stream raises yaml.ComposerError, also a yaml.YAMLError
        fs.create_file("/data.yaml", contents="a: 1\n---\nb: 2\n")
        assert read_yaml("/data.yaml") == {}

    def test_read_empty_file_returns_none(self, fs):
        """An empty file parses to None, which is not an error"""
        fs.create_file("/data.yaml", contents="")
        assert read_yaml("/data.yaml") is None


class TestWriteYaml:
    """Test cases for the write_yaml function"""

    def _read(self, fs, path):
        return fs.get_file(path).content

    def test_write_creates_file(self, fs):
        assert write_yaml("/data.yaml", {"a": 1}) is True
        assert self._read(fs, "/data.yaml") == yaml_dumps({"a": 1})

    def test_write_auto_creates_parent_dir(self, fs):
        assert write_yaml("/a/b/c/data.yaml", {"a": 1}) is True
        assert self._read(fs, "/a/b/c/data.yaml") == yaml_dumps({"a": 1})

    def test_write_overwrites_existing(self, fs):
        fs.create_file("/data.yaml", contents="old: 1\n")
        assert write_yaml("/data.yaml", {"new": 2}) is True
        assert self._read(fs, "/data.yaml") == yaml_dumps({"new": 2})

    def test_write_unicode(self, fs):
        assert write_yaml("/data.yaml", {"name": "测试"}) is True
        assert self._read(fs, "/data.yaml") == "name: 测试\n".encode()

    def test_write_multiline(self, fs):
        assert write_yaml("/data.yaml", {"desc": "line1\nline2"}) is True
        assert self._read(fs, "/data.yaml") == b"desc: |-\n  line1\n  line2\n"

    def test_write_scalar(self, fs):
        assert write_yaml("/data.yaml", 42) is True
        assert self._read(fs, "/data.yaml") == b"42\n"
        assert read_yaml("/data.yaml") == 42

    def test_write_formatter(self, fs):
        def formatter(data):
            return b"# comment\n" + data

        assert write_yaml("/data.yaml", {"a": 1}, formatter=formatter) is True
        assert self._read(fs, "/data.yaml") == b"# comment\na: 1\n"

    def test_write_skip_same_same_content_skips(self, fs):
        write_yaml("/data.yaml", {"a": 1})
        assert write_yaml("/data.yaml", {"a": 1}, skip_same=True) is False

    def test_write_skip_same_different_content_writes(self, fs):
        write_yaml("/data.yaml", {"a": 1})
        assert write_yaml("/data.yaml", {"a": 2}, skip_same=True) is True
        assert self._read(fs, "/data.yaml") == yaml_dumps({"a": 2})

    def test_write_skip_same_missing_file_writes(self, fs):
        assert write_yaml("/data.yaml", {"a": 1}, skip_same=True) is True

    def test_write_skip_same_with_formatter(self, fs):
        """The formatter is applied before the skip_same comparison"""

        def formatter(data):
            return data.replace(b"a: 1", b"a: 100")

        assert write_yaml("/data.yaml", {"a": 1}, formatter=formatter) is True
        assert write_yaml("/data.yaml", {"a": 1}, skip_same=True, formatter=formatter) is False

    def test_write_without_skip_same_always_writes(self, fs):
        write_yaml("/data.yaml", {"a": 1})
        assert write_yaml("/data.yaml", {"a": 1}) is True

    def test_write_round_trip(self, fs):
        data = {"name": "test", "values": [1, 2, 3], "nested": {"flag": True}}
        write_yaml("/data.yaml", data)
        assert read_yaml("/data.yaml") == data


class TestFormatYaml:
    """Test cases for the format_yaml function"""

    def _read(self, fs, path):
        return fs.get_file(path).content

    def test_missing_file_returns_false(self, fs):
        assert format_yaml("/missing.yaml", lambda data: data) is False

    def test_invalid_yaml_returns_false(self, fs):
        """Only valid yaml is formatted"""
        contents = b"port: [unclosed\n"
        fs.create_file("/data.yaml", contents=contents)
        assert format_yaml("/data.yaml", lambda data: data.upper()) is False
        assert self._read(fs, "/data.yaml") == contents

    def test_same_content_returns_false(self, fs):
        contents = b"a: 1\n"
        fs.create_file("/data.yaml", contents=contents)
        assert format_yaml("/data.yaml", lambda data: data) is False
        assert self._read(fs, "/data.yaml") == contents

    def test_formatted_writes(self, fs):
        fs.create_file("/data.yaml", contents=b"a: 1\n")
        assert format_yaml("/data.yaml", lambda data: b"# header\n" + data) is True
        assert self._read(fs, "/data.yaml") == b"# header\na: 1\n"

    def test_formatted_content_stays_valid(self, fs):
        fs.create_file("/data.yaml", contents=b"a: 1\n")
        format_yaml("/data.yaml", lambda data: data.replace(b"1", b"2"))
        assert read_yaml("/data.yaml") == {"a": 2}
