"""Tests for the modconfig decorator contract."""

import inspect
from typing import ClassVar, get_type_hints

import pytest

from oas.config.entry.mod_config import modconfig
from oas.config.models.args import Input
from oas.config.models.groups import GroupBase
from oas.config.models.tasks import TaskBase
from oas.config.runtime.config_mod import ConfigMod, ConfigModMixin
from oas.config.table.config import ConfigTable

PUBLIC_METHODS = [
    'config_read',
    'config_batch_set',
    'config_set',
    'config_batch_reset',
    'config_reset',
    'config_group_batch_reset',
    'config_group_reset',
    'cfg_task_add',
    'cfg_task_del',
    'cfg_task_copy',
    'cfg_task_reset',
    'cfg_group_add',
    'cfg_group_del',
    'cfg_group_copy',
    'cfg_group_reset',
    'cfg_arg_get',
    'cfg_arg_set',
    'cfg_arg_batch_set',
    'cfg_arg_reset',
    'cfg_arg_batch_reset',
]
INTERNAL_METHODS = ['_config_snapshot', '_config_data_version']


class DecoratorGroup(GroupBase):
    count: int = Input.int(default=1)


class DecoratorTask(TaskBase):
    main: DecoratorGroup


@pytest.mark.parametrize('cls', [ConfigModMixin, ConfigMod])
@pytest.mark.parametrize('name', PUBLIC_METHODS + INTERNAL_METHODS)
def test_public_signature_hides_result(cls, name):
    method = getattr(cls, name)
    signature = inspect.signature(method)

    assert list(signature.parameters)[:2] == ['self', 'config_name']
    assert 'result' not in signature.parameters
    assert 'result' not in get_type_hints(method)
    assert 'result' in inspect.signature(method.__wrapped__).parameters


class Dummy:
    def read(self, result, config_name):
        return result


Dummy.read = modconfig._decorate(
    Dummy.read, lambda target, config_name: ('impl', config_name)
)


def test_result_is_injected_and_returned():
    assert Dummy().read(':memory:') == ('impl', ':memory:')


def test_decorator_mounts_no_adapter_on_the_target():
    """
    The decorator is stateless: it computes ``result``, hands it to the method
    and keeps nothing on the target -- no ModAdapter, no entry info.
    """
    dummy = Dummy()

    assert dummy.__dict__ == {}
    assert dummy.read(':memory:') == ('impl', ':memory:')
    assert dummy.__dict__ == {}


def test_target_needs_no_entry_info_and_no_config_name():
    """
    The shared adapter is gone, so neither ``__entry_info__`` nor an instance
    ``config_name`` is required: the name of the config comes from the call.
    """

    class Bare:
        def read(self, result, config_name):
            return result

    Bare.read = modconfig._decorate(Bare.read, lambda target, config_name: 'result')

    assert Bare().read(':memory:') == 'result'


def test_the_declaration_mixin_composes_into_a_stateless_facade(memory_config):
    """
    ``ConfigModMixin`` is the API alone: a facade can combine it without
    ``ConfigAccessState``, which is what the GUI side does.
    """

    class Facade(ConfigModMixin):
        pass

    facade = Facade()

    assert facade.__dict__ == {}
    assert facade._config_data_version(':memory:') == ConfigMod(
        ':memory:'
    )._config_data_version(':memory:')


def test_decorate_requires_callable():
    with pytest.raises(TypeError, match='must decorate a callable'):
        modconfig._decorate(object(), lambda target: None)


class Ordered:
    calls: ClassVar[list[str]] = []

    def read(self, result, config_name):
        Ordered.calls.append('method')
        return result


def _ordered_impl(target, config_name):
    Ordered.calls.append('impl')
    return 'result'


Ordered.read = modconfig._decorate(Ordered.read, _ordered_impl)


def test_implementation_runs_before_the_method_body():
    Ordered.calls.clear()

    assert Ordered().read(':memory:') == 'result'
    assert Ordered.calls == ['impl', 'method']


def test_internal_snapshot_reads_rows(memory_config):
    ConfigTable(':memory:').upsert_group(
        'DecoratorTask',
        'DecoratorTask@one',
        'DecoratorGroup',
        'main',
        b'\x80',
    )
    mod = ConfigMod(':memory:')

    rows, version = mod._config_snapshot(':memory:')

    assert [row.task for row in rows] == ['DecoratorTask@one']
    assert isinstance(version, tuple)
    assert len(version) == 2
    assert mod._config_data_version(':memory:')[1] == version[1]


def test_internal_data_version_on_empty_table(memory_config):
    version = ConfigMod(':memory:')._config_data_version(':memory:')

    assert isinstance(version, tuple)
    assert len(version) == 2
