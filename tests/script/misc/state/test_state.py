"""
Tests for script.misc.state

States are class-based (no instantiation). Fields must have type annotations and static default values.
"""
import msgspec
import pytest

from script.misc.state import GlobalState, TaskState


class TestBasicState:
    """Test basic state class definition and default values"""

    def test_basic_state(self):
        class StateA(GlobalState):
            a: int = 1
            b: str = '2'

        # Class attribute access
        assert StateA.a == 1
        assert StateA.b == '2'
        # dict_defaults contains all annotated fields with defaults
        assert StateA.__dict_defaults__ == {'a': 1, 'b': '2'}

    def test_requires_annotation(self):
        """Fields without type annotations are not included in dict_defaults"""

        class StateA(GlobalState):
            a: int = 1
            b = '2'  # no annotation — not a state field

        assert StateA.a == 1
        assert StateA.b == '2'
        assert StateA.__dict_defaults__ == {'a': 1}

    def test_cannot_instantiate(self):
        class StateA(GlobalState):
            a: int = 1

        with pytest.raises(TypeError, match='cannot be instantiated'):
            StateA()


class TestInheritanceAndOverride:
    """Test inheritance and field override"""

    def test_inheritance_and_override(self):
        class StateA(GlobalState):
            a: int = 1
            b: int = 2

        class StateB(StateA):
            b: int = 3
            c: int = 4

        # Inherited and overridden values
        assert StateB.a == 1
        assert StateB.b == 3
        assert StateB.c == 4
        assert StateB.__dict_defaults__ == {'a': 1, 'b': 3, 'c': 4}

        # Parent state is not affected by children
        assert StateA.a == 1
        assert StateA.b == 2
        assert StateA.__dict_defaults__ == {'a': 1, 'b': 2}

    def test_inherit_task_state(self):
        """TaskState also supports inheritance"""

        class StateA(TaskState):
            a: int = 1
            b: int = 2

        class StateB(StateA):
            b: int = 3

        assert StateB.a == 1
        assert StateB.b == 3
        assert StateA.b == 2


class TestAttrModification:
    """Test modifying, checking, and resetting fields"""

    def test_modify_and_check(self):
        class StateA(GlobalState):
            a: int = 1

        # Not modified initially
        assert not StateA.is_modified('a')

        # Modify
        StateA.a = 10
        assert StateA.a == 10
        assert StateA.is_modified('a')

        # Reset to default
        StateA.reset_field('a')
        assert StateA.a == 1
        assert not StateA.is_modified('a')

    def test_get_default(self):
        class StateA(GlobalState):
            a: int = 1
            b: str = 'hello'

        assert StateA.get_default('a') == 1
        assert StateA.get_default('b') == 'hello'

        with pytest.raises(ValueError, match='does not exist'):
            StateA.get_default('nonexistent')

    def test_is_modified_nonexistent_field(self):
        class StateA(GlobalState):
            a: int = 1

        with pytest.raises(ValueError, match='does not exist'):
            StateA.is_modified('nonexistent')

    def test_is_modified_after_reset(self):
        class StateA(GlobalState):
            a: int = 1

        StateA.a = 100
        assert StateA.is_modified('a')
        StateA.reset_field('a')
        assert not StateA.is_modified('a')

    def test_value_validation(self):
        """Setting wrong type raises ValidationError"""

        class StateA(GlobalState):
            a: int = 1

        with pytest.raises(msgspec.ValidationError):
            StateA.a = 'not_an_int'

    def test_undefined_field_dropped(self):
        """Setting a field not defined in the state is silently dropped"""

        class StateA(GlobalState):
            a: int = 1

        StateA.update(b=2)
        assert StateA.a == 1
        with pytest.raises(AttributeError):
            _ = StateA.b

    def test_reset_field_nonexistent(self):
        class StateA(GlobalState):
            a: int = 1

        with pytest.raises(ValueError, match='does not exist'):
            StateA.reset_field('nonexistent')


class TestResetAndClear:
    """Test reset_field and reset_all_fields (replaces old unset/clear)"""

    def test_reset_field(self):
        class StateA(GlobalState):
            a: int = 1
            b: int = 2

        StateA.a = 10
        assert StateA.a == 10
        assert StateA.is_modified('a')

        StateA.reset_field('a')
        assert StateA.a == 1
        assert not StateA.is_modified('a')

    def test_reset_all_fields(self):
        class StateA(GlobalState):
            a: int = 1
            b: int = 2

        StateA.a = 10
        StateA.b = 20
        assert StateA.is_modified('a')
        assert StateA.is_modified('b')

        StateA.reset_all_fields()
        assert StateA.a == 1
        assert StateA.b == 2
        assert not StateA.is_modified('a')
        assert not StateA.is_modified('b')

    def test_is_modified_with_default_value(self):
        """Setting a field to its default value means it's not modified"""

        class StateA(GlobalState):
            a: int = 1
            b: int = 2

        StateA.a = 1  # set to same as default
        StateA.b = 10  # set to different value
        assert not StateA.is_modified('a')
        assert StateA.is_modified('b')


