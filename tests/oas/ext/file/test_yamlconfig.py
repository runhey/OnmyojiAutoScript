import msgspec
import pytest
import yaml
from msgspec import Meta, Struct
from typing_extensions import Annotated

from oas.ext.file.yamlconfig import YamlConfig
from oas.testing.filesystem import fs  # noqa: F401


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


class MultiLineConfig(Struct):
    """Model with multiline string used in tests."""

    desc: str = "line1\nline2"


class SecretPasswordConfig(Struct):
    """Model with a password field used in secret tests."""

    password: str = "password"
    name: str = "server"


class SecretPasswordYamlConfig(YamlConfig):
    """YamlConfig subclass that hides password values in show(), like YamlConfigWithPassword."""

    def _secrete_value(self, path):
        if 'password' in path:
            return '********'
        return super()._secrete_value(path)


class TestYamlConfigInit:
    def test_model_not_struct(self):
        with pytest.raises(TypeError, match="msgspec.Struct"):
            YamlConfig("config.yaml", dict)

    def test_model_not_default_constructible(self, fs):
        class NoDefault(Struct):
            port: int

        with pytest.raises(ValueError, match="default constructible"):
            YamlConfig('/config.yaml', NoDefault)


class TestYamlConfigHelpMap:
    def test_help_map(self, fs):
        config = YamlConfig('/config.yaml', CommentedConfig)
        assert config.help_map == {("port",): ["line 1", "line 2"], ("name",): "server name"}

    def test_help_map_cached(self, fs):
        config = YamlConfig('/config.yaml', CommentedConfig)
        assert config.help_map is config.help_map

    def test_help_map_no_help(self, fs):
        config = YamlConfig('/config.yaml', Config)
        assert config.help_map == {}

    def test_help_map_same_key_different_levels(self, fs):
        class Inner(Struct):
            port: Annotated[int, Meta(extra={"help": "inner port help"})] = 1

        class Outer(Struct):
            port: Annotated[int, Meta(extra={"help": "outer port help"})] = 2
            inner: Inner = msgspec.field(default_factory=Inner)

        config = YamlConfig('/config.yaml', Outer)
        assert config.help_map == {
            ("port",): "outer port help",
            ("inner", "port"): "inner port help",
        }


class TestYamlConfigRead:
    def test_missing_file_returns_defaults(self, fs):
        config = YamlConfig('/config.yaml', Config)
        assert config.data == Config()
        # FileNotFoundError is recorded as an error
        assert len(config.errors) == 1
        assert isinstance(config.errors[0], FileNotFoundError)

    def test_read_values(self, fs):
        fs.create_file('/config.yaml', contents="""\
# comment
port: 9090
name: custom
""")
        config = YamlConfig('/config.yaml', Config)
        assert config.data.port == 9090
        assert config.data.name == "custom"
        assert config.errors == []

    def test_read_attribute_access(self, fs):
        fs.create_file('/config.yaml', contents="""\
port: 9090
""")
        config = YamlConfig('/config.yaml', Config)
        assert config.data.port == 9090

    def test_read_invalid_value_falls_back_to_default(self, fs):
        fs.create_file('/config.yaml', contents="""\
port: not-a-number
name: custom
""")
        config = YamlConfig('/config.yaml', Config)
        assert config.data.port == 8080
        assert config.data.name == "custom"
        assert config.errors

    def test_read_unknown_key_ignored(self, fs):
        fs.create_file('/config.yaml', contents="""\
unknown: 1
port: 9090
""")
        config = YamlConfig('/config.yaml', Config)
        assert config.data.port == 9090

    def test_read_invalid_yaml(self, fs):
        fs.create_file('/config.yaml', contents="""\
port: [unclosed
""")
        config = YamlConfig('/config.yaml', Config)
        assert config.data == Config()
        # yaml.YAMLError is recorded as an error
        assert len(config.errors) == 1
        assert isinstance(config.errors[0], yaml.YAMLError)

    def test_read_non_utf8(self, fs):
        # Invalid utf-8 bytes can't be expressed with multiline string
        fs.create_file('/config.yaml', contents=b"port: \xff\xfe\n")
        config = YamlConfig('/config.yaml', Config)
        assert config.data == Config()
        # yaml.YAMLError (ReaderError) is recorded as an error
        assert len(config.errors) == 1
        assert isinstance(config.errors[0], yaml.YAMLError)

    def test_read_bom(self, fs):
        # BOM bytes can't be expressed with multiline string
        fs.create_file('/config.yaml', contents=b"\xef\xbb\xbfport: 9090\n")
        config = YamlConfig('/config.yaml', Config)
        assert config.data.port == 9090

    def test_read_numeric_string_keeps_type(self, fs):
        fs.create_file('/config.yaml', contents="""\
name: '8080'
""")
        config = YamlConfig('/config.yaml', Config)
        assert config.data.name == "8080"

    def test_read_list_value(self, fs):
        class ListConfig(Struct):
            ports: list = msgspec.field(default_factory=list)

        fs.create_file('/config.yaml', contents="""\
ports: [4, 5, 6]
""")
        config = YamlConfig('/config.yaml', ListConfig)
        assert config.data.ports == [4, 5, 6]

    def test_read_nested_struct(self, fs):
        fs.create_file('/config.yaml', contents="""\
inner:
  port: 9090
name: custom
""")
        config = YamlConfig('/config.yaml', OuterConfig)
        assert config.data == OuterConfig(inner=InnerConfig(port=9090), name="custom")

    def test_read_multiline_string(self, fs):
        fs.create_file('/config.yaml', contents="""\
desc: |-
  hello
  world
""")
        config = YamlConfig('/config.yaml', MultiLineConfig)
        assert config.data.desc == "hello\nworld"


