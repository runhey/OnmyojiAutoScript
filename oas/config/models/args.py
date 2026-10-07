from __future__ import annotations

from types import MappingProxyType
from typing import Annotated, Any, ClassVar, Literal

from pydantic import Field, GetJsonSchemaHandler, TypeAdapter
from pydantic.fields import FieldInfo
from pydantic.json_schema import JsonSchemaValue
from pydantic_core import CoreSchema, core_schema

from oas.ext.inflection import underscore


class OptionItem:
    """Define one member of an :class:`Option` type.

    An ``OptionItem`` combines the value accepted by an option with the
    Pydantic ``FieldInfo`` used to describe that member in JSON Schema.  It is
    normally created with one of the typed factory methods: ``str``, ``int``,
    ``float``, or ``bool``.  The resulting item is assigned to a member name
    inside an ``Option`` class, where :class:`OptionMeta` turns it into an
    Enum-like member.

    Args:
        value (Any): The value represented by this option member.  The value's
            type must match the factory method used to create the item, and all
            members of one ``Option`` must use the same underlying type.
        field_info (FieldInfo): Pydantic field information associated with the
            item.  This argument is used internally; callers should use a
            typed factory method instead.

    Factory methods:
        ``OptionItem.str(value, **kwargs)`` creates a string option.
        ``OptionItem.int(value, **kwargs)`` creates an integer option.
        ``OptionItem.float(value, **kwargs)`` creates a floating-point option.
        ``OptionItem.bool(value, **kwargs)`` creates a boolean option.

    Metadata keyword arguments:
        title (str | None): Member title.  If omitted, it defaults to an
            i18n key in the form ``$<option>.<member>.title``.  Passing
            ``None`` explicitly keeps the title out of the schema.
        description (str | None): Member description.  If omitted, it defaults
            to an i18n key in the form ``$<option>.<member>.description``.
            Passing ``None`` explicitly keeps the description out of the
            schema.
        hide (bool | None): UI visibility metadata.  The default is ``False``;
            passing ``None`` omits ``hide`` from the schema.
        icon (str | None): UI icon metadata.  It is omitted when ``None``.
        alias (str | None): UI alias metadata.  It is omitted when ``None``.
        json_schema_extra (dict[str, Any] | None): Additional JSON Schema
            metadata.  Values in this mapping override ``hide``, ``icon``,
            and ``alias``.  The ``readOnly`` value is always forced to
            ``True``.  Other unrecognized keyword arguments are also merged
            into this mapping.

    Notes:
        ``readOnly`` is always exported as ``True`` for an OptionItem member.
        The member ``type`` is generated from the typed factory method.  An
        OptionItem does not accept a ``default`` argument because its default
        is always its own value.  The old ``help`` argument, as well as
        ``examples`` and ``deprecated``, is ignored; use ``description`` for
        explanatory text.

    Example:
        ```python
        class Priority(Option):
            HIGH = OptionItem.str(
                "high",
                title="高优先级",
                description="最紧急",
                icon="fire",
            )
        ```
    """

    def __init__(self, value: Any, field_info: FieldInfo):
        self.value = value
        self.field_info = field_info
        self._core_type = type(value)
        self._title_provided = False
        self._description_provided = False

    def __repr__(self) -> str:
        return f"OptionItem({self.value!r})"

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, OptionItem):
            return self.value == other.value
        return self.value == other

    def __hash__(self) -> int:
        return hash(self.value)

    @classmethod
    def str(cls, value: str, **kwargs: Any) -> "OptionItem":
        return cls._make(str, value, **kwargs)

    @classmethod
    def int(cls, value: int, **kwargs: Any) -> "OptionItem":
        return cls._make(int, value, **kwargs)

    @classmethod
    def float(cls, value: float, **kwargs: Any) -> "OptionItem":
        return cls._make(float, value, **kwargs)

    @classmethod
    def bool(cls, value: bool, **kwargs: Any) -> "OptionItem":
        return cls._make(bool, value, **kwargs)

    @classmethod
    def _make(cls, core_type: type, value: Any, **kwargs: Any) -> "OptionItem":
        if type(value) is not core_type:
            raise TypeError(
                f"OptionItem.{core_type.__name__}() requires a "
                f"{core_type.__name__} value, got {type(value).__name__}"
            )

        hide = kwargs.pop("hide", False)
        # ``description`` is the only human-readable explanation field.
        # Ignore the old ``help`` argument so it cannot reappear in the schema.
        kwargs.pop("help", None)
        icon = kwargs.pop("icon", None)
        alias = kwargs.pop("alias", None)
        if "default" in kwargs:
            raise TypeError("OptionItem does not accept a default argument")
        title_provided = "title" in kwargs
        description_provided = "description" in kwargs

        kwargs.pop("examples", None)
        kwargs.pop("deprecated", None)
        field_keys = {"title", "description"}
        user_extra = kwargs.pop("json_schema_extra", {}) or {}
        if not isinstance(user_extra, dict):
            raise TypeError("json_schema_extra must be a dictionary")

        extra: dict[str, Any] = {}
        if hide is not None:
            extra["hide"] = hide
        if icon is not None:
            extra["icon"] = icon
        if alias is not None:
            extra["alias"] = alias

        for key in list(kwargs):
            if key not in field_keys:
                extra[key] = kwargs.pop(key)

        extra.update(user_extra)
        extra["readOnly"] = True  # 这里前端就只能看不能改。

        item = cls(value, Field(default=value, **kwargs, json_schema_extra=extra))
        item._core_type = core_type
        item._title_provided = title_provided
        item._description_provided = description_provided
        return item

    def apply_default_metadata(self, option_name: str, member_name: str) -> None:
        prefix = f"${underscore(option_name)}.{underscore(member_name)}"
        if not self._title_provided:
            self.field_info.title = f"{prefix}.title"
        if not self._description_provided:
            self.field_info.description = f"{prefix}.description"