class TestBatchUpdate:
    """Test update method for batch-setting fields"""

    def test_batch_update(self):
        class StateA(GlobalState):
            a: int = 1
            b: int = 2

        StateA.update(a=10)
        assert StateA.a == 10
        assert StateA.b == 2
        assert StateA.is_modified('a')
        assert not StateA.is_modified('b')

    def test_batch_update_validation(self):
        """update with wrong type raises ValidationError"""

        class StateA(GlobalState):
            a: int = 1

        with pytest.raises(msgspec.ValidationError):
            StateA.update(a='not_an_int')

    def test_update_unknown_field_dropped(self):
        """update with unknown field silently drops it"""

        class StateA(GlobalState):
            a: int = 1

        StateA.update(unknown_field=42)
        assert StateA.a == 1


class TestUpdateFromClass:
    """Test update_from_class for merging class attributes into state"""

    def test_update_from_class_basic(self):
        """Basic merge: fields in override class that exist in state are applied"""

        class StateA(GlobalState):
            a: int = 1
            b: str = 'hello'
            c: float = 3.14

        class Override:
            a = 99
            b = 'world'
            c = 2.71

        StateA.update_from_class(Override)
        assert StateA.a == 99
        assert StateA.b == 'world'
        assert StateA.c == 2.71

    def test_update_from_class_partial(self):
        """Only fields that exist in state are merged; unrelated override fields are ignored"""

        class StateA(GlobalState):
            a: int = 1
            b: str = 'hello'

        class Override:
            a = 99
            extra = 'ignored'
            another_extra = 42

        StateA.update_from_class(Override)
        assert StateA.a == 99
        assert StateA.b == 'hello'  # unchanged

    def test_update_from_class_missing_fields(self):
        """Fields in state but not in override class remain unchanged"""

        class StateA(GlobalState):
            a: int = 1
            b: str = 'hello'

        class Override:
            a = 99

        StateA.update_from_class(Override)
        assert StateA.a == 99
        assert StateA.b == 'hello'  # unchanged

    def test_update_from_class_after_modification(self):
        """update_from_class resets previously modified fields"""

        class StateA(GlobalState):
            a: int = 1
            b: str = 'hello'

        StateA.a = 10
        StateA.b = 'modified'

        class Override:
            a = 99

        StateA.update_from_class(Override)
        assert StateA.a == 99
        assert StateA.b == 'modified'  # unchanged because not in Override

    def test_update_from_class_empty_override(self):
        """Empty override class leaves state unchanged"""

        class StateA(GlobalState):
            a: int = 1
            b: str = 'hello'

        class Override:
            pass

        StateA.update_from_class(Override)
        assert StateA.a == 1
        assert StateA.b == 'hello'

    def test_update_from_class_various_types(self):
        """Override class with various types should merge correctly"""

        class StateA(GlobalState):
            flag: bool = False
            count: int = 0
            name: str = ''

        class Override:
            flag = True
            count = 42
            name = 'test'

        StateA.update_from_class(Override)
        assert StateA.flag is True
        assert StateA.count == 42
        assert StateA.name == 'test'

    def test_update_from_class_override_not_state(self):
        """Override class is a plain class, not a state class"""

        class StateA(GlobalState):
            x: int = 0
            y: int = 0

        class ExternalConfig:
            x = 100
            y = 200
            z = 300  # not in state

        StateA.update_from_class(ExternalConfig)
        assert StateA.x == 100
        assert StateA.y == 200

    def test_update_from_class_subclass_state(self):
        """update_from_class works on subclass states"""

        class BaseA(GlobalState):
            a: int = 1
            b: str = 'base'

        class SubA(BaseA):
            c: float = 0.0

        class Override:
            a = 99
            c = 9.99

        SubA.update_from_class(Override)
        assert SubA.a == 99
        assert SubA.b == 'base'  # unchanged
        assert SubA.c == 9.99

    def test_update_from_class_task_state(self):
        """update_from_class works on TaskState subclasses"""

        class StateA(TaskState):
            a: int = 1
            b: str = 'task'

        class Override:
            a = 42
            b = 'overridden'

        StateA.update_from_class(Override)
        assert StateA.a == 42
        assert StateA.b == 'overridden'

    def test_update_from_class_classmethod_exists(self):
        """update_from_class is callable as a class method"""

        class StateA(GlobalState):
            a: int = 1

        assert hasattr(StateA, 'update_from_class')
        assert callable(StateA.update_from_class)

    def test_update_from_instance(self):
        """update_from_class works with an instance of a class"""

        class StateA(GlobalState):
            a: int = 1
            b: str = 'hello'

        class Override:
            def __init__(self):
                self.a = 99
                self.b = 'world'

        StateA.update_from_class(Override())
        assert StateA.a == 99
        assert StateA.b == 'world'

    def test_update_from_instance_partial(self):
        """Instance with only some matching fields"""

        class StateA(GlobalState):
            a: int = 1
            b: str = 'hello'
            c: str = 'extra'

        class Override:
            def __init__(self):
                self.a = 55
                self.c = 'from_instance'

        StateA.update_from_class(Override())
        assert StateA.a == 55
        assert StateA.b == 'hello'  # unchanged
        assert StateA.c == 'from_instance'