class TestYamlConfigAutoFix:
    """Init writes back fixed values when read found validation errors."""

    def test_init_auto_fix_invalid_value(self, fs):
        fs.create_file('/config.yaml', contents="""\
port: not-a-number
name: custom
""")
        config = YamlConfig('/config.yaml', Config)
        # Invalid field falls back to default, valid fields are preserved
        assert config.data == Config(port=8080, name="custom")
        # File is rewritten with the fixed values
        text = open('/config.yaml', encoding="utf-8").read()
        assert text == """\
port: 8080
name: custom
debug: false
"""

    def test_init_auto_fix_nested(self, fs):
        fs.create_file('/config.yaml', contents="""\
inner:
  port: not-a-number
name: custom
""")
        YamlConfig('/config.yaml', OuterConfig)
        # Second read has no errors, the file is now valid
        config2 = YamlConfig('/config.yaml', OuterConfig)
        assert config2.data == OuterConfig(inner=InnerConfig(port=8080), name="custom")
        assert config2.errors == []

    def test_init_auto_fix_round_trip(self, fs):
        fs.create_file('/config.yaml', contents="""\
port: not-a-number
""")
        YamlConfig('/config.yaml', Config)
        config2 = YamlConfig('/config.yaml', Config)
        assert config2.data == Config()
        assert config2.errors == []

    def test_init_auto_fix_keeps_errors(self, fs):
        # Errors of the read are still exposed after the auto fix
        fs.create_file('/config.yaml', contents="""\
port: not-a-number
""")
        config = YamlConfig('/config.yaml', Config)
        assert config.errors

    def test_init_no_write_on_valid(self, fs):
        text = """\
port: 9090
name: custom
"""
        fs.create_file('/config.yaml', contents=text)
        YamlConfig('/config.yaml', Config)
        # Valid file is not rewritten
        assert open('/config.yaml', encoding="utf-8").read() == text

    def test_init_auto_fix_invalid_yaml(self, fs):
        fs.create_file('/config.yaml', contents="""\
port: [unclosed
""")
        YamlConfig('/config.yaml', Config)
        # Invalid yaml is replaced with default values
        text = open('/config.yaml', encoding="utf-8").read()
        assert text == """\
port: 8080
name: server
debug: false
"""

    def test_init_auto_fix_missing_file(self, fs):
        YamlConfig('/config.yaml', Config)
        # Missing file is created with default values
        assert fs.exists('/config.yaml')
        text = open('/config.yaml', encoding="utf-8").read()
        assert text == """\
port: 8080
name: server
debug: false
"""

    def test_init_auto_fix_non_utf8(self, fs):
        fs.create_file('/config.yaml', contents=b"port: \xff\xfe\n")
        YamlConfig('/config.yaml', Config)
        # Non-utf8 file is replaced with default values
        text = open('/config.yaml', 'rb').read()
        assert text == "port: 8080\nname: server\ndebug: false\n".encode('utf-8')


