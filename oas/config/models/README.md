







### Option

```python
class OptionItem(xxx):
    ...

    @classmethod
    def str(cls, xxx) -> Field:
        """这个是一个工厂函数(后面需要有同时支持int,float这些基础的)， 可以是类方法或者是纯函数, 输入是自定义的schema，"""
        ...
        return Field(xxx)


class Option(xxx):
    HIGH: OptionItem = OptionItem.str(
        default='xx', title='高优先级', description='最紧急'
    )
    LOW: OptionItem = OptionItem.str(default='xx', title='低优先级', description='xxx')

    ...

    @classmethod
    def field(cls, xxx):
        """
        和上面的工厂函数类似，也是返回一个
        也是把额外的schema注入到Field里面去
        """
        return Field(xxx)


class Config(BaseModel):
    priority: Option = Option.new(description='选个优先级')
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

Operation = Literal['set', 'merge', 'delete', 'replace']


@dataclass(frozen=True, slots=True)
class SchemaRule:
    target: str
    property: str | None = None
    operation: Operation = 'set'
    value: Any = None
    when: Callable[['SchemaContext'], bool] | None = None
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
    @schema.hide('scheduler.server_update')
    @schema.title('scheduler.server_update', value='服务器更新')
    @schema.icon('scheduler.server_update', value='refresh')
    def schema_overrides(cls, rules: list[SchemaRule]):
        # 用户显式调用 schema_overrides(rules) 时登记传入规则
        for rule in rules:
            cls._pending_schema_rules.append(rule)


# 导出前由用户显式登记临时规则
Task.schema_overrides(
    [
        SchemaRule(
            target='scheduler.server_update',
            property='hide',
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
@schema.hide('scheduler.server_update', value=True)
@schema.icon('scheduler.server_update', value='refresh')
def schema_overrides(cls, rules: list[SchemaRule]): ...
```

一次修改一个 Arg 的多个属性时，可以使用 `merge`：

```python
SchemaRule(
    target='scheduler.server_update',
    operation='merge',
    value={
        'hide': True,
        'icon': 'refresh',
        'title': '服务器更新',
    },
)
```

如果需要改写这个 Arg 的全部 schema 信息，使用 `replace`。此时不填写
`property`，`value` 必须是完整的目标 schema：

```python
SchemaRule(
    target='scheduler.server_update',
    operation='replace',
    value={
        'type': 'Switch',
        'default': False,
        'hide': True,
        'icon': 'refresh',
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


### 动态 Group 的 JSON 导出

#### 已确定的模型

Task 使用 `groups: list[GroupMe]` 保存运行时数量不固定的 Group。列表是 Task
内存中的实际数据结构，不为每个实例声明单独的 Pydantic 字段：

```python
class Task(TaskBase):
    groups: list[GroupMe] = Field(default_factory=list)
```

每个列表元素都是一个经过 Pydantic 校验的 `GroupMe` 实例。新增时向列表追加
实例；删除时移除对应元素。列表保留用户排列顺序，因此删除中间项后，后面的
元素自然前移，不需要留下空位、维护 count 或给实例重新分配业务 ID。

#### 当前阶段：JSON

当前只实现 JSON 导出，直接使用 `model_dump(mode="json")` 的嵌套数组结构：

```json
{
  "groups": [
    {"name": "第一组", "enabled": true},
    {"name": "第二组", "enabled": false}
  ]
}
```

导出的数组顺序与 Task 中列表顺序一致。JSON 结果不展开成
`group_1.name`、`group_2.name` 这样的键，也不额外输出 Group 数量字段；数组本身
就能表达数量和顺序。空列表导出为 `"groups": []`。

#### 后续阶段：数据库

数据库实现完成后，每个 `GroupMe` 实例对应数据库中的一条 Group 记录。读取时按
数据库定义的顺序取回记录并组装成 `groups` 列表；保存和删除记录的细节由后续
数据库适配层负责。数据库尚未实现，因此当前 JSON 导出不调用数据库，也不定义
数据库表结构、主键或序号字段。

数据库适配应保持 Task 的 `groups: list[GroupMe]` 运行时接口。若数据库需要稳定
主键或显式排序字段，应在记录层处理，不把数据库标识混入当前 JSON Group 字段。

#### JSON Schema

Task 的 JSON Schema 应将 `groups` 描述为数组，并把 `GroupMe` 的模型 schema
作为数组元素 schema（`items`）。Schema 描述允许的 Group 结构，不应把当前列表
长度固化为固定字段数量或固定 `maxItems`。具体前端如何增加、删除或排序数组项，
由 UI 层消费该数组 schema 时实现。
