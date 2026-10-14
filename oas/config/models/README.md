







### Option

```python
class OptionItem(xxx):
    ...
    
    @classmethod
    def str(cls, xxx) -> Field:
        """ 这个是一个工厂函数(后面需要有同时支持int,float这些基础的)， 可以是类方法或者是纯函数, 输入是自定义的schema，"""
        ...
        return Field(xxx)
    

class Option(xxx):
    HIGH: OptionItem = OptionItem.str(default='xx',title="高优先级", description="最紧急")
    LOW: OptionItem = OptionItem.str(default='xx',title="低优先级", description="xxx")
    
    ...
    
    @classmethod
    def field(cls, xxx):
        """
        和上面的工厂函数类似，也是返回一个
        也是把额外的schema注入到Field里面去
        """
        return Field(xxx)
    
    
class Config(BaseModel):
    priority: Option = Option.new(description="选个优先级")

```
1. Option用法类似enum, 比如常见的相等，
2. 最终OptionItem 的 schema 每个选项独立，且 type、title、default 这些标准键都在。
3. 接口简洁，越少越好 
4. 用法兼容enum的常见用法。
5. schema这个非常重要，我希望OptionItem导出的shema每一个选项都是独立的，保持标准的比如description、type我也不知道标准的有什么。



### Options

```python
class OptionItem 和 上面一致

class Options(Option):
    ...

class Prioritys(Options):
    HIGH: OptionItem = OptionItem.str(default='xx',title="高优先级", description="最紧急")
    LOW: OptionItem = OptionItem.str(default='xx',title="低优先级", description="xxx")
    
    ...
    
    @classmethod
    def field(cls, xxx):
        """
        函数保持和Options一致，不过default是list
        """
        return Field(xxx)
    
    @classmethod
    def annotated(cls):
        return Annotated(
            list["Prioritys"],
            ... 自定义的一下
        )
    
    
class Config(BaseModel):
    prioritys: Prioritys = Options.field(description="选个优先级")
    # 这里我希望坚持的一个点是prioritys:类型标注是Prioritys本身，

```

1. 保持接口整洁，
2. schema json 类似于Option


### Task 使用 Group 时的动态覆盖

Group 自己只定义通用的字段、校验规则和默认 UI 元数据。某个 Task 使用
Group 时，如果只希望修改当前 Task 的显示效果，例如隐藏
`SchedulerGroup.server_update`，不应该修改 Group 的公共定义，否则所有引用
这个 Group 的 Task 都会受到影响。

这里的覆盖属于 **Task 使用 Group 时的局部配置**。它只改变当前 Task 导出的
schema/UI 元数据，可以覆盖 `hide`、`icon`、`title`、`description` 等字段，
不改变 Group 的 Python 类型，也不改变 Pydantic 的值校验和运行时数据。

覆盖的目标可以抽象成：

```text
Task
└── group_overrides
    └── scheduler
        └── server_update
            └── hide = true
```

schema 生成阶段读取 Task 的覆盖配置，把它应用到对应 Group 的 schema；其他
Task 仍然使用 Group 的原始定义。覆盖配置应当保持声明式、集中且容易搜索，
避免把同一份规则分散到多个解析器或运行时分支中。

#### 六种覆盖方案对比

