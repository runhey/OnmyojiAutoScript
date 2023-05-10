import QtQuick
import QtQuick.Controls
import FluentUI

FluTextBox{

    property var items:[]
    property string emptyText: "没有找到结果"
    property int autoSuggestBoxReplacement: FluentIcons.Search
    signal itemClicked(var data)
    signal handleClicked

    id:control
    width: 300

    Component.onCompleted: {
        loadData()
    }

    QtObject{
        id:d
        property bool flagVisible: true
    }

    Popup{
        id:control_popup
        y:control.height
        focus: false
        enter: Transition {
            NumberAnimation {
                property: "y"
                from:0
                to:control_popup.y
                duration: 150
            }
            NumberAnimation {
                property: "opacity"
                from:0
                to:1
                duration: 150
            }
        }
        onVisibleChanged: {
            if(visible){
                list_view.currentIndex = -1
            }
        }
        background: Rectangle{
            width: control.width
            radius: 4
            FluShadow{
                radius: 4
            }
            color: FluTheme.dark ? Qt.rgba(51/255,48/255,48/255,1) : Qt.rgba(248/255,250/255,253/255,1)
            height: 38*Math.min(Math.max(list_view.count,1),8)
            ListView{
                id:list_view
                anchors.fill: parent
                clip: true
                currentIndex: -1
                ScrollBar.vertical: FluScrollBar {}
                header: Item{
                    width: control.width
                    height: visible ? 38 : 0
                    visible: list_view.count === 0
                    FluText{
                        text:emptyText
                        anchors{
                            verticalCenter: parent.verticalCenter
                            left: parent.left
                            leftMargin: 10
                        }
                    }
                }
                delegate:Control{
                    width: control.width
                    padding:10
                    background: Rectangle{
                        color:  {
                            if(list_view.currentIndex === index){
                                return FluTheme.dark ? Qt.rgba(63/255,60/255,61/255,1) : Qt.rgba(237/255,237/255,242/255,1)
                            }
                            if(hovered){
                                return FluTheme.dark ? Qt.rgba(63/255,60/255,61/255,1) : Qt.rgba(237/255,237/255,242/255,1)
                            }
                            return FluTheme.dark ? Qt.rgba(51/255,48/255,48/255,1) : Qt.rgba(0,0,0,0)
                        }
                        MouseArea{
                            id:mouse_area
                            anchors.fill: parent
                            Connections{
                                target: control
                                function onHandleClicked(){
                                    if((list_view.currentIndex === index)){
                                        handleClick(modelData)
                                    }
                                }
                            }
                            onClicked: handleClick(modelData)
                        }
                        Rectangle{
                            width: 3
                            color:FluTheme.primaryColor.dark
                            visible: list_view.currentIndex === index
                            radius: 3
                            height: 20
                            anchors{
                                left: parent.left
                                verticalCenter: parent.verticalCenter
                            }
                        }
                    }
                    contentItem: FluText{
                        text:modelData.title
                        anchors{
                            verticalCenter: parent.verticalCenter
                        }
                    }
                }
            }
        }
    }
    onTextChanged: {
        loadData()
        if(d.flagVisible){
            control_popup.visible = true
        }
    }

    function handleClick(modelData){
        control_popup.visible = false
        control.itemClicked(modelData)
        updateText(modelData.title)
    }

    function updateText(text){
        d.flagVisible = false
        control.text = text
        d.flagVisible = true
    }

    function loadData(){
        var result = []
        if(items==null){
            list_view.model = result
            return
        }
        items.map(function(item){
            if(item.title.indexOf(control.text)!==-1){
                result.push(item)
            }
        })
        list_view.model = result
    }

}