class TestYamlConfigLogger:
    """Print outputs are captured with capsys."""

    def test_read_invalid_value_logs_warning(self, fs, capsys):
        fs.create_file('/config.yaml', contents="""\
port: not-a-number
""")
        YamlConfig('/config.yaml', Config)
        out = capsys.readouterr().out
        assert "Invalid deploy config value" in out

    def test_read_valid_no_warning(self, fs, capsys):
        fs.create_file('/config.yaml', contents="""\
port: 9090
""")
        YamlConfig('/config.yaml', Config)
        out = capsys.readouterr().out
        assert not "Invalid deploy config value" in out

    def test_validate_invalid_logs_warning(self, fs, capsys):
        fs.create_file('/config.yaml', contents="""\
port: 9090
""")
        config = YamlConfig('/config.yaml', Config)
        config.data.port = "not-a-number"
        assert config.validate() is False
        out = capsys.readouterr().out
        assert "Invalid deploy config value" in out

    def test_validate_valid_no_warning(self, fs, capsys):
        fs.create_file('/config.yaml', contents="""\
port: 9090
""")
        config = YamlConfig('/config.yaml', Config)
        assert config.validate() is True
        out = capsys.readouterr().out
        assert not "Invalid deploy config value" in out

    def test_write_logs_info(self, fs, capsys):
        config = YamlConfig('/config.yaml', Config)
        config.data.port = 9090
        assert config.write() is True
        out = capsys.readouterr().out
        assert "Write config" in out

    def test_write_skip_same_no_info(self, fs, capsys):
        config = YamlConfig('/config.yaml', Config)
        assert config.write(skip_same=False) is True
        capsys.readouterr()  # clear previous output
        assert config.write(skip_same=True) is False
        out = capsys.readouterr().out
        assert not "Write config" in out

    def test_auto_fix_logs_warning_then_info(self, fs, capsys):
        fs.create_file('/config.yaml', contents="""\
port: not-a-number
""")
        YamlConfig('/config.yaml', Config)
        out = capsys.readouterr().out
        # warning from read(), info from the auto-fix write()
        assert "Invalid deploy config value" in out
        assert "Write config" in out

    def test_read_invalid_yaml_logs_warning_then_info(self, fs, capsys):
        fs.create_file('/config.yaml', contents="""\
port: [unclosed
""")
        YamlConfig('/config.yaml', Config)
        out = capsys.readouterr().out
        assert "Invalid deploy config value" in out
        assert "Write config" in out

    def test_read_missing_file_logs_warning_then_info(self, fs, capsys):
        YamlConfig('/config.yaml', Config)
        out = capsys.readouterr().out
        assert "Invalid deploy config value" in out
        assert "Write config" in out

    def test_read_non_utf8_logs_warning_then_info(self, fs, capsys):
        fs.create_file('/config.yaml', contents=b"port: \xff\xfe\n")
        YamlConfig('/config.yaml', Config)
        out = capsys.readouterr().out
        assert "Invalid deploy config value" in out
        assert "Write config" in out