| 方案 | 覆盖配置放置位置 | 示例形式 | 作用范围 | 优点 | 缺点 | 适合场景 | 推荐度 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **1. Task 类属性** | Task 类的专用类属性，例如 `group_overrides` | `group_overrides = {"scheduler": {"server_update": {"hide": True}}}` | 当前 Task | 配置集中；不污染 Group；声明式；容易搜索、调试和生成 schema；不同 Task 之间天然隔离 | 需要 schema 生成器约定并读取这个类属性；覆盖字典缺少静态类型提示 | 大多数固定的 Task 专属隐藏和 UI 覆盖 | **最高** |
| **2. Task 内嵌配置类** | Task 内部专门的覆盖模型，例如 `SchemaOverrides` | `class SchemaOverrides(BaseModel): ...` | 当前 Task | 有 Pydantic 校验和类型提示；层级结构清楚；覆盖项很多时比深层字典更易维护 | 类数量增加；简单覆盖显得稍重；动态路径仍需额外表达 | 一个 Task 有大量覆盖项，或覆盖内容需要严格校验 | 高 |
| **3. Task 类方法** | Task 提供 `schema_overrides()` 或类似方法 | `@classmethod def schema_overrides(cls): return {...}` | 当前 Task，可根据条件变化 | 可以根据 Task 类型、环境或其他配置动态生成；能复用辅助逻辑 | 配置隐藏在代码逻辑中；不如静态表直观；可能产生不可预测的 schema | 覆盖规则确实依赖条件，静态配置无法表达 | 中 |
| **4. Task 装饰器** | Task 类定义外的装饰器参数 | `@group_overrides(scheduler={...})` | 当前 Task | 使用位置醒目；Task 字段声明保持干净；可以封装校验 | 需要实现装饰器和元数据保存机制；调试时要追踪装饰器；IDE 和静态搜索体验较弱 | 希望把覆盖声明放在类定义正上方，且项目愿意维护装饰器 API | 中低 |
| **5. 外部注册表** | 独立模块或配置表，按 Task 名称注册覆盖 | `OVERRIDES[FindJadeTask] = {...}` | 注册表指定的 Task | Task 模型完全不包含 UI 覆盖；可集中批量管理或自动生成 | 配置与 Task 分离；容易出现名称失配或忘记注册；阅读 Task 时看不到实际 UI 行为 | 覆盖规则由外部系统生成，或需要统一批量管理多个 Task | 低 |
| **6. `Group.field()` 参数** | Task 声明 Group 字段时传入 `overrides` | `scheduler = Group.field(overrides={...})` | 当前字段实例 | 作用对象最明确；离被覆盖的 Group 字段最近；不需要额外的 Task 配置入口 | 字段声明会变得很重；多个 Group 和多个 Arg 时可读性快速下降；Group 字段定义与 UI 覆盖耦合 | 覆盖非常少、字段只有一两个的简单场景 | 不建议作为主方案 |

#### 方案选择

默认采用 **方案 1：Task 类属性**。它在简洁性、隔离性和可维护性之间最平衡：

- Group 保持自己的公共定义；
- Task 只声明自己的差异；
- `Group.field()` 保持轻量；
- schema 生成器只有一个统一入口；
- 将来需要严格校验时，可以把类属性的值替换为方案 2 的配置模型，而不改变
  Task 与 Group 的整体关系。

方案 3 只用于真正需要条件计算的覆盖；方案 4 和方案 5 暂不作为默认 API；
方案 6 可以保留为极少量局部覆盖的兼容写法，但不应承载完整的覆盖系统。


#### `schema_overrides()`、`SchemaRule` 与专用装饰器

Task 的 Group 覆盖采用“规则声明”和“规则执行”分离的设计：装饰器只负责
在类定义阶段记录规则，统一处理器在导出 schema 时执行规则。规则归属于具体
的 Task 类，并使用一个类级临时缓冲区保存用户在导出前手动登记的规则，不放在
一个全局的 `schema` 状态表中，因此不同 Task 之间不会互相污染。

```text
schema
└── 只提供装饰器语法，生成 SchemaRule

Task 类
└── schema_overrides.__oas_schema_rules__: tuple[SchemaRule, ...]

Task 类的临时导出缓冲区
└── _pending_schema_rules: list[SchemaRule]
```

```python
from dataclasses import dataclass
from typing import Any, Callable, Literal

Operation = Literal["set", "merge", "delete", "replace"]


@dataclass(frozen=True, slots=True)
class SchemaRule:
    target: str
    property: str | None = None
    operation: Operation = "set"
    value: Any = None
    when: Callable[["SchemaContext"], bool] | None = None
```

| 字段 | 含义 |
|---|---|
| `target` | 目标 Group 或 Arg 的点号路径，例如 `scheduler.server_update` |
| `property` | 要修改的 schema 属性；`None` 表示操作整个目标节点 |
| `operation` | `set`、`merge`、`delete` 或 `replace` |
| `value` | 新值、合并字典或完整替换节点 |
| `when` | 可选条件，接收 `SchemaContext`，返回真值时才执行 |

装饰器是 `SchemaRule` 的语法糖。每个装饰器可以接收一个或多个目标路径，
并把规则记录到被装饰函数的元数据上。导出时沿 Task 的继承链直接读取这些
函数元数据，不再复制到另一个 `__schema_rules__` 属性。用户需要临时覆盖时，手动调用
`schema_overrides(rules)`，把传入的规则记录到 `_pending_schema_rules`。两类规则
使用完全相同的 `SchemaRule` 类型。