class TestTaskStateResetAll:
    """Test TaskState-specific reset_all_subclasses functionality"""

    def test_task_state_reset_all_subclasses(self):
        class StateA(TaskState):
            a: int = 1

        class StateB(TaskState):
            b: int = 2

        # Modify values
        StateA.a = 10
        StateB.b = 20
        assert StateA.is_modified('a')
        assert StateB.is_modified('b')

        # Reset all TaskState subclasses
        TaskState.reset_all_subclasses()

        # All should be back to defaults
        assert not StateA.is_modified('a')
        assert not StateB.is_modified('b')
        assert StateA.a == 1
        assert StateB.b == 2

    def test_task_state_reset_does_not_affect_global_state(self):
        """TaskState.reset_all_subclasses should not affect GlobalState subclasses"""

        class GlobalA(GlobalState):
            x: int = 1

        class TaskA(TaskState):
            y: int = 100

        GlobalA.x = 999
        TaskA.y = 888

        TaskState.reset_all_subclasses()

        # Global state should remain modified
        assert GlobalA.is_modified('x')
        assert GlobalA.x == 999

        # Task state should be reset
        assert not TaskA.is_modified('y')
        assert TaskA.y == 100

    def test_deep_inheritance_reset(self):
        """reset_all_subclasses should work on deep inheritance chains"""

        class BaseA(TaskState):
            a: int = 1

        class MiddleB(BaseA):
            b: int = 2

        class LeafC(MiddleB):
            c: int = 3

        MiddleB.b = 20
        LeafC.c = 30

        TaskState.reset_all_subclasses()

        assert MiddleB.b == 2
        assert LeafC.c == 3
        # Parent fields should also be reset
        assert LeafC.a == 1


class TestMatch:
    """Test match and _match methods on state classes"""

    def test_match_single_condition_true(self):
        class StateA(GlobalState):
            a: str = 'x'
            b: str = 'y'

        assert StateA.match(a='x')
        assert StateA.match(b='y')

    def test_match_single_condition_false(self):
        class StateA(GlobalState):
            a: str = 'x'
            b: str = 'y'

        assert not StateA.match(a='z')
        assert not StateA.match(b='w')

    def test_match_multiple_conditions_all_match(self):
        class StateA(GlobalState):
            a: str = 'x'
            b: str = 'y'

        assert StateA.match(a='x', b='y')

    def test_match_multiple_conditions_one_fails(self):
        class StateA(GlobalState):
            a: str = 'x'
            b: str = 'y'

        assert not StateA.match(a='x', b='w')
        assert not StateA.match(a='z', b='y')
        assert not StateA.match(a='z', b='w')

    def test_match_nonexistent_key(self):
        class StateA(GlobalState):
            a: str = 'x'

        assert not StateA.match(nonexistent='value')
        assert not StateA.match(foo='bar')

    def test_match_mixed_existent_and_nonexistent(self):
        class StateA(GlobalState):
            a: str = 'x'
            b: str = 'y'

        assert not StateA.match(a='x', nonexistent='value')
        assert not StateA.match(a='x', b='y', fake='attr')

    def test_match_empty_kwargs(self):
        class StateA(GlobalState):
            a: str = 'x'

        assert StateA.match()

    @pytest.mark.parametrize("a, b, expected", [
        ('x', 'y', True),
        ('x', 'z', False),
        ('z', 'y', False),
        ('z', 'w', False),
    ])
    def test_match_parametrized_combinations(self, a, b, expected):
        class StateA(GlobalState):
            a: str = 'x'
            b: str = 'y'

        assert StateA.match(a=a, b=b) == expected

    def test_match_after_assignment(self):
        class StateA(GlobalState):
            a: str = 'x'

        StateA.a = 'z'
        assert StateA.match(a='z')
        assert not StateA.match(a='x')

    def test_match_with_multiple_conditions_after_assignment(self):
        class StateA(GlobalState):
            a: str = 'x'
            b: str = 'y'

        StateA.a = 'z'
        StateA.b = 'w'
        assert StateA.match(a='z', b='w')
        assert not StateA.match(a='z', b='y')

    def test_match_on_subclass_with_custom_defaults(self):
        class BaseA(GlobalState):
            a: str = 'default_a'
            b: str = 'default_b'

        class SubA(BaseA):
            a: str = 'custom_a'
            b: str = 'custom_b'

        assert SubA.match(a='custom_a')
        assert SubA.match(b='custom_b')
        assert not SubA.match(a='default_a')
        assert not SubA.match(a='default_a', b='custom_b')

    def test_match_on_task_state(self):
        """match should work on TaskState subclasses too"""
        class StateA(TaskState):
            a: int = 1
            b: int = 2

        assert StateA.match(a=1, b=2)
        assert not StateA.match(a=100)