class OptionMeta(type):
    """为 Option 创建成员并提供 Enum 风格的访问接口。
    当时评估的 ``Annotated + Union`` 方案，用法如下：

    ```python
    HighOption = Annotated[
        Literal["high"],
        Field(title="高优先级", json_schema_extra={"x-color": "red"}),
    ]
    LowOption = Annotated[
        Literal["low"],
        Field(title="低优先级", json_schema_extra={"x-color": "gray"}),
    ]
    Priority = Union[HighOption, LowOption]

    class Config(BaseModel):
        priority: Priority = Field(description="选个优先级")
    ```

    对比自定义类加元类方案，否决它的重要原因：
        1. 没有成员访问。Priority 是 Union 类型别名，没有 .HIGH 属性，Priority.HIGH 会报错。自定义类方案里 Priority.HIGH 直接可用。
        2. 不能构造。Priority("high") 不可调用，Union 只能校验不能实例化。自定义类方案 Priority("high") 正常。
        3. 不能遍历。for m in Priority 不可行，只能另外遍历 PriorityMembers 的类属性，和成员定义脱节。自定义类方案可以直接遍历 Priority.__members__。
        4. 校验后是裸值。拿到的是 "high" 字符串，不是成员对象。自定义类方案拿到 Option 实例，能访问 .value 并进行相等比较。
        5. 成员和 schema 两处定义。成员值写在 PriorityValue，title、x-color 写在另一个 Annotated[Literal[...], Field(...)] 里。同一个字符串需要手写两次，改一处忘一处就会不同步。自定义类方案在成员里直接写元数据，schema 自动读取，保持单一数据源。
        6. 默认输出 anyOf，不是 oneOf。想改成 oneOf 还要再写一层 __get_pydantic_json_schema__，代码没有减少，反而增加。自定义类方案直接输出 oneOf。
        7. 顶层使用要额外包 RootModel。自定义类方案本身就是类型，可以直接作为字段类型使用。
    """
    def __new__(mcs, name, bases, namespace):
        definitions = {
            key: value for key, value in namespace.items() if isinstance(value, OptionItem)
        }

        inherited_members = [
            base.__name__
            for base in bases
            if getattr(base, "__members__", {})
        ]
        if inherited_members:
            raise TypeError(
                f"{name} cannot inherit Option members from "
                f"{', '.join(inherited_members)}"
            )
        # ``Option`` itself and the abstract ``Options`` base are allowed to
        # have no members.  Every user-defined concrete subtype must declare
        # at least one member, so an empty subtype cannot silently become an
        # unusable option type.
        allow_empty = bool(namespace.get("__option_allow_empty__", False))
        if bases and not definitions and not allow_empty:
            raise TypeError(f"{name} must define at least one OptionItem")

        cls = super().__new__(mcs, name, bases, namespace)

        members: dict[str, Option] = {}
        values: dict[Any, str] = {}
        for member_name, item in definitions.items():
            if item.value in values:
                previous = values[item.value]
                raise ValueError(
                    f"{name} has duplicate option value {item.value!r} "
                    f"for {previous!r} and {member_name!r}"
                )

            member = object.__new__(cls)
            member.name = member_name
            member.value = item.value
            member.option_item = item
            item.apply_default_metadata(name, member_name)
            members[member_name] = member
            values[item.value] = member_name
            setattr(cls, member_name, member)

        types = {item._core_type for item in definitions.values()}
        if len(types) > 1:
            type_names = ", ".join(sorted(t.__name__ for t in types))
            raise TypeError(f"{name} option values must use one core type, got: {type_names}")

        cls.__members__ = MappingProxyType(members)
        cls._value2member_map_ = {
            member.value: member for member in members.values()
        }
        return cls

    def __call__(cls, value: Any):
        if isinstance(value, cls):
            return value
        try:
            return cls._value2member_map_[value]
        except (KeyError, TypeError):
            valid = set(cls._value2member_map_)
            raise ValueError(f"{value!r} 不是合法选项，合法值: {valid}") from None

    def __iter__(cls):
        return iter(cls.__members__.values())

    def __reversed__(cls):
        return reversed(tuple(cls.__members__.values()))

    def __len__(cls):
        return len(cls.__members__)

    def __contains__(cls, value: Any):
        if isinstance(value, cls):
            return True
        try:
            return value in cls._value2member_map_
        except TypeError:
            return False

    def __getitem__(cls, name: str):
        return cls.__members__[name]


