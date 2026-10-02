import msgspec
from msgspec import Meta, Struct
from typing_extensions import Annotated

from oas.ext.file.yamlconfig import build_help_map, insert_comments, insert_comments_iter, iter_yaml_rows


class Config(Struct):
    """Flat model used in tests."""

    port: int = 8080
    name: str = "server"
    debug: bool = False


class CommentedConfig(Struct):
    """Model with help comments used in tests."""

    port: Annotated[int, Meta(extra={"help": "line 1\nline 2"})] = 8080
    name: Annotated[str, Meta(extra={"help": "server name"})] = "server"


class InnerConfig(Struct):
    """Inner model used in tests."""

    port: Annotated[int, Meta(extra={"help": "inner port"})] = 8080


class OuterConfig(Struct):
    """Outer model used in tests."""

    inner: InnerConfig = msgspec.field(default_factory=InnerConfig)
    name: str = "server"


class TestBuildHelpMap:
    def test_build_help_map(self):
        help_map = build_help_map(CommentedConfig)
        # Multiline help is parsed by _split_help into a list of lines
        assert help_map == {("port",): ["line 1", "line 2"], ("name",): "server name"}

    def test_build_help_map_nested(self):
        help_map = build_help_map(OuterConfig)
        assert help_map == {("inner", "port"): "inner port"}

    def test_build_help_map_same_key_different_levels(self):
        class Inner(Struct):
            port: Annotated[int, Meta(extra={"help": "inner port help"})] = 1

        class Outer(Struct):
            port: Annotated[int, Meta(extra={"help": "outer port help"})] = 2
            inner: Inner = msgspec.field(default_factory=Inner)

        help_map = build_help_map(Outer)
        assert help_map == {
            ("port",): "outer port help",
            ("inner", "port"): "inner port help",
        }

    def test_build_help_map_help_list(self):
        class Model(Struct):
            port: Annotated[int, Meta(extra={"help": ["line 1", "line 2"]})] = 8080

        assert build_help_map(Model) == {("port",): ["line 1", "line 2"]}

    def test_no_help_fields(self):
        assert build_help_map(Config) == {}


class TestIterYamlRows:
    def test_basic(self):
        rows = list(iter_yaml_rows("""\
port: 8080
name: server
"""))
        assert rows == [
            (("port",), "port: 8080"),
            (("name",), "name: server"),
        ]

    def test_nested(self):
        rows = list(iter_yaml_rows("""\
outer:
  port: 8080
"""))
        assert rows == [
            (("outer",), "outer:"),
            (("outer", "port"), "  port: 8080"),
        ]

    def test_same_key_different_levels(self):
        rows = list(iter_yaml_rows("""\
port: 1
inner:
  port: 2
"""))
        assert rows == [
            (("port",), "port: 1"),
            (("inner",), "inner:"),
            (("inner", "port"), "  port: 2"),
        ]

    def test_block_scalar_content_none(self):
        rows = list(iter_yaml_rows("""\
desc: |-
  line1
  line2
port: 8080
"""))
        assert rows == [
            (("desc",), "desc: |-"),
            (None, "  line1"),
            (None, "  line2"),
            (("port",), "port: 8080"),
        ]

    def test_comment_and_empty_none(self):
        rows = list(iter_yaml_rows("""\
# comment

port: 8080
"""))
        assert rows == [
            (None, "# comment"),
            (None, ""),
            (("port",), "port: 8080"),
        ]


class TestInsertCommentsIter:
    def test_comment_before_key(self):
        rows = iter_yaml_rows("""\
port: 8080
""")
        out = list(insert_comments_iter(rows, {("port",): "port help"}))
        assert out == ["# port help", "port: 8080"]

    def test_multiline_help(self):
        rows = iter_yaml_rows("""\
port: 8080
""")
        out = list(insert_comments_iter(rows, {("port",): ["line 1", "line 2"]}))
        assert out == ["# line 1", "# line 2", "port: 8080"]

    def test_no_help_key(self):
        rows = iter_yaml_rows("""\
port: 8080
""")
        out = list(insert_comments_iter(rows, {}))
        assert out == ["port: 8080"]

    def test_indent_preserved(self):
        rows = iter_yaml_rows("""\
outer:
  port: 8080
""")
        out = list(insert_comments_iter(rows, {("outer", "port"): "port help"}))
        assert out == ["outer:", "  # port help", "  port: 8080"]

    def test_unknown_key_untouched(self):
        rows = iter_yaml_rows("""\
name: server
""")
        out = list(insert_comments_iter(rows, {("port",): "port help"}))
        assert out == ["name: server"]


class TestInsertComments:
    def test_insert_above_key(self):
        text = """\
port: 8080
name: server
"""
        help_map = {("port",): ["line 1", "line 2"]}
        assert insert_comments(text, help_map) == """\
# line 1
# line 2
port: 8080
name: server
"""

    def test_no_help_map(self):
        text = """\
port: 8080
"""
        assert insert_comments(text, {}) == text

    def test_indent_preserved(self):
        text = """\
outer:
  port: 8080
"""
        help_map = {("outer", "port"): "port help"}
        assert insert_comments(text, help_map) == """\
outer:
  # port help
  port: 8080
"""

    def test_existing_comment_kept(self):
        text = """\
# existing
port: 8080
"""
        help_map = {("port",): "port help"}
        assert insert_comments(text, help_map) == """\
# existing
# port help
port: 8080
"""

    def test_empty_lines_kept(self):
        text = """\
port: 8080

name: server
"""
        help_map = {("name",): "name help"}
        assert insert_comments(text, help_map) == """\
port: 8080

# name help
name: server
"""

    def test_key_prefix_no_collision(self):
        text = """\
a: 1
a1: 2
"""
        help_map = {("a",): "a help", ("a1",): "a1 help"}
        assert insert_comments(text, help_map) == """\
# a help
a: 1
# a1 help
a1: 2
"""

    def test_comment_not_inserted_inside_multiline_string(self):
        text = """\
desc: |-
  line1
  line2
"""
        help_map = {("desc",): "desc help"}
        assert insert_comments(text, help_map) == """\
# desc help
desc: |-
  line1
  line2
"""

    def test_same_key_different_levels(self):
        text = """\
port: 1
inner:
  port: 2
"""
        help_map = {("port",): "top port", ("inner", "port"): "inner port"}
        assert insert_comments(text, help_map) == """\
# top port
port: 1
inner:
  # inner port
  port: 2
"""

    def test_block_scalar_content_not_tracked_as_key(self):
        text = """\
desc: |-
  key: not a real key
port: 8080
"""
        help_map = {("port",): "port help"}
        assert insert_comments(text, help_map) == """\
desc: |-
  key: not a real key
# port help
port: 8080
"""

    def test_block_scalar_with_comment(self):
        text = """\
desc: | # comment
  key: not a real key
port: 8080
"""
        help_map = {("port",): "port help"}
        assert insert_comments(text, help_map) == """\
desc: | # comment
  key: not a real key
# port help
port: 8080
"""

