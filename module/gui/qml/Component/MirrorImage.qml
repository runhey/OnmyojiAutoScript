import QtQuick 2.0
import QtQuick.Controls
import QtQuick.Dialogs
import FluentUI
import Oas
import "../Global"

Item {
    implicitWidth: 1280
    implicitHeight: 720 + 50
    property alias imageWidth: paintImage.width
    property alias imageHeight: paintImage.height


    Item{
        anchors{
            left: parent.left
            top: parent.top
            topMargin: 45
        }
    PaintImage{
        id: paintImage
        width: 1280
        height: 720
        Timer{
            id: timerImage
            repeat: true
            running: if(imageSoucre.currentText === "Device Image"){return true}
                     else{ return false}
            interval: 500

            onTriggered: {
                paintImage.update_image()
            }
        }

        function update_image(){
            if(imageSoucre.currentText === "Local Image"){
                const imagePath = localImageName.text
                if(!imagePath.startsWith("file:///")){
                    return
                }
                paintImage.set_local(imagePath)
            }
            else{
                const i = process_manager.gui_mirror_image(MainEvent.scriptName)
                paintImage.image = i
            }
        }
        Component.onCompleted:{
            timerImage.start()
        }
    }}

    FluExpander{
        id: imageExpander
        headerText: qsTr("Screen Settings")
        width: parent.width
        anchors.left: parent.left
        anchors.top: parent.top
        contentHeight: paintImage.height

        Column{
            anchors.fill: parent
            anchors.leftMargin: 20

        // 设置你的图片源
        Item{
            width: imageExpander.width
            height: 50
            FluText{
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: "Image Source"
            }
            FComboBox{
                id: imageSoucre
                anchors{
                    left: parent.left
                    leftMargin: 150
                    verticalCenter: parent.verticalCenter
                }
                width: 200
                model: ["Device Image", "Local Image"]
                Component.onCompleted:{
                    currentIndex = 0
                }
            }
        }
        // 设置你的本地的图片地址
        Item{
            width: imageExpander.width
            height: 50
            FluText{
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: "Local Image Name"
            }

            FluFilledButton{
                id: localImageName
                anchors{
                    left: parent.left
                    leftMargin: 150
                    verticalCenter: parent.verticalCenter
                }
                width: 200
                text:"select your image"
                clip: true
//                horizontalAlignment: Text.AlignRight
//                elide: Text.ElideRight
                onClicked: {
                    imageFileDialog.open()
                }
            }

            FileDialog{
                   id: imageFileDialog
                   title: "select your image"
                   nameFilters: ["Image Files (*.png *.jpg)"]
                   onAccepted: {
                       const selectedUrl = imageFileDialog.selectedFile.toString()
                       localImageName.text = selectedUrl
                       paintImage.update_image()
                   }
               }
        }
        // 设置两个框的交互模式
        Item{
            width: imageExpander.width
            height: 50
            FluText{
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: "ROI Model"
            }
            FComboBox{
                id: roiModel
                anchors{
                    left: parent.left
                    verticalCenter: parent.verticalCenter
                    leftMargin: 150
                }
                width: 200
                model: ["Same Size", "Include", "None"]
            }
        }
        // 设置显示的帧率
        Item{
            width: imageExpander.width
            height: 50
            FluText{
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: "Frame Rate"
            }
            FluSlider{
                id: frameRate
                anchors{
                    left: parent.left
                    verticalCenter: parent.verticalCenter
                    leftMargin: 150
                }
                size: 200
                value: 2
                maxValue: 10
                onReleased: {
                    if(value > 0){
                        timerImage.interval = 1000 / value
                    }
                }
            }
        }

        }
    }
}
