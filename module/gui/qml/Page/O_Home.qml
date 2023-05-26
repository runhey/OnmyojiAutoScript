import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import FluentUI

import "../Component"


SplitPanel{

    onTitleChanged: {
        if(title === "Home"){
            var comp = Qt.createComponent("../../qml/Page/Home.qml")
            if (comp.status === Component.Ready) {
                setLoader(comp)
            }
        }else if(title === "Update"){
            var updater = Qt.createComponent("../../qml/Page/Update.qml")
            if (updater.status === Component.Ready) {
                setLoader(updater)
            }
        }
    }
    Component.onCompleted:{
        var comp = Qt.createComponent("../../qml/Page/Home.qml")
        if (comp.status === Component.Ready) {
            setDefalut(comp)
        }
    }
}

