"""
Tests for oas.ext.file.jsonfile.

Covers the low level serialization helpers (json_loads / json_dumps),
the ValueProxy wrapper, and the file IO helpers
(read_json / write_json / write_json_custom_indent).

The custom indent mechanism (NoIndent / NoIndentNoSpace /
CustomIndentEncoder / json_dumps_custom_indent) is covered in
test_jsonfile_indent.py.
"""
import json
from datetime import datetime

import pytest

from oas.ext.file.jsonfile import (
    NoIndent, ValueProxy, json_dumps, json_dumps_custom_indent, json_loads, read_json, write_json,
    write_json_custom_indent
)
from oas.testing.filesystem import fs  # noqa: F401


class TestJsonLoads:
    """Test cases for the json_loads function"""

    def test_loads_bytes(self):
        assert json_loads(b'{"a": 1}') == {"a": 1}

    def test_loads_unicode_bytes(self):
        assert json_loads('{"name": "测试"}'.encode()) == {"name": "测试"}

    def test_loads_list(self):
        assert json_loads(b"[1, 2, 3]") == [1, 2, 3]

    def test_loads_invalid_raises(self):
        """Invalid json raises JSONDecodeError, callers decide how to handle it"""
        with pytest.raises(json.JSONDecodeError):
            json_loads(b"not json")


class TestJsonDumps:
    """Test cases for the json_dumps function"""

    def test_returns_bytes(self):
        assert isinstance(json_dumps({"a": 1}), bytes)

    def test_indent_2(self):
        assert json_dumps({"a": 1}) == b'{\n  "a": 1\n}'

    def test_ensure_ascii_false(self):
        """Non-ascii characters are not escaped"""
        assert json_dumps({"name": "测试"}) == '{\n  "name": "测试"\n}'.encode()

    def test_sort_keys_false(self):
        """Insertion order is kept"""
        data = {"b": 1, "a": 2, "c": 3}
        result = json_dumps(data)
        assert result.index(b'"b"') < result.index(b'"a"') < result.index(b'"c"')

    def test_default_str(self):
        """Objects that cannot be serialized are converted with str()"""
        test_date = datetime(2023, 12, 25, 10, 30, 45)  # noqa: DTZ001
        result = json_dumps({"date": test_date})
        assert result == f'{{\n  "date": "{test_date}"\n}}'.encode()

    def test_round_trip(self):
        data = {
            "name": "test",
            "values": [1, 2, 3],
            "nested": {"flag": True, "none": None},
            "unicode": "测试🚀",
        }
        assert json_loads(json_dumps(data)) == data


class TestValueProxy:
    """Test cases for the ValueProxy wrapper class"""

    def test_init_and_value(self):
        proxy = ValueProxy([1, 2, 3])
        assert proxy.value == [1, 2, 3]

    def test_str(self):
        assert str(ValueProxy(42)) == "42"
        assert str(ValueProxy([1, 2])) == "[1, 2]"

    def test_repr(self):
        # repr() wraps the f-string result in quotes
        assert repr(ValueProxy(42)) == "'ValueProxy(42)'"

    def test_bool(self):
        assert bool(ValueProxy(1)) is True
        assert bool(ValueProxy(0)) is False
        assert bool(ValueProxy([])) is False

    def test_getitem(self):
        assert ValueProxy([1, 2, 3])[1] == 2

    def test_setitem(self):
        proxy = ValueProxy([1, 2, 3])
        proxy[1] = 99
        assert proxy.value == [1, 99, 3]

    def test_delitem(self):
        proxy = ValueProxy([1, 2, 3])
        del proxy[1]
        assert proxy.value == [1, 3]

    def test_eq(self):
        assert ValueProxy([1, 2]) == [1, 2]
        assert ValueProxy(1) == 1
        assert ValueProxy([1, 2]) != [2, 1]

    def test_iter(self):
        assert list(ValueProxy([1, 2, 3])) == [1, 2, 3]

    def test_len(self):
        assert len(ValueProxy([1, 2, 3])) == 3

    def test_contains(self):
        proxy = ValueProxy([1, 2, 3])
        assert 2 in proxy
        assert 9 not in proxy

    def test_items_keys_values(self):
        proxy = ValueProxy({"a": 1, "b": 2})
        assert proxy.items() == {"a": 1, "b": 2}.items()
        assert list(proxy.keys()) == ["a", "b"]
        assert list(proxy.values()) == [1, 2]

    def test_get(self):
        proxy = ValueProxy({"a": 1})
        assert proxy.get("a") == 1
        assert proxy.get("missing") is None
        assert proxy.get("missing", 42) == 42


