import QtQuick
import QtQuick.Controls
import FluentUI
import "../Component"
import "../Global"

SplitPanel{
    id: root

    property string configName: ""  //这个东西会在Nav内部赋值

    Timer{
        id: startPython
        interval: 400 // 定时器间隔为一秒
        repeat: false // 设置为一次性定时器
        onTriggered: {
            // 停止定时器
            process_manager.add(root.configName)
            startPython.stop()
        }
    }

    onTitleChanged: {
        // 如果是总览
        if(title === "Overview"){
            showDefalut()
        }
        //如果是其他的开发的工具
        else if(title === "Image Rule"){
            const component = Qt.createComponent("../../qml/Content/ImageRule.qml")
            if(component.status !== Component.Ready){
                console.error("image rule component is not ready")
                return
            }
            setLoader(component)
        }
        else if(title === "Ocr Rule"){
            const component = Qt.createComponent("../../qml/Content/OcrRule.qml")
            if(component.status !== Component.Ready){
                console.error("ocr rule component is not ready")
                return
            }
            setLoader(component)
        }
        else if(title === "Click Rule"){
            const component = Qt.createComponent("../../qml/Content/ClickRule.qml")
            if(component.status !== Component.Ready){
                console.error("click rule component is not ready")
                return
            }
            setLoader(component)
        }
        else if(title === "Long Click Rule"){
            const component = Qt.createComponent("../../qml/Content/LongClickRule.qml")
            if(component.status !== Component.Ready){
                console.error("long click rule component is not ready")
                return
            }
            setLoader(component)
        }
        else if(title === "Swipe Rule"){
            const component = Qt.createComponent("../../qml/Content/SwipeRule.qml")
            if(component.status !== Component.Ready){
                console.error("swipe rule component is not ready")
                return
            }
            setLoader(component)
        }
        else if(title === "List Rule"){
            const component = Qt.createComponent("../../qml/Content/ListRule.qml")
            if(component.status !== Component.Ready){
                console.error("ListRule rule component is not ready")
                return
            }
            setLoader(component)
        }
        else if(title === "TaskList"){
            const component = Qt.createComponent("../../qml/Content/TaskList.qml")
            if(component.status !== Component.Ready){
                console.error("TaskList component is not ready")
                return
            }
            setLoader(component)
        }


        //最后才是一般的参数页面
        else{
            const component = Qt.createComponent("../../qml/Component/Args.qml")
            if (component.status === Component.Ready) {
                setLoader(component)
                const args = process_manager.gui_args(configName, title)
                const value = process_manager.gui_task(configName, title)
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

        //创建左边的菜单
        const data = JSON.parse(process_manager.gui_menu())
        if(MainEvent.branch == 'master'){
            if('Tools' in data){
                delete data['Tools']
            }
        }

        create(data)

        // 点击的时候顺带创建 python 进程
        setDefalutConfig(configName)
        startPython.start()
    }


    Component.onCompleted:{

        const component = Qt.createComponent("../../qml/Component/Overview.qml")
        if (component.status === Component.Ready) {
            setDefalut(component)

        } else {
            // 组件加载失败
            console.debug('组件!加载失败')
        }
    }
}
