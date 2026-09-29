"""
Performance test for cached_property descriptor behavior.

Tests verify that cached_property avoids __get__ calls on subsequent access
for normal classes, msgspec Struct classes with dict=True, and dataclasses.
"""

import dataclasses as dc

import msgspec
import pytest

from oas.ext.cache.cache import cached_property

# =============================================================================
# Helper: count __get__ calls by wrapping the cached_property descriptor
# =============================================================================


class GetCallTracker:
    """
    Wraps a cached_property descriptor to track how many times __get__ is called.

    After wrapping, every call to __get__ increments the counter and delegates
    to the original descriptor.
    """

    def __init__(self, descriptor):
        self._descriptor = descriptor
        self.call_count = 0

    def __get__(self, instance, owner):
        self.call_count += 1
        return self._descriptor.__get__(instance, owner)

    def __set_name__(self, owner, name):
        self._descriptor.__set_name__(owner, name)


def _patch_cached_property(cls, attr):
    """
    Patch a cached_property descriptor on a class with a GetCallTracker.

    Args:
        cls: The class whose descriptor to patch
        attr (str): The attribute name of the cached_property

    Returns:
        GetCallTracker: The tracker wrapping the original descriptor
    """
    original = cls.__dict__[attr]
    tracker = GetCallTracker(original)
    type.__setattr__(cls, attr, tracker)
    return tracker


# =============================================================================
# Test: Normal class
# =============================================================================


def test_normal_class_second_access_skips_get():
    """
    On a normal class, cached_property replaces itself in __dict__ after first
    access, so the second and later accesses do NOT invoke __get__.
    """

    class Normal:
        calc_count = 0

        @cached_property
        def value(self):
            Normal.calc_count += 1
            return "computed"

    tracker = _patch_cached_property(Normal, "value")
    obj = Normal()

    # First access - should go through __get__
    result1 = obj.value
    assert result1 == "computed"
    assert Normal.calc_count == 1
    assert tracker.call_count == 1

    # Second access - should NOT go through __get__ (hits instance __dict__)
    result2 = obj.value
    assert result2 == "computed"
    assert Normal.calc_count == 1  # calc function NOT called again
    assert tracker.call_count == 1  # __get__ NOT called again

    # Third access - still no __get__
    result3 = obj.value
    assert result3 == "computed"
    assert Normal.calc_count == 1
    assert tracker.call_count == 1

    # Verify the value lives in instance __dict__
    assert "value" in obj.__dict__
    assert obj.__dict__["value"] == "computed"


def test_normal_class_multiple_instances():
    """Each instance caches independently, __get__ called once per instance."""

    class Normal:
        calc_count = 0

        @cached_property
        def value(self):
            Normal.calc_count += 1
            return f"computed_{Normal.calc_count}"

    tracker = _patch_cached_property(Normal, "value")
    obj1 = Normal()
    obj2 = Normal()

    # obj1 first access
    assert obj1.value == "computed_1"
    assert tracker.call_count == 1
    assert Normal.calc_count == 1

    # obj1 second access - no __get__
    assert obj1.value == "computed_1"
    assert tracker.call_count == 1
    assert Normal.calc_count == 1

    # obj2 first access - new __get__
    assert obj2.value == "computed_2"
    assert tracker.call_count == 2
    assert Normal.calc_count == 2

    # obj2 second access - no __get__
    assert obj2.value == "computed_2"
    assert tracker.call_count == 2
    assert Normal.calc_count == 2


# =============================================================================
# Test: msgspec Struct with dict=True
# =============================================================================


def test_msgspec_struct_with_dict_true():
    """
    cached_property works on msgspec.Struct with dict=True.

    After first access the computed value is stored in __dict__ and subsequent
    accesses skip __get__ and do not recompute.
    """

    class MsgStruct(msgspec.Struct, dict=True):
        calc_count: int = 0

        @cached_property
        def value(self):
            self.calc_count += 1
            return "computed"

    tracker = _patch_cached_property(MsgStruct, "value")
    obj = MsgStruct()

    # Verify the instance has __dict__ (dict=True enables it)
    assert hasattr(obj, "__dict__")

    # First access
    assert obj.value == "computed"
    assert obj.calc_count == 1
    assert tracker.call_count == 1

    # Second access - should NOT call __get__, should NOT recompute
    assert obj.value == "computed"
    assert obj.calc_count == 1
    assert tracker.call_count == 1

    # Verify cached in __dict__
    assert "value" in obj.__dict__
    assert obj.__dict__["value"] == "computed"


