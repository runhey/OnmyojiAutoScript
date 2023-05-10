import QtQuick
import QtQuick.Controls
import FluentUI

Item {

    property bool flagXChanged: true
    property int radius : 5
    property int loopTime: 2000
    property bool showIndicator: true

    id:control
    width: 400
    height: 300

    ListModel{
        id:content_model
    }

    FluRectangle{
        anchors.fill: parent
        radius: [control.radius,control.radius,control.radius,control.radius]
        FluShadow{
            radius:control.radius
        }
        ListView{
            id:list_view
            anchors.fill: parent
            snapMode: ListView.SnapOneItem
            clip: true
            boundsBehavior: ListView.StopAtBounds
            model:content_model
            maximumFlickVelocity: 4 * (list_view.orientation === Qt.Horizontal ? width : height)
            preferredHighlightBegin: 0
            preferredHighlightEnd: 0
            highlightMoveDuration: 0
            orientation : ListView.Horizontal
            delegate: Item{
                width: ListView.view.width
                height: ListView.view.height
                property int displayIndex: {
                    if(index === 0)
                        return content_model.count-3
                    if(index === content_model.count-1)
                        return 0
                    return index-1
                }
                Image {
                    anchors.fill: parent
                    source: model.url
                    asynchronous: true
                    fillMode:Image.PreserveAspectCrop
                }
            }
            onMovementEnded:{
                currentIndex = list_view.contentX/list_view.width
                if(currentIndex === 0){
                    currentIndex = list_view.count-2
                }else if(currentIndex === list_view.count-1){
                    currentIndex = 1
                }
                flagXChanged = false
                timer_run.start()
            }
            onMovementStarted: {
                flagXChanged = true
                timer_run.stop()
            }
            onContentXChanged: {
                if(flagXChanged){
                    var maxX = Math.min(list_view.width*(currentIndex+1),list_view.count*list_view.width)
                    var minY = Math.max(0,(list_view.width*(currentIndex-1)))
                    if(contentX>=maxX){
                        contentX = maxX
                    }
                    if(contentX<=minY){
                        contentX = minY
                    }
                }
            }
        }
    }
    function setData(data){
        content_model.clear()
        content_model.append(data[data.length-1])
        content_model.append(data)
        content_model.append(data[0])
        list_view.currentIndex = 1
        timer_run.restart()
    }
    Row{
        spacing: 10
        anchors{
            horizontalCenter: parent.horizontalCenter
            bottom: parent.bottom
            bottomMargin: 20
        }
        visible: showIndicator
        Repeater{
            model: list_view.count
            Rectangle{
                width: 8
                height: 8
                radius: 4
                visible: {
                    if(index===0 || index===list_view.count-1)
                        return false
                    return true
                }
                border.width: 1
                border.color: FluColors.Grey100
                color:   list_view.currentIndex === index ?  FluTheme.primaryColor.dark : Qt.rgba(1,1,1,0.5)
            }
        }
    }
    Timer{
        id:timer_anim
        interval: 250
        onTriggered: {
            list_view.highlightMoveDuration = 0
            if(list_view.currentIndex === list_view.count-1){
                list_view.currentIndex = 1
            }
        }
    }
    Timer{
        id:timer_run
        interval: control.loopTime
        repeat: true
        onTriggered: {
            list_view.highlightMoveDuration = 250
            list_view.currentIndex = list_view.currentIndex+1
            timer_anim.start()
        }
    }
}
