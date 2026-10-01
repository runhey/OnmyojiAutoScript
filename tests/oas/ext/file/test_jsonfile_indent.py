import json
from datetime import datetime

import pytest

from oas.ext.file.jsonfile import NoIndent, NoIndentNoSpace, json_dumps_custom_indent


class TestJsonDumpsCustomIndent:
    """Test cases for json_dumps_custom_indent function.

    Each test asserts the complete output with a multiline bytes literal, so a
    regression in any part of the formatting (indentation, separators, inline
    content) fails the whole assertion.
    """

    def test_basic_noindent_functionality(self):
        """Basic NoIndent functionality: inline content with regular indent"""
        data = {
            'name': 'test',
            'coordinates': NoIndent([10, 20, 30, 40]),
            'description': 'This is a test'
        }

        result = json_dumps_custom_indent(data)

        # Should return bytes
        assert isinstance(result, bytes), "Function should return bytes"

        # NoIndent should be on one line, regular content properly indented
        assert result == b"""\
{
  "name": "test",
  "coordinates": [10, 20, 30, 40],
  "description": "This is a test"
}"""

    def test_basic_noindent_nospace_functionality(self):
        """Basic NoIndentNoSpace functionality: no spaces in inline content"""
        data = {
            'name': 'test',
            'color': NoIndentNoSpace([255, 128, 64]),
            'metadata': {'version': 1}
        }

        result = json_dumps_custom_indent(data)

        # Should return bytes
        assert isinstance(result, bytes), "Function should return bytes"

        # NoIndentNoSpace should be on one line without spaces
        assert result == b"""\
{
  "name": "test",
  "color": [255,128,64],
  "metadata": {
    "version": 1
  }
}"""

    def test_parent_indentation_no_effect(self):
        """Parent indentation should not affect NoIndent/NoIndentNoSpace"""
        data = {
            'level1': {
                'level2': {
                    'level3': {
                        'noindent_array': NoIndent([1, 2, 3, 4]),
                        'nospace_array': NoIndentNoSpace(['a', 'b', 'c']),
                        'normal_data': 'should be indented'
                    }
                }
            }
        }

        result = json_dumps_custom_indent(data)

        # Deep nesting should not affect NoIndent behavior,
        # normal content should still be properly nested (8 spaces for level 3)
        assert result == b"""\
{
  "level1": {
    "level2": {
      "level3": {
        "noindent_array": [1, 2, 3, 4],
        "nospace_array": ["a","b","c"],
        "normal_data": "should be indented"
      }
    }
  }
}"""

    def test_replacement_no_side_effects(self):
        """Replacement should not affect other content"""
        # Use strings that might contain patterns similar to placeholders
        data = {
            'suspicious_string': 'No|1NdEnτ-12345 and τ characters',
            'array_with_noindent': NoIndent([1, 2, 3]),
            'another_string': 'Contains placeholder-like text No|1NdEnτ-n0SpaCæ-67890',
            'normal_array': [4, 5, 6]
        }

        result = json_dumps_custom_indent(data)

        # Original suspicious strings should remain unchanged,
        # NoIndent should work correctly, normal array should be indented.
        # str literal + encode: bytes literals are ASCII-only in Python.
        assert result == """\
{
  "suspicious_string": "No|1NdEnτ-12345 and τ characters",
  "array_with_noindent": [1, 2, 3],
  "another_string": "Contains placeholder-like text No|1NdEnτ-n0SpaCæ-67890",
  "normal_array": [
    4,
    5,
    6
  ]
}""".encode('utf-8')

    def test_nested_noindent_usage(self):
        """Nested usage of NoIndent/NoIndentNoSpace"""
        data = {
            'outer': NoIndent({
                'inner_normal': [1, 2, 3],
                'inner_noindent': NoIndent(['a', 'b', 'c']),
                'inner_nospace': NoIndentNoSpace({'x': 1, 'y': 2})
            }),
            'mixed_nesting': {
                'level1': NoIndentNoSpace([
                    NoIndent({'nested': True}),
                    'normal_string'
                ])
            }
        }

        result = json_dumps_custom_indent(data)

        # Outer NoIndent dict is compacted, nested NoIndent/NoIndentNoSpace
        # keep their own formatting, inner NoIndent keeps ", " separators
        # inside the nospace array
        assert result == b"""\
{
  "outer": {"inner_normal": [1, 2, 3], "inner_noindent": ["a", "b", "c"], "inner_nospace": {"x":1,"y":2}},
  "mixed_nesting": {
    "level1": [{"nested": true},"normal_string"]
  }
}"""

    def test_default_parameter_propagation(self):
        """default=str and other parameters should propagate to inline content"""
        # Test with datetime objects that need custom serialization
        test_date = datetime(2023, 12, 25, 10, 30, 45)

        data = {
            'regular_date': test_date,
            'noindent_dates': NoIndent([test_date, test_date]),
            'nospace_date_dict': NoIndentNoSpace({
                'created': test_date,
                'modified': test_date
            })
        }

        result = json_dumps_custom_indent(data)

        # All datetime objects should be serialized as strings,
        # in regular fields and inside inline content
        assert result == b"""\
{
  "regular_date": "2023-12-25 10:30:45",
  "noindent_dates": ["2023-12-25 10:30:45", "2023-12-25 10:30:45"],
  "nospace_date_dict": {"created":"2023-12-25 10:30:45","modified":"2023-12-25 10:30:45"}
}"""

    def test_empty_and_edge_cases(self):
        """Edge cases: empty objects, None values, etc."""
        data = {
            'empty_noindent': NoIndent([]),
            'empty_nospace': NoIndentNoSpace({}),
            'none_in_noindent': NoIndent([None, 'test', None]),
            'complex_nested': {
                'data': NoIndent({
                    'empty_list': [],
                    'empty_dict': {},
                    'none_value': None
                })
            }
        }

        result = json_dumps_custom_indent(data)

        # Empty structures and None values should be preserved
        assert result == b"""\
{
  "empty_noindent": [],
  "empty_nospace": {},
  "none_in_noindent": [null, "test", null],
  "complex_nested": {
    "data": {"empty_list": [], "empty_dict": {}, "none_value": null}
  }
}"""

    def test_mixed_usage_comprehensive(self):
        """Comprehensive test mixing all features"""
        data = {
            'config': {
                'window_size': NoIndent([1920, 1080]),
                'colors': {
                    'primary': NoIndentNoSpace([255, 0, 0]),
                    'secondary': NoIndentNoSpace([0, 255, 0]),
                    'palette': NoIndent([
                        NoIndentNoSpace([100, 100, 100]),
                        NoIndentNoSpace([200, 200, 200])
                    ])
                },
                'settings': {
                    'nested': {
                        'deep': {
                            'coordinates': NoIndent([10, 20, 30, 40])
                        }
                    }
                }
            },
            'metadata': NoIndent({
                'version': '1.0',
                'author': 'test',
                'tags': NoIndentNoSpace(['tag1', 'tag2', 'tag3'])
            })
        }

        result = json_dumps_custom_indent(data)

        # Nested NoIndent within NoIndent should work,
        # deep nesting should not affect NoIndent
        assert result == b"""\
{
  "config": {
    "window_size": [1920, 1080],
    "colors": {
      "primary": [255,0,0],
      "secondary": [0,255,0],
      "palette": [[100,100,100], [200,200,200]]
    },
    "settings": {
      "nested": {
        "deep": {
          "coordinates": [10, 20, 30, 40]
        }
      }
    }
  },
  "metadata": {"version": "1.0", "author": "test", "tags": ["tag1","tag2","tag3"]}
}"""

    def test_unicode_handling(self):
        """Unicode characters in NoIndent/NoIndentNoSpace content"""
        data = {
            'unicode_noindent': NoIndent(['测试', '🚀', 'café']),
            'unicode_nospace': NoIndentNoSpace({'中文': '测试', 'emoji': '🎉'}),
            'regular_unicode': {'标题': '测试文档'}
        }

        result = json_dumps_custom_indent(data)

        # Unicode should be preserved correctly in UTF-8 encoding.
        # str literal + encode: bytes literals are ASCII-only in Python.
        assert result == """\
{
  "unicode_noindent": ["测试", "🚀", "café"],
  "unicode_nospace": {"中文":"测试","emoji":"🎉"},
  "regular_unicode": {
    "标题": "测试文档"
  }
}""".encode('utf-8')

    def test_bytes_output_format(self):
        """Output is properly formatted UTF-8 bytes and valid JSON"""
        data = {
            'simple': NoIndent([1, 2, 3]),
            'nested': {
                'array': NoIndentNoSpace(['a', 'b', 'c'])
            }
        }

        result = json_dumps_custom_indent(data)

        # Should be bytes
        assert isinstance(result, bytes)

        # Should be valid UTF-8
        try:
            decoded = result.decode('utf-8')
        except UnicodeDecodeError:
            pytest.fail("Result is not valid UTF-8")

        # Should be valid JSON when decoded
        try:
            parsed = json.loads(decoded)
            assert parsed['simple'] == [1, 2, 3]
            assert parsed['nested']['array'] == ['a', 'b', 'c']
        except json.JSONDecodeError:
            pytest.fail("Result is not valid JSON")

    def test_scalar_noindent_values(self):
        """NoIndent wrapping scalar values should be inlined without quotes"""
        data = {
            'int_value': NoIndent(5),
            'str_value': NoIndent('abc'),
            'bool_value': NoIndent(True),
            'none_value': NoIndent(None),
        }

        result = json_dumps_custom_indent(data)

        assert result == b"""\
{
  "int_value": 5,
  "str_value": "abc",
  "bool_value": true,
  "none_value": null
}"""

    def test_noindent_dict_compact_format(self):
        """NoIndent dict should be compact with default separators (', ')"""
        data = {'config': NoIndent({'width': 1920, 'height': 1080})}

        result = json_dumps_custom_indent(data)

        assert result == b"""\
{
  "config": {"width": 1920, "height": 1080}
}"""

    def test_no_placeholder_left_in_output(self):
        """No placeholder text should remain in the final output"""
        data = {
            'a': NoIndent([1, 2]),
            'b': NoIndentNoSpace([3, 4]),
            'nested': {'c': NoIndent([5, 6])},
        }

        result = json_dumps_custom_indent(data)

        assert result == b"""\
{
  "a": [1, 2],
  "b": [3,4],
  "nested": {
    "c": [5, 6]
  }
}"""

        # No placeholder text should remain
        assert b'No|1NdEn' not in result

    def test_nested_nospace_with_noindent_exact(self):
        """NoIndentNoSpace containing NoIndent keeps exact per-type formatting"""
        data = {
            'mixed': NoIndentNoSpace([
                NoIndent({'nested': True}),
                'normal_string',
            ])
        }

        result = json_dumps_custom_indent(data)

        # Inner NoIndent keeps its own ", " separators inside the nospace array
        assert result == b"""\
{
  "mixed": [{"nested": true},"normal_string"]
}"""

    def test_top_level_noindent(self):
        """A top-level NoIndent object is inlined as the whole document"""
        result = json_dumps_custom_indent(NoIndent([1, 2, 3]))

        assert result == b'[1, 2, 3]'

    def test_noindent_special_characters(self):
        """Strings with quotes or newlines inside NoIndent are escaped correctly"""
        data = {'value': NoIndent(['a"b', 'line1\nline2'])}

        result = json_dumps_custom_indent(data)

        assert result == b"""\
{
  "value": ["a\\"b", "line1\\nline2"]
}"""
