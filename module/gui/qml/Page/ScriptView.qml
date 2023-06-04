import QtQuick
import QtQuick.Controls
import FluentUI
import "../Component"
import "../Global"

SplitPanel{

    property string configName: ""

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
        console.debug(process_manager.gui_menu)
        const data = JSON.parse(process_manager.gui_menu())
        create(data)
    }


    Component.onCompleted:{


//        var data = {'Overview':[], 'Script': ['Script', 'General', 'Restart']}


        const component = Qt.createComponent("../../qml/Component/Overview.qml")
        if (component.status === Component.Ready) {
            setDefalut(component)
        } else {
            // 组件加载失败
            console.debug('组件!加载失败')
        }
    }
}
