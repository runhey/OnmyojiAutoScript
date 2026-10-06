









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
    def new(cls, xxx):
        """
        和上面的工厂函数类似，也是返回一个, 不过new这个函数名不太好，看看下什么合适
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