class Option(metaclass=OptionMeta):
    """Enum-like option type with Pydantic schema metadata.

    Define each option member with :class:`OptionItem`.  When the option type
    is used as a Pydantic model field, ``Option.field`` adds metadata to the
    field schema.  The schema contains one branch for every option member;
    each branch includes the member's value, type, default, and member-level
    metadata.

    UI display (dropdown, ``HIGH`` selected)::
        ┌─────────────────────────┐
        │ Priority                │
        ├─────────────────────────┤
        │ ▸ HIGH    高优先级       │
        │   MEDIUM  中优先级       │
        │   LOW     低优先级       │
        └─────────────────────────┘

    Args:
        title (str | None): Display title for the Option field.  This is a
            standard Pydantic field value and is omitted from the schema when
            it is ``None``.
        description (str | None): Description for the Option field.  This is
            a standard Pydantic field value and is omitted from the schema
            when it is ``None``.
        hide (bool | None): UI visibility metadata for the Option field.
            The default is ``False``.  Passing ``None`` omits ``hide`` from
            the schema.
        icon (str | None): UI icon metadata for the Option field.  It is
            omitted from the schema when it is ``None``.
        alias (str | None): UI alias metadata for the Option field.  It is
            reserved for future Pydantic alias support and currently has no
            effect.
        depends (str | None): Dependency value used by the UI to decide
            whether to display this Option field.  The field is displayed
            when the referenced option has this value.  It is omitted from
            the schema when it is ``None``.
        default (Any): Default value accepted by ``pydantic.Field``.  When
            provided, it must be an Option member or a list of Option members
            for a ``list[Option]`` field.  It is serialized as the underlying
            value or values.  Raw values such as ``"fast"`` are not accepted.
            ``default`` and ``default_factory`` must not be used together.
        default_factory (Callable): Factory accepted by ``pydantic.Field``
            for creating the default value at model construction time.  The
            factory result is validated as an Option value.  The callable
            itself is not serialized into JSON Schema.
        json_schema_extra (dict[str, Any] | None): Additional schema metadata
            to merge with ``hide``, ``icon``, and ``depends``.  Values in this
            mapping take precedence over those built-in metadata fields.
        **kwargs (Any): Other keyword arguments accepted by
            ``pydantic.Field``.  ``title``, ``description``, ``default``, and
            ``default_factory`` are the supported field controls documented
            above.

    Notes:
        The Option schema root has ``type="Option"``.  Each member branch has
        its concrete value type, such as ``string`` or ``integer``.  The
        member type is generated from the common value type of the Option
        members.  ``readOnly`` is a member-level OptionItem setting, not an
        Option field setting.

    Example:
        ```python
        class Priority(Option):
            HIGH = OptionItem.str("high", title="高优先级")

        class Config(BaseModel):
            priority: Priority = Option.field(description="选择优先级")
        ```
    """

    __members__: ClassVar[dict[str, "Option"]]

    def __repr__(self) -> str:
        return f"{type(self).__name__}.{self.name}"

    def __str__(self) -> str:
        return str(self.value)

    def __eq__(self, other: Any) -> bool:
        if isinstance(other, Option):
            return type(self) is type(other) and self.value == other.value
        return self.value == other

    def __hash__(self) -> int:
        return hash(self.value)

    @classmethod
    def field(
        cls,
        *,
        hide: bool | None = False,
        icon: str | None = None,
        alias: str | None = None,
        depends: str | None = None,
        json_schema_extra: dict[str, Any] | None = None,
        **kwargs: Any,
    ) -> FieldInfo:
        if json_schema_extra is not None and not isinstance(json_schema_extra, dict):
            raise TypeError("json_schema_extra must be a dictionary")

        extra: dict[str, Any] = {}
        if hide is not None:
            extra["hide"] = hide
        if icon is not None:
            extra["icon"] = icon
        if depends is not None:
            extra["depends"] = depends
        extra.update(json_schema_extra or {})
        # ``alias`` is intentionally reserved for future Pydantic alias
        # support.  It is accepted by the signature but currently ignored.
        del alias
        kwargs["validate_default"] = True
        is_multi = bool(getattr(cls, "__option_is_multi__", False))
        if "default" in kwargs:
            default = kwargs["default"]
            if is_multi:
                valid_default = isinstance(default, list) and all(
                    isinstance(item, cls) for item in default
                )
            else:
                valid_default = isinstance(default, cls)
            if not valid_default:
                raise TypeError(
                    "Options.field default must be a list of members"
                    if is_multi
                    else "Option.field default must be an Option member"
                )
            if not is_multi:
                kwargs["default"] = default.value
            else:
                kwargs["default"] = [item.value for item in default]
        return Field(**kwargs, json_schema_extra=extra)

    @classmethod
    def _core_type(cls) -> type:
        members = list(cls.__members__.values())
        return members[0].option_item._core_type if members else str

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> CoreSchema:
        core_type = cls._core_type()
        if core_type is bool:
            value_schema = core_schema.bool_schema()
        elif core_type is int:
            value_schema = core_schema.int_schema()
        elif core_type is float:
            value_schema = core_schema.float_schema()
        else:
            value_schema = core_schema.str_schema()

        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.no_info_before_validator_function(
                cls._unwrap_input,
                value_schema,
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda value: value.value,
            ),
        )

    @classmethod
    def _unwrap_input(cls, value: Any) -> Any:
        if isinstance(value, cls):
            return value.value
        if isinstance(value, OptionItem):
            return value.value
        return value

    @classmethod
    def _validate(cls, value: Any) -> "Option":
        return cls(value)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        schema = handler.resolve_ref_schema(handler(core_schema))
        schema.pop("enum", None)
        schema.pop("type", None)
        schema["type"] = "Option"
        schema["oneOf"] = [cls._member_schema(member) for member in cls]
        return schema

    @classmethod
    def _member_schema(cls, member: "Option") -> dict[str, Any]:
        item = member.option_item
        schema = TypeAdapter(
            Annotated[Literal[member.value], item.field_info]
        ).json_schema()
        return schema


