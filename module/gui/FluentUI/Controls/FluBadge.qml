import QtQuick
import QtQuick.Controls
import FluentUI

Rectangle{

    property bool isDot: false
    property bool showZero: true
    property int count: 0

    id:control
    color:Qt.rgba(255/255,77/255,79/255,1)
    width: {
        if(isDot)
            return 10
        if(count<10){
            return 20
        }else if(count<100){
           return 30
        }
        return 40
    }
    height: {
        if(isDot)
            return 10
        return 20
    }
    radius: {
        if(isDot)
            return 5
        return 10
    }
    border.width: 1
    border.color: Qt.rgba(1,1,1,1)
    visible: {
        if(showZero)
            return true
        return count!==0
    }
    anchors{
        right: {
            if(parent)
                return parent.right
            return undefined
        }
        top: {
            if(parent)
                return parent.top
            return undefined
        }
        rightMargin: {
            if(isDot){
                return -2.5
            }
            return -(control.width/2)
        }
        topMargin: {
            if(isDot){
                return -2.5
            }
            return  -10
        }
    }

    Text{
        anchors.centerIn: parent
        color: Qt.rgba(1,1,1,1)
        visible: !isDot
        text:{
            if(count<100)
                return count
            return count+"+"
        }
    }



}
