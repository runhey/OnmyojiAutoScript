import msgspec
from typing_extensions import Annotated

from oas.ext.cache.msgspec_meta import FieldMetadata, get_field_metadata


class EmptyStruct(msgspec.Struct):
    pass


class NoMetadata(msgspec.Struct):
    a: int
    b: str
    c: float


class WithMetadata(msgspec.Struct):
    name: Annotated[str, msgspec.Meta(extra={"label": "Name"})]
    count: Annotated[int, msgspec.Meta(extra_json_schema={"type": "integer"})]
    plain: str


class MergedMeta(msgspec.Struct):
    value: Annotated[
        int,
        msgspec.Meta(extra={"min": 0}, extra_json_schema={"type": "integer"}),
        msgspec.Meta(extra={"max": 100}),
    ]


class MergeOverride(msgspec.Struct):
    value: Annotated[
        int,
        msgspec.Meta(extra={"min": 0, "max": 50}),
        msgspec.Meta(extra={"max": 100}),
    ]


class ExtraOnly(msgspec.Struct):
    tag: Annotated[str, msgspec.Meta(extra={"role": "admin"})]


class JsonSchemaOnly(msgspec.Struct):
    score: Annotated[float, msgspec.Meta(extra_json_schema={"type": "number"})]


class MetaWithNone(msgspec.Struct):
    item: Annotated[str, msgspec.Meta(extra=None, extra_json_schema=None)]


class TestGetFieldMetadata:
    """Tests for get_field_metadata."""

    def test_empty_struct(self):
        """Empty struct should return an empty dict."""
        result = get_field_metadata(EmptyStruct)
        assert result == {}

    def test_no_metadata(self):
        """Fields without Any metadata should all get empty FieldMetadata."""
        result = get_field_metadata(NoMetadata)
        assert set(result.keys()) == {"a", "b", "c"}
        for name in ("a", "b", "c"):
            assert isinstance(result[name], FieldMetadata)
            assert result[name].extra == {}
            assert result[name].extra_json_schema == {}

    def test_with_metadata(self):
        """Fields with metadata should have extracted values, others empty."""
        result = get_field_metadata(WithMetadata)
        assert set(result.keys()) == {"name", "count", "plain"}

        # name has extra
        assert result["name"].extra == {"label": "Name"}
        assert result["name"].extra_json_schema == {}

        # count has extra_json_schema
        assert result["count"].extra == {}
        assert result["count"].extra_json_schema == {"type": "integer"}

        # plain has no metadata
        assert result["plain"].extra == {}
        assert result["plain"].extra_json_schema == {}

    def test_merged_meta(self):
        """Multiple Meta objects should merge keys together."""
        result = get_field_metadata(MergedMeta)
        assert set(result.keys()) == {"value"}
        assert result["value"].extra == {"min": 0, "max": 100}
        assert result["value"].extra_json_schema == {"type": "integer"}

    def test_merge_override(self):
        """Later Meta keys should override earlier ones on the same key."""
        result = get_field_metadata(MergeOverride)
        assert result["value"].extra == {"min": 0, "max": 100}

    def test_extra_only(self):
        """Field with extra only should have empty json schema."""
        result = get_field_metadata(ExtraOnly)
        assert result["tag"].extra == {"role": "admin"}
        assert result["tag"].extra_json_schema == {}

    def test_json_schema_only(self):
        """Field with extra_json_schema only should have empty extra."""
        result = get_field_metadata(JsonSchemaOnly)
        assert result["score"].extra == {}
        assert result["score"].extra_json_schema == {"type": "number"}

    def test_meta_with_none(self):
        """Meta with explicit None values should result in empty dicts."""
        result = get_field_metadata(MetaWithNone)
        assert result["item"].extra == {}
        assert result["item"].extra_json_schema == {}

    def test_field_types_are_fieldmetadata(self):
        """All result values must be FieldMetadata instances."""
        result = get_field_metadata(WithMetadata)
        for v in result.values():
            assert isinstance(v, FieldMetadata)

    def test_regular_class(self):
        """A regular class with annotated fields should get FieldMetadata."""
        class Regular:
            x: int = 1

        result = get_field_metadata(Regular)
        assert set(result.keys()) == {"x"}
        assert isinstance(result["x"], FieldMetadata)
        assert result["x"].extra == {}
        assert result["x"].extra_json_schema == {}