class TestStructModel:
    """Test the internal struct model behavior"""

    def test_omit_defaults(self):
        """struct model uses omit_defaults"""

        class StateA(GlobalState):
            a: int = 1
            b: int = 2

        # msgspec encoder should omit default values
        encoded = msgspec.json.encode(StateA.__struct_model__(a=1, b=2))
        assert encoded == b'{}'

        encoded = msgspec.json.encode(StateA.__struct_model__(a=10, b=2))
        assert encoded == b'{"a":10}'

    def test_forbid_unknown(self):
        """struct model forbids unknown fields"""

        class StateA(GlobalState):
            a: int = 1

        with pytest.raises(TypeError):
            StateA.__struct_model__(a=1, unknown=2)

    def test_dict_defaults_matches_struct_defaults(self):
        """dict_defaults should match struct model defaults"""

        class StateA(GlobalState):
            a: int = 10
            b: str = 'hello'
            c: float = 3.14

        for name, expected in StateA.__dict_defaults__.items():
            field_idx = StateA.__struct_model__.__struct_fields__.index(name)
            struct_default = StateA.__struct_model__.__struct_defaults__[field_idx]
            assert expected == struct_default


class TestMutableDefaults:
    """Test mutable collection (list, dict, set) defaults are auto-wrapped and isolated"""

    def test_list_default(self):
        """Non-empty list default should be accepted"""

        class StateA(GlobalState):
            items: list = [1, 2, 3]

        assert StateA.items == [1, 2, 3]

    def test_dict_default(self):
        """Non-empty dict default should be accepted"""

        class StateA(GlobalState):
            mapping: dict = {'a': 1, 'b': 2}

        assert StateA.mapping == {'a': 1, 'b': 2}

    def test_set_default(self):
        """Non-empty set default should be accepted"""

        class StateA(GlobalState):
            tags: set = {1, 2, 3}

        assert StateA.tags == {1, 2, 3}

    def test_empty_list_default(self):
        """Empty list default should be accepted"""

        class StateA(GlobalState):
            items: list = []

        assert StateA.items == []

    def test_empty_dict_default(self):
        """Empty dict default should be accepted"""

        class StateA(GlobalState):
            mapping: dict = {}

        assert StateA.mapping == {}

    def test_empty_set_default(self):
        """Empty set default should be accepted"""

        class StateA(GlobalState):
            tags: set = set()

        assert StateA.tags == set()

    def test_mutation_does_not_affect_default(self):
        """Mutating the current value should not change the stored default"""

        class StateA(GlobalState):
            items: list = [1, 2, 3]

        StateA.items.append(4)
        assert StateA.items == [1, 2, 3, 4]
        assert StateA.get_default('items') == [1, 2, 3]

    def test_dict_mutation_does_not_affect_default(self):
        """Mutating a dict field should not change the stored default"""

        class StateA(GlobalState):
            mapping: dict = {'a': 1}

        StateA.mapping['b'] = 2
        assert StateA.mapping == {'a': 1, 'b': 2}
        assert StateA.get_default('mapping') == {'a': 1}

    def test_set_mutation_does_not_affect_default(self):
        """Mutating a set field should not change the stored default"""

        class StateA(GlobalState):
            tags: set = {1, 2}

        StateA.tags.add(3)
        assert StateA.tags == {1, 2, 3}
        assert StateA.get_default('tags') == {1, 2}

    def test_reset_field_restores_fresh_copy(self):
        """reset_field should restore a fresh (deep-copied) default, not the same object"""

        class StateA(GlobalState):
            items: list = [1, 2, 3]

        StateA.items.append(99)
        StateA.reset_field('items')
        assert StateA.items == [1, 2, 3]
        # Mutating the restored value should not affect the default
        StateA.items.append(88)
        assert StateA.get_default('items') == [1, 2, 3]

    def test_reset_all_fields_restores_fresh_copy(self):
        """reset_all_fields should restore fresh copies for mutable defaults"""

        class StateA(GlobalState):
            items: list = [1, 2, 3]
            mapping: dict = {'x': 0}

        StateA.items.append(99)
        StateA.mapping['y'] = 1
        StateA.reset_all_fields()
        assert StateA.items == [1, 2, 3]
        assert StateA.mapping == {'x': 0}
        # Mutating the restored value should not affect defaults
        StateA.items.append(77)
        StateA.mapping['z'] = 2
        assert StateA.get_default('items') == [1, 2, 3]
        assert StateA.get_default('mapping') == {'x': 0}

    def test_is_modified_with_mutable(self):
        """is_modified should detect mutations"""

        class StateA(GlobalState):
            items: list = [1, 2, 3]

        assert not StateA.is_modified('items')
        StateA.items.append(4)
        assert StateA.is_modified('items')
        StateA.reset_field('items')
        assert not StateA.is_modified('items')

    def test_update_replaces_mutable(self):
        """update should replace the mutable value entirely"""

        class StateA(GlobalState):
            items: list = [1, 2, 3]

        StateA.update(items=[4, 5, 6])
        assert StateA.items == [4, 5, 6]
        assert StateA.get_default('items') == [1, 2, 3]

    def test_update_from_class_replaces_mutable(self):
        """update_from_class should replace mutable field values"""

        class StateA(GlobalState):
            items: list = [1, 2, 3]
            mapping: dict = {'a': 1}

        class Override:
            items = [7, 8, 9]
            mapping = {'b': 2}

        StateA.update_from_class(Override)
        assert StateA.items == [7, 8, 9]
        assert StateA.mapping == {'b': 2}


