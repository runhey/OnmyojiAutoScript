import QtQuick
import FluentUI
import "../Global/"

FluPaneItem{
    title: "home"
    icon:FluentIcons.Play36
    onTap:{
        navigationView.push(Qt.resolvedUrl("../../qml/Page/ScriptView.qml"))
    }
}