class TestReadJson:
    """Test cases for the read_json function"""

    def test_read_existing_file(self, fs):
        fs.create_file("/data.json", contents='{"name": "test", "value": 42}')
        assert read_json("/data.json") == {"name": "test", "value": 42}

    def test_read_unicode(self, fs):
        fs.create_file("/data.json", contents='{"name": "测试"}')
        assert read_json("/data.json") == {"name": "测试"}

    def test_read_top_level_list(self, fs):
        fs.create_file("/data.json", contents="[1, 2, 3]")
        assert read_json("/data.json") == [1, 2, 3]

    def test_read_missing_file_returns_default(self, fs):
        assert read_json("/missing.json") == {}

    def test_read_missing_file_custom_factory(self, fs):
        assert read_json("/missing.json", default_factory=list) == []

    def test_read_invalid_json_returns_default(self, fs):
        fs.create_file("/data.json", contents="{not valid json")
        assert read_json("/data.json") == {}

    def test_read_invalid_json_custom_factory(self, fs):
        fs.create_file("/data.json", contents="{not valid json")
        assert read_json("/data.json", default_factory=list) == []


class TestWriteJson:
    """Test cases for the write_json function"""

    def _read(self, fs, path):
        return fs.get_file(path).content

    def test_write_creates_file(self, fs):
        assert write_json("/data.json", {"a": 1}) is True
        assert self._read(fs, "/data.json") == json_dumps({"a": 1})

    def test_write_auto_creates_parent_dir(self, fs):
        assert write_json("/a/b/c/data.json", {"a": 1}) is True
        assert self._read(fs, "/a/b/c/data.json") == json_dumps({"a": 1})

    def test_write_overwrites_existing(self, fs):
        fs.create_file("/data.json", contents='{"old": 1}')
        assert write_json("/data.json", {"new": 2}) is True
        assert self._read(fs, "/data.json") == json_dumps({"new": 2})

    def test_write_custom_dumper(self, fs):
        def dumper(obj):
            return json.dumps(obj).encode("utf-8")

        assert write_json("/data.json", {"a": 1}, dumper=dumper) is True
        assert self._read(fs, "/data.json") == b'{"a": 1}'

    def test_write_skip_same_same_content_skips(self, fs):
        write_json("/data.json", {"a": 1})
        assert write_json("/data.json", {"a": 1}, skip_same=True) is False

    def test_write_skip_same_different_content_writes(self, fs):
        write_json("/data.json", {"a": 1})
        assert write_json("/data.json", {"a": 2}, skip_same=True) is True
        assert self._read(fs, "/data.json") == json_dumps({"a": 2})

    def test_write_skip_same_missing_file_writes(self, fs):
        assert write_json("/data.json", {"a": 1}, skip_same=True) is True

    def test_write_without_skip_same_always_writes(self, fs):
        write_json("/data.json", {"a": 1})
        assert write_json("/data.json", {"a": 1}) is True


class TestWriteJsonCustomIndent:
    """Test cases for the write_json_custom_indent function"""

    def test_write_custom_indent_content(self, fs):
        data = {"area": NoIndent([100, 100, 200, 200])}
        assert write_json_custom_indent("/data.json", data) is True
        assert fs.get_file("/data.json").content == json_dumps_custom_indent(data)

    def test_write_custom_indent_round_trip(self, fs):
        """NoIndent content is written inline and read back as plain json"""
        data = {"area": NoIndent([100, 100, 200, 200]), "name": "test"}
        write_json_custom_indent("/data.json", data)
        assert read_json("/data.json") == {"area": [100, 100, 200, 200], "name": "test"}

    def test_write_custom_indent_skip_same(self, fs):
        data = {"area": NoIndent([100, 100, 200, 200])}
        write_json_custom_indent("/data.json", data)
        assert write_json_custom_indent("/data.json", data, skip_same=True) is False
