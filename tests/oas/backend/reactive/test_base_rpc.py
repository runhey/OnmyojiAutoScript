"""
Tests for RPCMethod (alasio/backend/reactive/base_rpc.py): argument parsing,
type conversion, sync/async calls, and @rpc method collection.
"""

import pytest
from msgspec import ValidationError

from oas.backend.reactive.base_rpc import SIG_EMPTY, RPCMethod, rpc
from oas.backend.reactive.base_topic import BaseTopic


class TestRPCMethod:
    def test_build_parses_signature(self):
        """defaults and annotations are parsed, "self" is skipped"""

        def func(self, a, b=2, c: int = 3, *, d: str = 'x'):
            pass

        method = RPCMethod(func)
        assert method.dict_default == {'a': SIG_EMPTY, 'b': 2, 'c': 3, 'd': 'x'}
        assert method.dict_annotation == {
            'a': SIG_EMPTY,
            'b': SIG_EMPTY,
            'c': int,
            'd': str,
        }

    def test_build_skips_var_args(self):
        """*args and **kwargs are not treated as rpc arguments"""

        def func(self, x, *args, **kwargs):
            pass

        method = RPCMethod(func)
        assert method.dict_default == {'x': SIG_EMPTY}
        assert method.dict_annotation == {'x': SIG_EMPTY}

    def test_convert_with_var_args(self):
        """var-args methods convert normally, extra input keys are ignored"""

        def func(self, x=1, *args, **kwargs):
            pass

        method = RPCMethod(func)
        assert method.convert({}) == {'x': 1}
        assert method.convert({'x': 2, 'args': 3, 'kwargs': 4}) == {'x': 2}

    def test_convert_no_args(self):
        """a method without arguments converts any input to empty kwargs"""

        def func(self):
            pass

        assert RPCMethod(func).convert({}) == {}
        assert RPCMethod(func).convert({'ignored': 1}) == {}

    def test_convert_uses_defaults(self):
        """missing optional arguments fall back to their defaults"""

        def func(self, x=5, y='a'):
            pass

        assert RPCMethod(func).convert({}) == {'x': 5, 'y': 'a'}

    def test_convert_annotated_default(self):
        """defaults go through annotation conversion like explicit values"""

        def func(self, x: int = 3):
            pass

        assert RPCMethod(func).convert({}) == {'x': 3}

    def test_convert_explicit_values(self):
        """explicit values override defaults"""

        def func(self, x=5, y='a'):
            pass

        assert RPCMethod(func).convert({'x': 1, 'y': 'b'}) == {'x': 1, 'y': 'b'}

    def test_convert_missing_required(self):
        """missing required arguments raise ValidationError with the arg name"""

        def func(self, x, y=1):
            pass

        with pytest.raises(ValidationError, match='Missing arg: "x"'):
            RPCMethod(func).convert({})

    @pytest.mark.parametrize('value', [
        [1, 2],
        'string',
        5,
        1.5,
        None,
    ])
    def test_convert_input_not_dict(self, value):
        """non-dict input raises ValidationError"""

        def func(self, x):
            pass

        with pytest.raises(ValidationError, match='Input is not a dict'):
            RPCMethod(func).convert(value)

    @pytest.mark.parametrize('annotation, raw, expected', [
        (int, 42, 42),
        (str, '42', '42'),
        (float, 1.5, 1.5),
        (bool, True, True),
        (list, (1, 2), [1, 2]),
        (dict, {'a': 1}, {'a': 1}),
    ])
    def test_convert_type_conversion(self, annotation, raw, expected):
        """values are converted to the annotated type (strict, no coercion)"""

        def func(self, x: annotation):
            pass

        assert RPCMethod(func).convert({'x': raw}) == {'x': expected}

    @pytest.mark.parametrize('annotation, raw', [
        (int, '42'),
        (int, 1.5),
        (int, True),
        (str, 42),
        (float, '1.5'),
        (bool, 1),
        (dict, '{"a": 1}'),
    ])
    def test_convert_invalid_type(self, annotation, raw):
        """wrong-typed values raise ValidationError naming the argument"""
        def func(self, x: annotation):
            pass

        with pytest.raises(ValidationError) as e:
            RPCMethod(func).convert({'x': raw})
        assert f'Invalid type for arg "x"' in str(e.value)

    def test_call_sync(self):
        """call_sync passes converted kwargs to the function and returns its result"""

        def func(self, x: int, y='a'):
            return (x, y)

        method = RPCMethod(func)
        assert method.call_sync(object(), {'x': 3}) == (3, 'a')

    def test_call_sync_missing_arg(self):
        """call_sync propagates the conversion error"""

        def func(self, x: int):
            pass

        with pytest.raises(ValidationError, match='Missing arg: "x"'):
            RPCMethod(func).call_sync(object(), {})

    @pytest.mark.trio
    async def test_call_async(self):
        """call_async awaits the function and returns its result"""

        async def func(self, x: int):
            return x * 2

        method = RPCMethod(func)
        assert await method.call_async(object(), {'x': 3}) == 6

    def test_rpc_decorator_wraps_method(self):
        """the @rpc decorator pre-builds an RPCMethod on the function"""

        @rpc
        def func(self):
            pass

        assert isinstance(func._rpc_method_instance, RPCMethod)
        assert func._rpc_method_instance.func is func


class TestRpcMethodsCollection:
    def test_collects_rpc_methods(self):
        """BaseTopic.__init_subclass__ collects @rpc methods into rpc_methods"""

        class Topic(BaseTopic):
            @rpc
            async def alpha(self):
                pass

            @rpc
            def beta(self):
                pass

        assert set(Topic.rpc_methods) == {'alpha', 'beta'}
        assert all(isinstance(method, RPCMethod) for method in Topic.rpc_methods.values())

    def test_child_inherits_without_polluting_parent(self):
        """child classes inherit parent rpc methods, parent registry is untouched"""

        class Parent(BaseTopic):
            @rpc
            async def alpha(self):
                pass

        class Child(Parent):
            @rpc
            async def beta(self):
                pass

        assert set(Parent.rpc_methods) == {'alpha'}
        assert set(Child.rpc_methods) == {'alpha', 'beta'}
        assert Child.rpc_methods['alpha'] is Parent.rpc_methods['alpha']

    def test_child_override_replaces_method(self):
        """a child class can override a parent's rpc method"""

        class Parent(BaseTopic):
            @rpc
            async def alpha(self):
                return 'parent'

        class Child(Parent):
            @rpc
            async def alpha(self):
                return 'child'

        assert Child.rpc_methods['alpha'] is not Parent.rpc_methods['alpha']
        assert Child.rpc_methods['alpha'].func is Child.__dict__['alpha']
        assert Parent.rpc_methods['alpha'].func is Parent.__dict__['alpha']

    def test_sibling_classes_isolated(self):
        """rpc methods are not shared between sibling classes"""

        class A(BaseTopic):
            @rpc
            async def alpha(self):
                pass

        class B(BaseTopic):
            @rpc
            async def beta(self):
                pass

        assert 'beta' not in A.rpc_methods
        assert 'alpha' not in B.rpc_methods