class TestBatchSet:
    """Test batch_set context manager for deferred updates"""

    def test_batch_set_basic(self):
        """Multiple sets inside context are applied as a single update"""

        class StateA(GlobalState):
            a: int = 1
            b: str = 'hello'

        with StateA.batch_set():
            StateA.a = 99
            StateA.b = 'world'

        assert StateA.a == 99
        assert StateA.b == 'world'

    def test_batch_set_no_modification(self):
        """No sets inside context should skip update"""

        class StateA(GlobalState):
            a: int = 1
            b: str = 'hello'

        with StateA.batch_set():
            pass

        assert StateA.a == 1
        assert StateA.b == 'hello'

    def test_batch_set_single(self):
        """Single set inside context should still work"""

        class StateA(GlobalState):
            a: int = 1

        with StateA.batch_set():
            StateA.a = 42

        assert StateA.a == 42

    def test_batch_set_validates_types(self):
        """Type validation still works inside batch context"""

        class StateA(GlobalState):
            a: int = 1

        with pytest.raises(msgspec.ValidationError):
            with StateA.batch_set():
                StateA.a = 'not_an_int'

        # Value should remain unchanged after validation failure
        assert StateA.a == 1

    def test_batch_set_works_on_subclass(self):
        """batch_set works on subclass states"""

        class BaseA(GlobalState):
            a: int = 1

        class SubA(BaseA):
            b: str = 'base'

        with SubA.batch_set():
            SubA.a = 10
            SubA.b = 'overridden'

        assert SubA.a == 10
        assert SubA.b == 'overridden'

    def test_batch_set_on_task_state(self):
        """batch_set works on TaskState subclasses"""

        class StateA(TaskState):
            a: int = 1

        with StateA.batch_set():
            StateA.a = 88

        assert StateA.a == 88

    def test_batch_set_does_not_affect_normal_set(self):
        """Normal sets after batch context work as expected"""

        class StateA(GlobalState):
            a: int = 1
            b: int = 2

        with StateA.batch_set():
            StateA.a = 10

        StateA.b = 99
        assert StateA.a == 10
        assert StateA.b == 99