```python
class Task(TaskBase):
    __schema_rules__: tuple[SchemaRule, ...]

    @classmethod
    @schema.hide("scheduler.server_update")
    @schema.title("scheduler.server_update", value="服务器更新")
    @schema.icon("scheduler.server_update", value="refresh")
    def schema_overrides(cls, rules: list[SchemaRule]):
        # 用户显式调用 schema_overrides(rules) 时登记传入规则
        for rule in rules:
            cls._pending_schema_rules.append(rule)


# 导出前由用户显式登记临时规则
Task.schema_overrides(
    [
        SchemaRule(
            target="scheduler.server_update",
            property="hide",
            value=True,
        )
    ]
)
Task.model_json_schema()
```

规则应用顺序为：

```text
Group/Arg 原始 schema
    ↓
字段自身的 json_schema_extra
    ↓
schema_overrides 函数元数据（类定义规则）
    ↓
Task._pending_schema_rules（导出前手动登记的临时规则）
    ↓
当前 Task 的最终 schema
```

同一个目标和属性后应用的规则覆盖先应用的规则。导出完成后，无论成功或失败，
`_pending_schema_rules` 都会清空。

| `operation` | `property` | 作用 | 示例 |
|---|---|---|---|
| `set` | 属性名 | 设置一个 schema 属性 | `property="hide", value=True` |
| `merge` | `None` 或属性名 | 合并对象内容 | 一次设置 `hide`、`icon`、`title` |
| `delete` | 属性名或 `None` | 删除一个属性或整个目标节点 | 删除 `description`；删除整个 Arg |
| `replace` | `None` | 用完整 schema 替换整个目标节点 | 替换一个 Arg 的全部 schema 信息 |

修改单个属性时使用对应的专用装饰器：

```python
@schema.hide("scheduler.server_update", value=True)
@schema.icon("scheduler.server_update", value="refresh")
def schema_overrides(cls, rules: list[SchemaRule]):
    ...
```

一次修改一个 Arg 的多个属性时，可以使用 `merge`：

```python
SchemaRule(
    target="scheduler.server_update",
    operation="merge",
    value={
        "hide": True,
        "icon": "refresh",
        "title": "服务器更新",
    },
)
```

如果需要改写这个 Arg 的全部 schema 信息，使用 `replace`。此时不填写
`property`，`value` 必须是完整的目标 schema：

```python
SchemaRule(
    target="scheduler.server_update",
    operation="replace",
    value={
        "type": "Switch",
        "default": False,
        "hide": True,
        "icon": "refresh",
    },
)
```

`replace` 只替换当前 Task 导出的 schema 节点，不修改 Group 类、Arg 的
Pydantic 校验规则或运行时数据模型。替换内容需要由统一处理器校验为合法的
schema 节点；如果只是补充或修改少数属性，应优先使用 `set` 或 `merge`，以
保留原始节点中未覆盖的字段。

| 分类 | 规范 |
|---|---|
| 规则归属 | 类定义装饰器规则放在 `schema_overrides` 函数元数据；手动登记规则放在 `_pending_schema_rules` |
| 装饰器职责 | 只在类定义阶段创建和登记规则，不调用 `schema_overrides()`，不修改 schema |
| `schema_overrides()` 职责 | 用户显式传入 `list[SchemaRule]`，把规则登记到 `_pending_schema_rules` |
| Hook 职责 | `__get_pydantic_json_schema__()` 只读取、执行并清空两类规则，不调用 `schema_overrides()` |
| 目标路径 | 使用点号路径定位 Group 或 Arg，例如 `scheduler.server_update` |
| Task 隔离 | 规则只作用于声明它的 Task，不改变公共 Group 定义 |
| 继承 | 父 Task 规则先收集，子 Task 规则后收集 |
| 条件 | `when` 通过 `SchemaContext` 判断是否应用规则 |
| 校验 | 目标路径不存在、操作不匹配或替换节点无效时导出失败并抛出明确异常 |
| 输出 | 原始 schema 不被污染，最终结果是当前 Task 的独立 schema |


### 动态 Group 的 OAS 与 Alasio 方案

动态 Group 允许 Task 在运行时增加或删除任意数量的 Group 实例。由于数量在
运行时才确定，不能把每一个实例预先定义成 Pydantic 模型字段。OAS 采用
**容器作为内存模型、边界处扁平化**的方式：内存中使用 `list[Group]` 或带有
顺序信息的字典；写入数据库、导出给 UI 时，再转换成
`group_me_1.field`、`group_me_2.field` 这样的扁平键。

这样既可以在运行时自由增删 Group，也可以保持数据库和 UI 的扁平格式。转换
只发生在边界，不改变内存中的业务模型。

