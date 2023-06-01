import QtQuick
import QtQuick.Controls
import FluentUI
import "../Component"
import "../Global"

SplitPanel{

    property string configName: ""

    onTitleChanged: {
        if(title === "Overview"){
            showDefalut()
        }
        else{
            var component = Qt.createComponent("../../qml/Component/Args.qml")
            if (component.status === Component.Ready) {
                setLoader(component)
                var args = process_manager.gui_args(configName, title)
                var value = process_manager.gui_task(configName, title)
                setLoaderData(args, value)
                setLoaderContext(configName, title)
            }else{
                // 组件加载失败
            }
        }
    }

    onConfigNameChanged: {
        if(configName === ""){
            console.info('configname is emtry')
            return
        }
        var data = JSON.parse(process_manager.gui_menu(configName))
        create(data)
    }


    Component.onCompleted:{


//        var data = {'Overview':[], 'Script': ['Script', 'General', 'Restart']}


        var component = Qt.createComponent("../../qml/Component/Overview.qml")
        if (component.status === Component.Ready) {
            setDefalut(component)
        } else {
            // 组件加载失败
            console.debug('组件!加载失败')
        }
    }
}
