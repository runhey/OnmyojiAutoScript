import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import FluentUI

Item {

    property int textSize: 15
    property string separator: "/"
    property var items: []
    property int spacing: 5
    signal clickItem(var model)

    id:control
    implicitWidth: 300
    height: 30

    onItemsChanged: {
        list_model.clear()
        list_model.append(items)
    }

    ListModel{
        id:list_model
    }

    ListView{
        id:list_view
        width: parent.width
        height: 30
        orientation: ListView.Horizontal
        model: list_model
        clip: true
        spacing : control.spacing
        boundsBehavior: ListView.StopAtBounds
        remove: Transition {
            NumberAnimation {
                properties: "opacity"
                from: 1
                to: 0
                duration: 83
            }
        }
        add: Transition {
            NumberAnimation {
                properties: "opacity"
                from: 0
                to: 1
                duration: 83
            }
        }
        delegate: Item{
            height: item_layout.height
            width: item_layout.width
            RowLayout{
                id:item_layout
                spacing: list_view.spacing
                height: list_view.height

                FluText{
                    text:model.title
                    Layout.alignment: Qt.AlignVCenter
                    color: {
                        if(item_mouse.pressed){
                            return FluTheme.dark ? Qt.rgba(150/255,150/255,150/235,1) : Qt.rgba(134/255,134/255,134/235,1)
                        }
                        if(item_mouse.containsMouse){
                            return FluTheme.dark ? Qt.rgba(204/255,204/255,204/235,1) : Qt.rgba(92/255,92/255,92/235,1)
                        }
                        return FluTheme.dark ? Qt.rgba(255/255,255/255,255/235,1) :  Qt.rgba(26/255,26/255,26/235,1)
                    }
                    MouseArea{
                        id:item_mouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            control.clickItem(model)
                        }
                    }
                }

                FluText{
                    text:control.separator
                    font.pixelSize:  control.textSize
                    visible: list_view.count-1 !== index
                    Layout.alignment: Qt.AlignVCenter
                }
            }
        }
    }

    function remove(index,count){
        list_model.remove(index,count)
    }

    function count(){
        return list_model.count
    }

}