class TestYamlConfigWrite:
    def test_write_comments(self, fs):
        config = YamlConfig('/config.yaml', CommentedConfig)
        config.write()
        text = open('/config.yaml', encoding="utf-8").read()
        assert text == """\
# line 1
# line 2
port: 8080
# server name
name: server
"""

    def test_write_creates_file(self, fs):
        config = YamlConfig('/config.yaml', Config)
        assert config.write(skip_same=False) is True
        assert fs.exists('/config.yaml')

    def test_write_round_trip(self, fs):
        config = YamlConfig('/config.yaml', Config)
        config.data.port = 9090
        config.data.name = "custom"
        config.data.debug = True
        config.write()

        config2 = YamlConfig('/config.yaml', Config)
        assert config2.data == Config(port=9090, name="custom", debug=True)

    def test_write_round_trip_numeric_string(self, fs):
        class StringConfig(Struct):
            port: str = "8080"

        config = YamlConfig('/config.yaml', StringConfig)
        config.write()

        config2 = YamlConfig('/config.yaml', StringConfig)
        assert config2.data == StringConfig(port="8080")

    def test_write_nested_round_trip(self, fs):
        config = YamlConfig('/config.yaml', OuterConfig)
        config.data.inner.port = 9090
        config.write()

        text = open('/config.yaml', encoding="utf-8").read()
        assert text == """\
inner:
  # inner port
  port: 9090
name: server
"""

        config2 = YamlConfig('/config.yaml', OuterConfig)
        assert config2.data == OuterConfig(inner=InnerConfig(port=9090))

    def test_write_multiline_round_trip(self, fs):
        config = YamlConfig('/config.yaml', MultiLineConfig)
        config.data.desc = "hello\nworld"
        config.write()

        config2 = YamlConfig('/config.yaml', MultiLineConfig)
        assert config2.data == MultiLineConfig(desc="hello\nworld")

    def test_write_same_key_different_levels(self, fs):
        class Inner(Struct):
            port: Annotated[int, Meta(extra={"help": "inner port help"})] = 1

        class Outer(Struct):
            port: Annotated[int, Meta(extra={"help": "outer port help"})] = 2
            inner: Inner = msgspec.field(default_factory=Inner)

        config = YamlConfig('/config.yaml', Outer)
        config.write()

        text = open('/config.yaml', encoding="utf-8").read()
        assert text == """\
# outer port help
port: 2
inner:
  # inner port help
  port: 1
"""

        config2 = YamlConfig('/config.yaml', Outer)
        assert config2.data == Outer(port=2, inner=Inner(port=1))

    def test_write_skip_same(self, fs):
        config = YamlConfig('/config.yaml', Config)
        assert config.write(skip_same=False) is True
        assert config.write(skip_same=True) is False

    def test_write_skip_same_after_change(self, fs):
        config = YamlConfig('/config.yaml', Config)
        config.write()
        config.data.port = 9090
        assert config.write(skip_same=True) is True

    def test_write_comments_preserved_after_rewrite(self, fs):
        config = YamlConfig('/config.yaml', CommentedConfig)
        config.write()
        config.data.port = 9090
        config.write()
        text = open('/config.yaml', encoding="utf-8").read()
        assert text == """\
# line 1
# line 2
port: 9090
# server name
name: server
"""


class TestYamlConfigValidate:
    def test_validate_valid(self, fs):
        fs.create_file('/config.yaml', contents="""\
port: 9090
name: custom
""")
        config = YamlConfig('/config.yaml', Config)
        assert config.validate() is True
        assert config.errors == []
        assert config.data == Config(port=9090, name="custom")

    def test_validate_invalid_falls_back_to_default(self, fs):
        fs.create_file('/config.yaml', contents="""\
port: 9090
""")
        config = YamlConfig('/config.yaml', Config)
        # set an invalid value on data
        config.data.port = "not-a-number"
        assert config.validate() is False
        assert config.errors
        assert config.data.port == 8080

    def test_validate_errors_cleared_on_valid(self, fs):
        fs.create_file('/config.yaml', contents="""\
port: not-a-number
""")
        config = YamlConfig('/config.yaml', Config)
        assert config.errors
        config.data.port = 9090
        assert config.validate() is True
        assert config.errors == []

    def test_validate_nested(self, fs):
        fs.create_file('/config.yaml', contents="""\
inner:
  port: 9090
name: custom
""")
        config = YamlConfig('/config.yaml', OuterConfig)
        config.data.inner.port = "bad"
        assert config.validate() is False
        assert config.data.inner.port == 8080


