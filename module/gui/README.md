### 在pyside6中不能直接使用qrc， 需要转成rcc

根目录有一个console.bat。打开进入命令行

```
where python
cd module/gui
pyside6-rcc -o qml_rcc.py qml.qrc
pyside6-rcc -o res_rcc.py res.qrc
```

即可生成rcc文件。当然当你每修改一次qrc指向的资源文件时候就需要运行一次

```
可以这样导入
import module.gui.qml_rcc, module.gui.res_rcc
```

**但是很显然由于qml文件需要修改不能将其每次都rcc一次**

所以可以使用

```
Qt.resolvedUrl("../../qml/Page/O_Settings.qml")
```







[在PyQt中使用qrc/rcc资源系统（PySide6-PyQt5） - 知乎 (zhihu.com)](https://zhuanlan.zhihu.com/p/590358586)
