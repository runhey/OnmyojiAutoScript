"""Task models and declarative schema override rules."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, ClassVar, Literal, Self

from oas.config.models.base import ConfigBase
from oas.config.models.groups import GroupBase

Operation = Literal['set', 'merge', 'delete', 'replace']


@dataclass(frozen=True, slots=True)
class SchemaRule:
    """One declarative change to a Group or Arg schema node."""

    target: str
    property: str | None = None
    operation: Operation = 'set'
    value: Any = None
    when: Callable[[SchemaContext], bool] | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.target, str) or not self.target.strip():
            raise TypeError('SchemaRule.target must be a non-empty string')
        if self.property is not None and (
            not isinstance(self.property, str) or not self.property.strip()
        ):
            raise TypeError('SchemaRule.property must be a non-empty string or None')
        if self.operation not in {'set', 'merge', 'delete', 'replace'}:
            raise ValueError(f'unsupported schema rule operation: {self.operation!r}')
        if self.when is not None and not callable(self.when):
            raise TypeError('SchemaRule.when must be callable or None')


@dataclass(frozen=True, slots=True)
class SchemaContext:
    """Context passed to a conditional rule's ``when`` callback."""

    task_type: type[TaskBase]
    schema: dict[str, Any]
    task_instance: TaskBase | None = None
    target: str | None = None
    property: str | None = None


class schema:
    """Stateless decorator namespace for creating :class:`SchemaRule` values.

    The lowercase class name is intentional: it provides the public syntax
    ``@schema.hide(...)`` without creating a stateful ``schema`` object.
    """

    _rules_attribute = '__oas_schema_rules__'

    @classmethod
    def _attach(cls, function: Any, rules: Sequence[SchemaRule]) -> Any:
        """把规则暂存到被装饰函数的元数据上。
        设计原因：
        - 装饰器执行时，`Task` 类还没有创建完成，不能直接把规则归属到类。
        - 函数对象在类创建前已经存在，适合作为规则的临时载体。
        - 生成 schema 时沿 Task 的继承链读取这些函数元数据。

        这样做的好处：
        - 不需要维护全局规则注册表。
        - 规则天然跟随被装饰的函数，声明位置清晰。
        - 装饰器只负责声明规则，不直接修改 JSON Schema。
        - 父类和子类的规则可以在导出时按继承顺序合并。
        - 不同 Task 的规则彼此隔离，不会互相污染。
        """
        if isinstance(function, (classmethod, staticmethod)):
            callable_function = function.__func__
        else:
            callable_function = function
        if not callable(callable_function):
            raise TypeError('schema decorators must decorate a method')
        previous = tuple(getattr(callable_function, cls._rules_attribute, ()))
        setattr(callable_function, cls._rules_attribute, previous + tuple(rules))
        return function

    @staticmethod
    def _paths(paths: Sequence[str]) -> tuple[str, ...]:
        if not paths:
            raise TypeError('at least one schema path is required')
        result = tuple(paths)
        if any(not isinstance(path, str) or not path.strip() for path in result):
            raise TypeError('schema paths must be non-empty strings')
        return result

    @classmethod
    def _property(
        cls,
        property_name: str,
        args: Sequence[Any],
        value: Any,
    ) -> Callable[[Any], Any]:
        if len(args) == 1 and isinstance(args[0], Mapping):
            if value is not None:
                raise TypeError('mapping form cannot also provide value')
            mapping = args[0]
            cls._paths(tuple(mapping))
            rules = tuple(
                SchemaRule(target=path, property=property_name, value=item_value)
                for path, item_value in mapping.items()
            )
        else:
            if value is None:
                if len(args) < 2:
                    raise TypeError('schema decorator requires path and value')
                paths, value = args[:-1], args[-1]
            else:
                paths = args
            rules = tuple(
                SchemaRule(target=path, property=property_name, value=value)
                for path in cls._paths(paths)
            )

        def decorator(function: Any) -> Any:
            return cls._attach(function, rules)

        return decorator

    @classmethod
    def _operation(
        cls,
        operation: Operation,
        target: str,
        property: str | None = None,
        value: Any = None,
    ) -> Callable[[Any], Any]:
        rule = SchemaRule(target, property, operation, value)

        def decorator(function: Any) -> Any:
            return cls._attach(function, (rule,))

        return decorator

    @staticmethod
    def hide(*paths: str, value: bool = True) -> Callable[[Any], Any]:
        return schema._property('hide', paths, value)

    @staticmethod
    def icon(*args: Any, value: str | None = None) -> Callable[[Any], Any]:
        return schema._property('icon', args, value)

    @staticmethod
    def title(*args: Any, value: str | None = None) -> Callable[[Any], Any]:
        return schema._property('title', args, value)

    @staticmethod
    def description(*args: Any, value: str | None = None) -> Callable[[Any], Any]:
        return schema._property('description', args, value)

    @staticmethod
    def depends(*args: Any, value: str | None = None) -> Callable[[Any], Any]:
        return schema._property('depends', args, value)

    @staticmethod
    def alias(*args: Any, value: str | None = None) -> Callable[[Any], Any]:
        return schema._property('alias', args, value)

    @staticmethod
    def set(target: str, property: str, value: Any = None) -> Callable[[Any], Any]:
        return schema._operation('set', target, property, value)

    @staticmethod
    def merge(target: str, value: Mapping[str, Any]) -> Callable[[Any], Any]:
        return schema._operation('merge', target, value=dict(value))

    @staticmethod
    def delete(target: str, property: str | None = None) -> Callable[[Any], Any]:
        return schema._operation('delete', target, property)

    @staticmethod
    def replace(target: str, value: Mapping[str, Any]) -> Callable[[Any], Any]:
        return schema._operation('replace', target, value=dict(value))