class TestYamlConfigSet:
    def test_set_flat_value(self, fs):
        fs.create_file('/config.yaml', contents="""\
port: 9090
name: custom
""")
        config = YamlConfig('/config.yaml', Config)
        assert config.set(('port',), 7070) is True
        assert config.data.port == 7070
        assert config.data.name == "custom"
        assert config.errors == []

    def test_set_nested_value(self, fs):
        fs.create_file('/config.yaml', contents="""\
inner:
  port: 9090
name: custom
""")
        config = YamlConfig('/config.yaml', OuterConfig)
        assert config.set(('inner', 'port'), 7070) is True
        assert config.data.inner.port == 7070
        assert config.data.name == "custom"
        assert config.errors == []

    def test_set_invalid_value_keeps_data(self, fs):
        fs.create_file('/config.yaml', contents="""\
port: 9090
""")
        config = YamlConfig('/config.yaml', Config)
        assert config.set(('port',), 'not-a-number') is False
        # Data is unchanged on validation failure
        assert config.data.port == 9090
        assert len(config.errors) == 1
        assert isinstance(config.errors[0], msgspec.ValidationError)

    def test_set_strict_type_no_coercion(self, fs):
        # convert validates with strict types, str is not coerced into int
        fs.create_file('/config.yaml', contents="""\
port: 9090
""")
        config = YamlConfig('/config.yaml', Config)
        assert config.set(('port',), '7070') is False
        assert config.data.port == 9090

    def test_set_unknown_key(self, fs):
        config = YamlConfig('/config.yaml', Config)
        assert config.set(('nope',), 1) is False
        assert config.data == Config()
        assert len(config.errors) == 1
        assert isinstance(config.errors[0], KeyError)

    def test_set_nested_unknown_key(self, fs):
        config = YamlConfig('/config.yaml', OuterConfig)
        assert config.set(('inner', 'nope'), 1) is False
        assert config.data == OuterConfig()
        assert len(config.errors) == 1
        assert isinstance(config.errors[0], KeyError)

    def test_set_leaf_not_mapping(self, fs):
        # Middle path goes through a non-mapping field
        config = YamlConfig('/config.yaml', Config)
        assert config.set(('name', 'x'), 1) is False
        assert config.data == Config()

    def test_set_empty_key(self, fs):
        config = YamlConfig('/config.yaml', Config)
        assert config.set((), 1) is False
        assert config.data == Config()
        assert len(config.errors) == 1
        assert isinstance(config.errors[0], ValueError)

    def test_set_clears_previous_errors(self, fs):
        fs.create_file('/config.yaml', contents="""\
port: not-a-number
""")
        config = YamlConfig('/config.yaml', Config)
        assert config.errors
        assert config.set(('port',), 9090) is True
        assert config.errors == []
        assert config.data.port == 9090

    def test_set_valid_no_warning(self, fs, capsys):
        config = YamlConfig('/config.yaml', Config)
        capsys.readouterr()  # clear read() output
        assert config.set(('port',), 9090) is True
        out = capsys.readouterr().out
        assert not "Invalid deploy config value" in out

    def test_set_invalid_logs_warning(self, fs, capsys):
        config = YamlConfig('/config.yaml', Config)
        assert config.set(('port',), 'bad') is False
        out = capsys.readouterr().out
        assert "Invalid deploy config value" in out

    def test_set_then_write_round_trip(self, fs):
        config = YamlConfig('/config.yaml', OuterConfig)
        assert config.set(('inner', 'port'), 9090) is True
        assert config.write(skip_same=False) is True

        config2 = YamlConfig('/config.yaml', OuterConfig)
        assert config2.data == OuterConfig(inner=InnerConfig(port=9090))
        assert config2.errors == []