class Options(Option):
    """Enum-like multi-select option type with Pydantic schema metadata.

    Define each member with :class:`OptionItem`, just as with :class:`Option`.
    When a concrete ``Options`` type is used as a Pydantic model field, the
    field value is a list of that type's members.  The generated schema uses
    ``type="Options"`` and places the member branches under ``items.oneOf``.
    The same member type can therefore describe both the selectable values and
    the list returned by validation.

    UI display (2x3 grid, ``HIGH`` and ``MEDIUM`` selected)::
        ┌────────────┬────────────┬────────────┐
        │ ▣ HIGH     │ ▣ MEDIUM   │ □ LOW      │
        ├────────────┼────────────┼────────────┤
        │ □ AUTO     │ □ SAFE     │ □ CUSTOM   │
        └────────────┴────────────┴────────────┘

    Args:
        title (str | None): Display title for the Options field.  This is a
            standard Pydantic field value and is omitted from the schema when
            it is ``None``.
        description (str | None): Description for the Options field.  This is
            a standard Pydantic field value and is omitted from the schema
            when it is ``None``.
        hide (bool | None): UI visibility metadata for the Options field.  The
            default is ``False``.  Passing ``None`` omits ``hide``.
        icon (str | None): UI icon metadata for the Options field.  It is
            omitted when it is ``None``.
        alias (str | None): Reserved field alias parameter.  It is accepted
            for API compatibility but currently has no effect.
        depends (str | None): Dependency value used by the UI to decide
            whether to display this Options field.  It is omitted when it is
            ``None``.
        default (list[Options]): Default list of members.  Every item must be
            a member of the concrete Options subtype; raw values are rejected.
            ``default`` and ``default_factory`` cannot be used together.
        default_factory (Callable): Factory accepted by ``pydantic.Field``.
            Its result is validated as a list of Options members.
        json_schema_extra (dict[str, Any] | None): Additional schema metadata
            merged into the field schema.  Values in this mapping take
            precedence over built-in ``hide``, ``icon``, and ``depends``.
        **kwargs (Any): Other keyword arguments accepted by ``pydantic.Field``.

    Notes:
        The validated runtime value is ``list[Options]`` and each item is a
        concrete member such as ``Prioritys.HIGH``.  Python and JSON dumps
        serialize the list to the members' underlying values, for example
        ``["high", "medium"]``.  Duplicate removal and member ordering are
        intentionally left for a later policy decision.

    Example:
        ```python
        class Prioritys(Options):
            HIGH = OptionItem.str("high", title="高优先级")
            LOW = OptionItem.str("low", title="低优先级")

        class Config(BaseModel):
            prioritys: Prioritys = Options.field(
                description="选择多个优先级",
                default=[Prioritys.HIGH],
            )
        ```
    """

    # The metaclass uses this marker to permit this abstract base to be empty.
    __option_allow_empty__ = True
    __option_is_multi__ = True

    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: Any) -> CoreSchema:
        """
        为 Options 创建多选成员并提供 Enum 风格的访问接口。
        评估的 list[Priority] 方案，用法如下：
        ```python
        class Config(BaseModel):
            tags: list[Priority] = Option.field(description="选标签")
        ```
        对比 Options(Option) 方案，否决它的重要原因：
            1. 没有多选专属类型。list[Priority] 只是一个普通列表，多选这个概念在类型上不可见，去重、排序、schema 标记没有地方内聚。
            2. 字段声明冗长。要加去重排序得写 Annotated[list[Priority], AfterValidator(...)]，加 schema 标记还要再叠 Field，每个多选字段都要重复一遍。
            3. 和单选不对称。单选是 priority: Priority，多选变成 tags: Annotated[list[Priority], ...]，两种风格，使用者要记两套写法。
            4. 去重排序语义不统一。写在每个字段的 AfterValidator 里，逻辑分散，改一处忘一处，多个字段行为可能不一致。
            5. schema 标记难加。想在 items 层级加 x-multiple 之类的标记，得靠 WithJsonSchema 完全接管 schema，手写一大坨，反而更容易出错。
            6. 无法复用 Option 的成员校验。list[Priority] 靠 Priority 自己校验，但多选容器自己的逻辑（去重、排序、数量约束）没有归属，只能散在字段上。
            7. 无法区分单选多选。类型都是 Option 子类或 list，前端拿到 schema 只能靠 type: array 猜，没有显式的多选标记。
        对比 Annotated[list[Priority]] 方案，否决它的重要原因：
            8. 字段声明冗长。每个多选字段都要写一长串 Annotated，和单选的 priority: Priority 风格不一致。
            9. 和单选不对称。单选一个类型名，多选一长串组合，两种写法并存，记忆负担大。
            10. 逻辑分散。去重、排序、schema 标记散在 Annotated 的各个参数里，没有统一归属，修改时要逐个字段找。
            11. 无法内聚多选行为。多选作为一种类型语义，没有自己的类型承载，只能靠注解拼装，复用性差。
            12. 无法复用 Option 的成员 schema。每个字段各自生成 items.oneOf，没有统一入口，多个多选字段容易生成不一致的 schema。
        Options(Option) 方案保留的原因：
            13. 接口对称。单选 priority: Priority，多选 prioritys: Prioritys，都是 X: Type，风格一致。
            14. 多选行为内聚。去重、排序、数量约束、schema 标记全部收进 Options，改一处全局生效。
            15. 复用现有定义。OptionItem、OptionMeta、成员校验逻辑大部分继承，不用重写。
            16. schema 结构可控。oneOf 下移到 items、加 x-multiple 标记，都在 __get_pydantic_json_schema__ 里统一处理。
            17. 成员定义单一数据源。Prioritys.HIGH 的 title、description、x-color 写在成员里，schema 自动读取，不用两处手写。
            18. 顶层可直接用。Prioritys 本身就是类型，不需要额外包 RootModel。
        """
        core_type = cls._core_type()
        if core_type is bool:
            value_schema = core_schema.bool_schema()
        elif core_type is int:
            value_schema = core_schema.int_schema()
        elif core_type is float:
            value_schema = core_schema.float_schema()
        else:
            value_schema = core_schema.str_schema()

        return core_schema.no_info_after_validator_function(
            cls._validate,
            core_schema.no_info_before_validator_function(
                cls._unwrap_input,
                core_schema.list_schema(value_schema),
            ),
            serialization=core_schema.plain_serializer_function_ser_schema(
                lambda value: [item.value for item in value],
            ),
        )

    @classmethod
    def _unwrap_input(cls, value: Any) -> Any:
        if not isinstance(value, (list, tuple)):
            return value
        return [
            item.value
            if isinstance(item, cls)
            else item.value
            if isinstance(item, OptionItem)
            else item
            for item in value
        ]

    @classmethod
    def _validate(cls, value: Any) -> list["Options"]:
        # TODO: decide and implement duplicate removal and member ordering.
        return [cls(item) for item in value]

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: CoreSchema, handler: GetJsonSchemaHandler
    ) -> JsonSchemaValue:
        schema = handler.resolve_ref_schema(handler(core_schema))
        schema["type"] = "Options"
        schema["items"] = {
            "type": "Option",
            "oneOf": [cls._member_schema(member) for member in cls],
        }
        return schema