def test_msgspec_struct_multiple_instances():
    """Each msgspec instance caches independently."""

    class MsgStruct(msgspec.Struct, dict=True):
        calc_count: int = 0

        @cached_property
        def value(self):
            self.calc_count += 1
            return f"computed_{self.calc_count}"

    tracker = _patch_cached_property(MsgStruct, "value")
    obj1 = MsgStruct()
    obj2 = MsgStruct()

    assert obj1.value == "computed_1"
    assert tracker.call_count == 1
    assert obj1.calc_count == 1

    assert obj1.value == "computed_1"
    assert tracker.call_count == 1
    assert obj1.calc_count == 1

    assert obj2.value == "computed_1"
    assert tracker.call_count == 2
    assert obj2.calc_count == 1

    assert obj2.value == "computed_1"
    assert tracker.call_count == 2
    assert obj2.calc_count == 1


def test_msgspec_struct_without_dict_raises():
    """
    msgspec.Struct without dict=True uses __slots__ and has no __dict__.
    cached_property should raise TypeError.
    """

    class MsgNoDict(msgspec.Struct):
        field: int = 0

        @cached_property
        def value(self):
            return "computed"

    obj = MsgNoDict()

    with pytest.raises(TypeError, match="No '__dict__' attribute"):
        _ = obj.value


# =============================================================================
# Test: dataclasses
# =============================================================================


def test_dataclass_second_access_skips_get():
    """
    On a dataclass, cached_property replaces itself in __dict__ after first
    access, so the second and later accesses do NOT invoke __get__.
    """

    @dc.dataclass
    class Data:
        calc_count: int = 0

        @cached_property
        def value(self):
            self.calc_count += 1
            return "computed"

    tracker = _patch_cached_property(Data, "value")
    obj = Data()

    # Verify the instance has __dict__
    assert hasattr(obj, "__dict__")

    # First access
    assert obj.value == "computed"
    assert obj.calc_count == 1
    assert tracker.call_count == 1

    # Second access - should NOT call __get__, should NOT recompute
    assert obj.value == "computed"
    assert obj.calc_count == 1
    assert tracker.call_count == 1

    # Third access - still no __get__
    assert obj.value == "computed"
    assert obj.calc_count == 1
    assert tracker.call_count == 1

    # Verify cached in __dict__
    assert "value" in obj.__dict__
    assert obj.__dict__["value"] == "computed"


def test_dataclass_multiple_instances():
    """Each dataclass instance caches independently."""

    @dc.dataclass
    class Data:
        calc_count: int = 0

        @cached_property
        def value(self):
            self.calc_count += 1
            return f"computed_{self.calc_count}"

    tracker = _patch_cached_property(Data, "value")
    obj1 = Data()
    obj2 = Data()

    assert obj1.value == "computed_1"
    assert tracker.call_count == 1
    assert obj1.calc_count == 1

    assert obj1.value == "computed_1"
    assert tracker.call_count == 1
    assert obj1.calc_count == 1

    assert obj2.value == "computed_1"
    assert tracker.call_count == 2
    assert obj2.calc_count == 1

    assert obj2.value == "computed_1"
    assert tracker.call_count == 2
    assert obj2.calc_count == 1


@pytest.mark.skipif(
    not hasattr(dc, "SLOTS"),
    reason="slots=True in dataclass requires Python 3.10+",
)
def test_dataclass_with_slots_raises():
    """
    dataclass with slots=True uses __slots__ and has no __dict__.
    cached_property should raise TypeError.
    """

    @dc.dataclass(slots=True)
    class DataSlots:
        field: int = 0

        @cached_property
        def value(self):
            return "computed"

    obj = DataSlots()

    with pytest.raises(TypeError, match="No '__dict__' attribute"):
        _ = obj.value


# =============================================================================
# Test: Cross-type consistency
# =============================================================================


def test_all_three_types_consistent():
    """Verify normal class, msgspec with dict=True, and dataclass all behave
    identically with cached_property."""

    class Normal:
        count = 0

        @cached_property
        def val(self):
            Normal.count += 1
            return Normal.count

    class Msg(msgspec.Struct, dict=True):
        count: int = 0

        @cached_property
        def val(self):
            self.count += 1
            return self.count

    @dc.dataclass
    class Data:
        count: int = 0

        @cached_property
        def val(self):
            self.count += 1
            return self.count

    normal_tracker = _patch_cached_property(Normal, "val")
    msg_tracker = _patch_cached_property(Msg, "val")
    data_tracker = _patch_cached_property(Data, "val")

    n = Normal()
    m = Msg()
    d = Data()

    # All first accesses should compute
    assert n.val == 1
    assert m.val == 1
    assert d.val == 1
    assert normal_tracker.call_count == 1
    assert msg_tracker.call_count == 1
    assert data_tracker.call_count == 1

    # All second accesses should skip __get__
    assert n.val == 1
    assert m.val == 1
    assert d.val == 1
    assert normal_tracker.call_count == 1
    assert msg_tracker.call_count == 1
    assert data_tracker.call_count == 1

    # All should have value in __dict__
    assert "val" in n.__dict__
    assert "val" in m.__dict__
    assert "val" in d.__dict__


