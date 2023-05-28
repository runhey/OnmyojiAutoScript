import QtQuick
import QtQuick.Controls
import FluentUI
import "../Component"
import "../Global"

SplitPanel{

    property string configName: ""
    onTitleChanged: {
        if(title === qsTr("Overview")){
            showDefalut()
        }
        else{
            var component = Qt.createComponent("../../qml/Component/Args.qml")
            if (component.status === Component.Ready) {
                setLoader(component)
            }else{
                // 组件加载失败
            }
        }
    }


    Component.onCompleted:{
        var data = {'Overview':[], 'Script': ['Script', 'General', 'Restart']}
        create(data)

        var component = Qt.createComponent("../../qml/Component/Overview.qml")
        if (component.status === Component.Ready) {
            setDefalut(component)
        } else {
            // 组件加载失败
            console.debug('组件加载失败')
        }
    }
}
