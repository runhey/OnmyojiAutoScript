# FluentUI

这个是很优秀的开源项目[zhuzichu520/FluentUI: FluentUI for QML (github.com)](https://github.com/zhuzichu520/FluentUI)



一方面由于其为新晋项目还需完善，另一方面在本项目中确实是需要一些特殊的需求

因此由如下方式使用：

1. Clone FluentUI repo to the root directory of this project
2. Modify the source code and record the changes
3. Build and generate the plugin by `msvc2019 release`
4. from `QT\6.4.3\msvc2019_64\qml` copy `Fluent` to `./module/gui`
5. from `bin/release` copy `fluent.dll` to `./toolkit`
6. 





# 修改

- FluWindow.qml

```qml
# 39行 对于可以正常显示的
return FluTheme.dark ? Qt.rgba(26/255,34/255,40/255,1) : Qt.rgba(238/255,244/255,249/255,1)
# 改为
return FluTheme.dark ? Qt.rgba(54/255,57/255,63/255,1) : Qt.rgba(249/255,249/255,249/255,1)
```

- FluNavigationView.qml

```qml
#470行 nav_app_bar 
注释掉RowLayout下的第一个FluIconButton
然后把Image这个替换成
Item{
                Layout.preferredHeight: 40
                Layout.preferredWidth: 40
                Layout.alignment: Qt.AlignVCenter
                Layout.leftMargin: 5
                Image{
                    width: 20
                    height: 20
                    anchors.centerIn: parent
                    id:image_logo
                    source: control.logo
                }
                MouseArea{
                    anchors.fill: parent
                    onClicked: Qt.openUrlExternally("https://github.com/runhey/OnmyojiAutoScript")
                }
            }
给RowLayout添加一个
FluText{
    Layout.alignment: Qt.AlignVCenter
    text: ">"
    Layout.leftMargin: 2
    font: FluTextStyle.Body
}
FluText{
    id: nav_app_bar_pane_title
    Layout.alignment: Qt.AlignVCenter
    text: ''
    Layout.leftMargin: 2
    font: FluTextStyle.Body
}
```

```
# 600行
改掉layout_list的witch从300->200
```

```qml
# 316行 com_panel_item对象
在MouseArea{onClick:}
添加一条nav_app_bar_pane_title.text = model.title


```

```
# 840 行

# 711 行的

```

```
# 742 行
topMargin = 0
```



- FluScrollablePage

```
# 46行

```

- FluTreeView

```
# 255行
在FluiconButton的属性上添加
                        width: 20
                        height: 20
```

