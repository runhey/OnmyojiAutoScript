import QtQuick
import QtQuick.Controls
import FluentUI
import "../Component"
import "../Global"

SplitPanel{

    property string configName: ""


    Component.onCompleted:{
        var data = {'OverView':[], 'Script': ['Script', 'General', 'Restart']}
        create(data)

        var component = Qt.createComponent("../../qml/Component/OverView.qml")
        if (component.status === Component.Ready) {
            setDefalut(component)
        } else {
            // 组件加载失败
        }
    }
}