class TaskBase(ConfigBase):
    """Base class for Tasks with declarative schema override rules."""

    __config_abstract__: ClassVar[bool] = True
    _pending_schema_rules: ClassVar[list[SchemaRule]] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Each Task subclass gets an independent temporary rule buffer.
        cls._pending_schema_rules = []

    def to_dict(self) -> dict[str, dict[str, Any]]:
        """Return the Group configuration of this Task as a plain dict.

        Only single Group fields are exported.  Dynamically managed Group
        lists are not supported yet and are intentionally omitted.
        """
        data: dict[str, dict[str, Any]] = {}
        for field_name in type(self).model_fields:
            value = getattr(self, field_name)
            if isinstance(value, GroupBase):
                data[field_name] = value.to_dict()
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Self:
        """Build a validated Task from a Group configuration dict."""
        return cls.model_validate(data)

    @classmethod
    def schema_overrides(cls, rules: list[SchemaRule]) -> None:
        """登记下一次导出 schema 时要应用的临时规则。

        这个方法由用户在调用 ``model_json_schema()`` 之前显式调用。参数是
        用户自己创建的 ``SchemaRule`` 列表，方法只负责把这些规则登记到当前
        Task 类的 ``_pending_schema_rules``，不会生成 schema，也不会直接修改
        任何 schema 节点。

        类定义上的 ``@schema.hide(...)``、``@schema.icon(...)`` 等装饰器是
        另一套规则来源：它们只在类定义阶段把规则记录到
        ``schema_overrides`` 函数的元数据上，导出时由 Pydantic hook 读取。
        这个方法不会自动调用装饰器，也不会把参数注入到用户函数中。

        用户可以使用四种操作：

        - ``set``：设置一个属性；
        - ``merge``：合并多个属性；
        - ``delete``：删除一个属性或整个目标节点；
        - ``replace``：替换整个目标节点。

        示例：

        .. code-block:: python

            SchedulerTask.schema_overrides([
                SchemaRule(
                    target="scheduler.server_update",
                    property="hide",
                    operation="set",
                    value=True,
                ),
                SchemaRule(
                    target="scheduler.server_update",
                    operation="merge",
                    value={"icon": "refresh", "title": "服务器更新"},
                ),
            ])
            schema = SchedulerTask.model_json_schema()

        规则会按照登记顺序应用，临时规则位于装饰器规则之后，因此可以覆盖
        装饰器设置的同名属性。``model_json_schema()`` 完成后，无论成功还是
        抛出异常，``_pending_schema_rules`` 都会被清空；下一次导出不会重复
        使用本次登记的临时规则。
        """
        cls._pending_schema_rules.extend(rules)

    @classmethod
    def _schema_node(
        cls,
        schema_data: dict[str, Any],
        path: str,
        resolve_ref_schema: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> tuple[dict[str, Any], str, dict[str, Any]]:
        """Materialize and locate one dotted schema path."""

        def resolve_ref(reference: str) -> dict[str, Any]:
            if reference.startswith('#/$defs/'):
                definitions = schema_data.get('$defs', {})
                name = reference[len('#/$defs/') :]
            elif reference.startswith('#/definitions/'):
                definitions = schema_data.get('definitions', {})
                name = reference[len('#/definitions/') :]
            else:
                raise ValueError(f'unsupported schema reference: {reference!r}')
            try:
                return definitions[name]
            except KeyError as exc:
                raise ValueError(
                    f'schema reference does not exist: {reference!r}'
                ) from exc

        def materialize(child: Any) -> dict[str, Any]:
            if not isinstance(child, dict):
                raise TypeError('schema node must be an object')
            reference = child.get('$ref')
            if not reference:
                return child
            if resolve_ref_schema is None:
                resolved = dict(resolve_ref(reference))
            else:
                resolved = dict(resolve_ref_schema(child))
            resolved.update(
                {key: value for key, value in child.items() if key != '$ref'}
            )
            if isinstance(resolved.get('properties'), dict):
                resolved['properties'] = dict(resolved['properties'])
            return resolved

        node: dict[str, Any] = schema_data
        parent: dict[str, Any] = schema_data
        key = ''
        for part in path.split('.'):
            node = materialize(node)
            properties = node.get('properties')
            if not isinstance(properties, dict) or part not in properties:
                raise KeyError(f'schema override path does not exist: {path!r}')
            parent, key = properties, part
            child = materialize(properties[part])
            properties[part] = child
            node = child
        return parent, key, materialize(node)

    @classmethod
    def apply_rules(
        cls,
        schema_data: dict[str, Any],
        rules: Sequence[SchemaRule],
        *,
        task_instance: TaskBase | None = None,
        resolve_ref_schema: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        for rule in rules:
            if rule.property == 'hide' and not isinstance(rule.value, bool):
                raise TypeError('schema.hide value must be bool')
            if (
                rule.property in {'icon', 'title', 'description', 'depends', 'alias'}
                and rule.value is not None
                and not isinstance(rule.value, str)
            ):
                raise TypeError(f'schema.{rule.property} value must be str or None')

            context = SchemaContext(
                task_type=cls,
                schema=schema_data,
                task_instance=task_instance,
                target=rule.target,
                property=rule.property,
            )
            if rule.when is not None and not rule.when(context):
                continue

            parent, key, node = cls._schema_node(
                schema_data,
                rule.target,
                resolve_ref_schema=resolve_ref_schema,
            )
            if rule.operation == 'replace':
                if not isinstance(rule.value, Mapping):
                    raise TypeError('replace rule value must be a mapping')
                if rule.property is None:
                    parent[key] = dict(rule.value)
                else:
                    node[rule.property] = rule.value
            elif rule.operation == 'delete':
                if rule.property is None:
                    del parent[key]
                else:
                    node.pop(rule.property, None)
            elif rule.operation == 'merge':
                if not isinstance(rule.value, Mapping):
                    raise TypeError('merge rule value must be a mapping')
                target = (
                    node
                    if rule.property is None
                    else node.setdefault(rule.property, {})
                )
                if not isinstance(target, dict):
                    raise TypeError('merge rule target must be an object')
                target.update(dict(rule.value))
            else:
                if rule.property is None:
                    raise ValueError('set rule requires property or use replace')
                node[rule.property] = rule.value
        return schema_data

    @classmethod
    def __get_pydantic_json_schema__(
        cls,
        core_schema: Any,
        handler: Callable[[Any], dict[str, Any]],
    ) -> dict[str, Any]:
        """Apply Task rules to the schema produced by Pydantic."""
        try:
            schema_data = handler(core_schema)
            rules: list[SchemaRule] = []
            for base in reversed(cls.__mro__):
                descriptor = base.__dict__.get('schema_overrides')
                if isinstance(descriptor, (classmethod, staticmethod)):
                    function = descriptor.__func__
                else:
                    function = descriptor
                if callable(function):
                    rules.extend(getattr(function, schema._rules_attribute, ()))
            rules.extend(cls._pending_schema_rules)
            return cls.apply_rules(
                schema_data,
                rules,
                resolve_ref_schema=handler.resolve_ref_schema,
            )
        finally:
            cls._pending_schema_rules.clear()
