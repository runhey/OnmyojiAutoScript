import datetime
import sys
import uuid
from typing import Any, Dict, List, Optional

import msgspec
import pytest

from tests.oas.db.validate import generate_example

# --- 1. Define Models for Testing ---


class SimpleModel(msgspec.Struct):
    """A basic model with required primitive types."""
    name: str
    user_id: int
    is_active: bool


class AllOptionalModel(msgspec.Struct):
    """A model where all fields have default values."""
    name: Optional[str] = None
    age: int = 30


class ComplexModel(msgspec.Struct):
    """A model with nested models and container types."""
    item_id: uuid.UUID
    owner: SimpleModel  # Nested model
    tags: List[str]
    metadata: Dict[str, Any]
    creation_date: datetime.datetime
    # Optional field that should not be populated
    notes: Optional[str] = "default note"


class RecursiveModel(msgspec.Struct):
    """A model with a recursive (self-referencing) optional field."""
    node_id: str
    child: Optional["RecursiveModel"] = None


# Define a model with Python 3.10+ syntax if applicable
if sys.version_info >= (3, 10):
    class ModernSyntaxModel(msgspec.Struct):
        identifier: str | int
        description: str | None
        config: dict[str, int] | None = None


# --- 2. Pytest Test Functions ---

def test_simple_model():
    """Tests generation for a model with basic required fields."""
    example = generate_example(SimpleModel)

    assert isinstance(example, SimpleModel)
    assert isinstance(example.name, str)
    assert isinstance(example.user_id, int)
    assert isinstance(example.is_active, bool)

    assert example.name == "string_example"
    assert example.user_id == 123
    assert example.is_active is True


def test_respects_default_values():
    """Tests that fields with default values are not overridden."""
    example = generate_example(AllOptionalModel)

    assert isinstance(example, AllOptionalModel)
    # The function should respect the default values
    assert example.name is None
    assert example.age == 30


def test_complex_model_with_nesting():
    """Tests generation for a model with nested structures."""
    example = generate_example(ComplexModel)

    assert isinstance(example, ComplexModel)

    # Test top-level fields
    assert isinstance(example.item_id, uuid.UUID)
    assert isinstance(example.creation_date, datetime.datetime)

    # Test nested model
    assert isinstance(example.owner, SimpleModel)
    assert example.owner.name == "string_example"
    assert example.owner.user_id == 123

    # Test container types
    assert isinstance(example.tags, list)
    assert len(example.tags) == 1
    assert example.tags[0] == "string_example"

    assert isinstance(example.metadata, dict)
    assert list(example.metadata.keys())[0] == "string_example"
    assert list(example.metadata.values())[0] == "any_value"

    # Test that optional field with default is respected
    assert example.notes == "default note"


def test_recursive_model():
    """Tests that recursive models are handled correctly without infinite loops."""
    example = generate_example(RecursiveModel)

    assert isinstance(example, RecursiveModel)
    assert isinstance(example.node_id, str)
    # The recursive field is optional, so it should default to None
    assert example.child is None


@pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python 3.10+ for | syntax")
def test_modern_syntax_model():
    """Tests generation for models using Python 3.10+ union syntax."""
    # This requires the ModernSyntaxModel to be defined
    example = generate_example(ModernSyntaxModel)

    assert isinstance(example, ModernSyntaxModel)
    # For `str | int`, the generator picks the first type `str`
    assert isinstance(example.identifier, str)
    assert example.identifier == "string_example"

    # For `str | None`, the generator picks the first non-None type `str`
    assert isinstance(example.description, str)
    assert example.description == "string_example"

    # The `config` field is optional, so it should be its default value `None`
    assert example.config is None