| 对比维度 | OAS：容器模型，边界扁平化 | Alasio：生成时扁平化 | 主要差异 |
| --- | --- | --- | --- |
| **配置定义** | Python/Pydantic 定义 Group 类型；Task 持有一个动态容器 | YAML 定义动态 Group；构建器生成固定的扁平字段 | OAS 以 Python 为唯一源；Alasio 以 YAML 和生成器为中心 |
| **运行时内存** | `list[GroupMe]` 或有序字典；可随时新增、删除、排序 | msgspec Struct 的扁平字段，例如 `group_me_count`、`group_me_1`、`group_me_2` | OAS 适合运行时动态数量；Alasio 模型本身没有列表 |
| **运行时增加 Group** | 直接向内存容器追加一个 Group 实例，数量不受模型字段数量限制 | 可以在预生成的 `group_me_1` 到 `group_me_N` 槽位内增加 Group；超过 `N` 时无法新增。增加上限必须回到构建期重新运行 `config_dev` 生成模型 | Alasio 可以运行时增行，但上限由构建期固定的槽位数决定；重新生成不是运行时操作 |
| **运行时删除 Group** | 从容器删除实例，剩余实例可重新编号 | 通常清空或重写对应扁平字段，并维护 count | OAS 操作列表更自然 |
| **业务逻辑访问** | 直接遍历 `list[GroupMe]`；不需要转换 | 调用 `dynamic.to_list(...)` 临时聚合 | OAS 的列表是本体；Alasio 的列表是视图 |
| **内存中的校验** | 每个容器元素都是 Pydantic Group，创建和修改时校验 | 每个扁平字段由 msgspec Struct 校验 | 校验对象不同，但都可以保持类型约束 |
| **数据库保存** | 保存前调用 `to_flat_dict()`，写成 `group_me_count`、`group_me_1.field` 等键值 | UI/业务先把编辑中的 list 视图交给 `dynamic.to_dict(list, prefix="...")` 展平成 `group_me_count`、`group_me_1.field` 等键值，再和 Group 的其他字段一起写入 SQLite | 两者最终都保存扁平键值；Alasio 的 list 视图落库前同样必须经过展开 |
| **数据库读取** | 读取扁平键后调用 `from_flat_dict()`，恢复成内存容器 | 直接解码成扁平 Struct | OAS 多一次边界转换 |
| **UI Schema** | 从 Group 的 schema 生成动态组模板，再展开成当前实例的扁平字段 | 使用构建器生成的扁平字段 schema | OAS 需要明确动态字段命名规则和展开器 |
| **UI 配置值** | 导出为 `group_me_1.name`、`group_me_2.name` 等扁平键 | 直接导出 Struct 的同名扁平字段 | UI 接收的数据格式可以保持一致 |
| **Group 数量** | 容器长度是真实数量；导出时生成 count 或从键集合计算 | 由生成字段和 `*_count` 管理 | OAS 不需要预先知道最大数量 |
| **schema 稳定性** | Group item schema 稳定，实例字段数量可以随当前容器展开 | 字段数量和 schema 在构建期确定，运行时不可改变；最大行数 `N` 由生成器预生成的 `*_1.*` 到 `*_N.*` 决定 | OAS 的动态 schema 可按当前配置生成或使用模板；Alasio 的槽位上限和字段 schema 固定 |
| **序号处理** | 展平时按容器顺序生成 `_1`、`_2`；从 list 删除后，剩余元素自然前移并重新编号 | `_1`、`_2` 是固定槽位号；删除一行通常清空该槽位，不把后面的槽位前移，由 `*_count` 标记有效行数 | OAS 的序号是容器顺序；Alasio 的序号是槽位编号 |
| **序列化职责** | `to_flat_dict()` / `from_flat_dict()` 是明确的边界适配器 | Struct 的编码器直接处理扁平字段 | OAS 不应依赖 Pydantic serializer 改变内存模型 |
| **优点** | 支持真正的运行时增删；业务代码自然；Group 类型可复用 | 运行时结构和持久化结构完全一致；无需额外展开 | OAS 灵活，Alasio 扁平链路简单 |
| **代价** | 需要维护容器与扁平字段之间的双向转换 | 动态数量受生成字段限制；模型不适合运行时加字段 | 两者是在灵活性和边界转换之间取舍 |

#### OAS 采用的最终方向

```text
内存：list[GroupMe] 或有序容器
    ↓ to_flat_dict()
数据库 / UI：group_me_1.field、group_me_2.field、...
    ↓ from_flat_dict()
内存：list[GroupMe] 或有序容器
```

OAS 不再尝试让 Pydantic 模型本身动态增加字段，也不把动态 Group 预先生成成
固定数量的字段。扁平格式只属于数据库和 UI 边界，容器格式属于运行时业务模型。