class TestYamlConfigShow:
    """show() logs settings that are different from the defaults."""

    def test_show_all_default(self, fs, capsys):
        config = YamlConfig('/config.yaml', Config)
        config.show()
        out = capsys.readouterr().out
        assert 'Showing deploy config of /config.yaml' in out
        assert '(config is the same as default)' in out
        assert not '(rest of the config is the same as default)' in out
        assert not '  port =' in out

    def test_show_flat_difference(self, fs, capsys):
        fs.create_file('/config.yaml', contents="""\
port: 9090
""")
        config = YamlConfig('/config.yaml', Config)
        config.show()
        out = capsys.readouterr().out
        assert 'Showing deploy config of /config.yaml' in out
        assert '  port = 9090' in out
        assert '(rest of the config is the same as default)' in out
        assert not '(config is the same as default)' in out

    def test_show_str_value_quoted(self, fs, capsys):
        fs.create_file('/config.yaml', contents="""\
name: custom
""")
        config = YamlConfig('/config.yaml', Config)
        config.show()
        out = capsys.readouterr().out
        assert "  name = 'custom'" in out

    def test_show_nested_difference(self, fs, capsys):
        fs.create_file('/config.yaml', contents="""\
inner:
  port: 9090
""")
        config = YamlConfig('/config.yaml', OuterConfig)
        config.show()
        out = capsys.readouterr().out
        assert '  inner.port = 9090' in out
        assert '(rest of the config is the same as default)' in out

    def test_show_multiple_differences(self, fs, capsys):
        fs.create_file('/config.yaml', contents="""\
port: 9090
name: custom
""")
        config = YamlConfig('/config.yaml', Config)
        config.show()
        out = capsys.readouterr().out
        assert '  port = 9090' in out
        assert "  name = 'custom'" in out

    def test_show_default_value_not_logged(self, fs, capsys):
        fs.create_file('/config.yaml', contents="""\
port: 9090
""")
        config = YamlConfig('/config.yaml', Config)
        config.show()
        out = capsys.readouterr().out
        # name keeps its default 'server', debug keeps its default False
        assert not '  name =' in out
        assert not '  debug =' in out

    def test_show_logs_info_to_backend(self, fs, capsys):
        fs.create_file('/config.yaml', contents="""\
port: 9090
""")
        config = YamlConfig('/config.yaml', Config)
        config.show()
        out = capsys.readouterr().out
        assert 'Showing deploy config of /config.yaml' in out
        assert '  port = 9090' in out
        assert '(rest of the config is the same as default)' in out


class TestYamlConfigSecreteValue:
    """_secrete_value() overrides the value shown by show() for secret fields."""

    def test_secrete_value_default_returns_nodesecret(self, fs):
        # Default returns NODEFAULT, so show() displays the current value
        config = YamlConfig('/config.yaml', SecretPasswordConfig)
        assert config._secrete_value(('password',)) is msgspec.NODEFAULT
        assert config._secrete_value(('name',)) is msgspec.NODEFAULT

    def test_show_hides_password_value(self, fs, capsys):
        fs.create_file('/config.yaml', contents="""\
password: hunter2
""")
        config = SecretPasswordYamlConfig('/config.yaml', SecretPasswordConfig)
        config.show()
        out = capsys.readouterr().out
        # Override value is displayed instead of the real one
        assert "  password = '********'" in out
        assert '(rest of the config is the same as default)' in out
        # The real password value never appears in the log
        assert not 'hunter2' in out

    def test_show_hides_password_keeps_other_differences(self, fs, capsys):
        fs.create_file('/config.yaml', contents="""\
password: hunter2
name: custom
""")
        config = SecretPasswordYamlConfig('/config.yaml', SecretPasswordConfig)
        config.show()
        out = capsys.readouterr().out
        assert "  password = '********'" in out
        assert "  name = 'custom'" in out
        assert not 'hunter2' in out

    def test_show_hides_nested_password(self, fs, capsys):
        class SecretInner(Struct):
            password: str = "password"
            port: int = 8080

        class SecretOuter(Struct):
            inner: SecretInner = msgspec.field(default_factory=SecretInner)
            name: str = "server"

        fs.create_file('/config.yaml', contents="""\
inner:
  password: hunter2
  port: 9090
""")
        config = SecretPasswordYamlConfig('/config.yaml', SecretOuter)
        config.show()
        out = capsys.readouterr().out
        # Path passed to _secrete_value is the full key path ('inner', 'password')
        assert "  inner.password = '********'" in out
        assert '  inner.port = 9090' in out
        assert not 'hunter2' in out

    def test_show_default_password_not_logged(self, fs, capsys):
        # Unchanged password is not a difference, show() logs nothing about it
        fs.create_file('/config.yaml', contents="""\
name: custom
""")
        config = SecretPasswordYamlConfig('/config.yaml', SecretPasswordConfig)
        config.show()
        out = capsys.readouterr().out
        assert "  name = 'custom'" in out
        assert not '  password =' in out