# =============================================================================
# Test: pydantic BaseModel
# =============================================================================

def test_pydantic_model_second_access_skips_get():
    """
    On a pydantic BaseModel, cached_property replaces itself in __dict__ after
    first access, so the second and later accesses do NOT invoke __get__.
    """
    pydantic = pytest.importorskip("pydantic", reason="pydantic not installed")

    class PydModel(pydantic.BaseModel):
        model_config = {"ignored_types": (cached_property,)}
        calc_count: int = 0

        @cached_property
        def value(self):
            self.calc_count += 1
            return "computed"

    tracker = _patch_cached_property(PydModel, "value")
    obj = PydModel()

    # Verify the instance has __dict__
    assert hasattr(obj, "__dict__")

    # First access
    assert obj.value == "computed"
    assert obj.calc_count == 1
    assert tracker.call_count == 1

    # Second access - should NOT call __get__, should NOT recompute
    assert obj.value == "computed"
    assert obj.calc_count == 1
    assert tracker.call_count == 1

    # Third access - still no __get__
    assert obj.value == "computed"
    assert obj.calc_count == 1
    assert tracker.call_count == 1

    # Verify cached in __dict__
    assert "value" in obj.__dict__
    assert obj.__dict__["value"] == "computed"


def test_pydantic_model_multiple_instances():
    """Each pydantic instance caches independently."""
    pydantic = pytest.importorskip("pydantic", reason="pydantic not installed")

    class PydModel(pydantic.BaseModel):
        model_config = {"ignored_types": (cached_property,)}
        calc_count: int = 0

        @cached_property
        def value(self):
            self.calc_count += 1
            return f"computed_{self.calc_count}"

    tracker = _patch_cached_property(PydModel, "value")
    obj1 = PydModel()
    obj2 = PydModel()

    assert obj1.value == "computed_1"
    assert tracker.call_count == 1
    assert obj1.calc_count == 1

    assert obj1.value == "computed_1"
    assert tracker.call_count == 1
    assert obj1.calc_count == 1

    assert obj2.value == "computed_1"
    assert tracker.call_count == 2
    assert obj2.calc_count == 1

    assert obj2.value == "computed_1"
    assert tracker.call_count == 2
    assert obj2.calc_count == 1


def test_all_four_types_consistent():
    """Verify normal class, msgspec with dict=True, dataclass, and pydantic
    model all behave identically with cached_property."""
    pydantic = pytest.importorskip("pydantic", reason="pydantic not installed")

    class Normal:
        count = 0

        @cached_property
        def val(self):
            Normal.count += 1
            return Normal.count

    class Msg(msgspec.Struct, dict=True):
        count: int = 0

        @cached_property
        def val(self):
            self.count += 1
            return self.count

    @dc.dataclass
    class Data:
        count: int = 0

        @cached_property
        def val(self):
            self.count += 1
            return self.count

    class Pyd(pydantic.BaseModel):
        model_config = {"ignored_types": (cached_property,)}
        count: int = 0

        @cached_property
        def val(self):
            self.count += 1
            return self.count

    normal_tracker = _patch_cached_property(Normal, "val")
    msg_tracker = _patch_cached_property(Msg, "val")
    data_tracker = _patch_cached_property(Data, "val")
    pyd_tracker = _patch_cached_property(Pyd, "val")

    n = Normal()
    m = Msg()
    d = Data()
    p = Pyd()

    # All first accesses should compute
    assert n.val == 1
    assert m.val == 1
    assert d.val == 1
    assert p.val == 1
    assert normal_tracker.call_count == 1
    assert msg_tracker.call_count == 1
    assert data_tracker.call_count == 1
    assert pyd_tracker.call_count == 1

    # All second accesses should skip __get__
    assert n.val == 1
    assert m.val == 1
    assert d.val == 1
    assert p.val == 1
    assert normal_tracker.call_count == 1
    assert msg_tracker.call_count == 1
    assert data_tracker.call_count == 1
    assert pyd_tracker.call_count == 1

    # All should have value in __dict__
    assert "val" in n.__dict__
    assert "val" in m.__dict__
    assert "val" in d.__dict__
    assert "val" in p.__dict__
