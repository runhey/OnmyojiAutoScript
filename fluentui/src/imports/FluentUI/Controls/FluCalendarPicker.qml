import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import FluentUI

Rectangle {

    property color dividerColor: FluTheme.dark ? Qt.rgba(77/255,77/255,77/255,1) : Qt.rgba(239/255,239/255,239/255,1)
    property color hoverColor: FluTheme.dark ? Qt.rgba(68/255,68/255,68/255,1) : Qt.rgba(251/255,251/255,251/255,1)
    property color normalColor: FluTheme.dark ? Qt.rgba(61/255,61/255,61/255,1) : Qt.rgba(254/255,254/255,254/255,1)
    property string text: "请选择日期"
    property var window : Window.window

    id:control
    color: {
        if(mouse_area.containsMouse){
            return hoverColor
        }
        return normalColor
    }
    height: 30
    width: 120
    radius: 4
    border.width: 1
    border.color: dividerColor

    MouseArea{
        id:mouse_area
        hoverEnabled: true
        anchors.fill: parent
        onClicked: {
            popup.showPopup()
        }
    }

    FluText{
        id:text_date
        anchors{
            left: parent.left
            right: parent.right
            rightMargin: 30
            top: parent.top
            bottom: parent.bottom
        }
        verticalAlignment: Text.AlignVCenter
        horizontalAlignment: Text.AlignHCenter
        text:control.text
    }

    FluIcon{
        iconSource: FluentIcons.Calendar
        iconSize: 14
        iconColor: text_date.color
        anchors{
            verticalCenter: parent.verticalCenter
            right: parent.right
            rightMargin: 12
        }
    }


    Menu{
        id:popup
        height: container.height
        width: container.width
        modal: true
        dim:false
        enter: Transition {
            reversible: true
            NumberAnimation {
                property: "opacity"
                from:0
                to:1
                duration: 83
            }
        }

        exit:Transition {
            NumberAnimation {
                property: "opacity"
                from:1
                to:0
                duration: 83
            }
        }

        contentItem: Item{
            clip: true
            FluCalendarView{
                id:container
                onDateClicked:
                    (date)=>{
                        popup.close()
                        var year = date.getFullYear()
                        var month = date.getMonth()
                        var day =  date.getDate()
                        text_date.text = year+"-"+(month+1)+"-"+day
                    }
            }
        }
        background: Item{
            FluShadow{
                radius: 5
            }
        }
        function showPopup() {
            var pos = control.mapToItem(null, 0, 0)
            if(window.height>pos.y+control.height+container.height){
                popup.y = control.height
            } else if(pos.y>container.height){
                popup.y = -container.height
            } else {
                popup.y = window.height-(pos.y+container.height)
            }
            popup.x = -(popup.width-control.width)/2
            popup.open()
        }
    }
}
