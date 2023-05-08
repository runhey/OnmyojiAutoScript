import QtQuick
import QtQuick.Layouts
import QtQuick.Controls
import FluentUI

Menu {

    default property alias content: container.data
    property bool enableAnimation: true
    id: popup
    width: 140
    height: container.height
    modal:true
    dim:false
    enter: Transition {
        reversible: true
        NumberAnimation {
            property: "opacity"
            from:0
            to:1
            duration: enableAnimation ? 83 : 0
        }
    }

    exit:Transition {
        NumberAnimation {
            property: "opacity"
            from:1
            to:0
            duration: enableAnimation ? 83 : 0
        }
    }

    background:Item{
        FluShadow{
            radius: 5
        }
    }
    contentItem: Item {
        clip: true
        Rectangle{
            anchors.fill: parent
            color:FluTheme.dark ? Qt.rgba(45/255,45/255,45/255,1) : Qt.rgba(249/255,249/255,249/255,1)
            border.color: FluTheme.dark ? Window.active ? Qt.rgba(55/255,55/255,55/255,1):Qt.rgba(45/255,45/255,45/255,1) : Qt.rgba(226/255,229/255,234/255,1)
            border.width: 1
            radius: 5
        }
        Column{
            id:container
            spacing: 5
            topPadding: 5
            bottomPadding: 5
            width: popup.width
            function closePopup(){
                popup.close()
            }
        }
    }

    function getContainerHeight(){
        return container.height
    }

}
