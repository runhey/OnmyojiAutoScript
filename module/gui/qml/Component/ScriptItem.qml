import QtQuick
import FluentUI
import "../Global/"

FluPaneItem{
    title: "home"
    icon:FluentIcons.Play36
    onTap:{
//        var component = Qt.createComponent("../../qml/Page/ScriptView.qml")
//        if (component.status === Component.Ready) {
//            var object = component.createObject(navigationView);

//            if (object !== null) {
//                object.configName = title
//                // 创建成功，可以进行操作
//                console.debug('创建成功')
//                navigationView.push(object)

//            }else{
//                // 创建失败
//            }
//        }else{
//            // 组件加载失败
//        }
    navigationView.pushScript(Qt.resolvedUrl("../../qml/Page/ScriptView.qml"), title)
        MainEvent.scriptName = title
    }
}
