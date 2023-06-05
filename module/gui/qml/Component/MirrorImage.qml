import QtQuick 2.0
import QtQuick.Controls
import QtQuick.Dialogs
import FluentUI
import Oas
import "../Global"

Item {
    id: imageItem
    implicitWidth: 1280
    implicitHeight: 720 + 50

    property alias imageWidth: paintImage.width
    property alias imageHeight: paintImage.height

    property alias roiRed_x: roi_Red.x
    property alias roiRed_y: roi_Red.y
    property alias roiRed_width: roi_Red.width
    property alias roiRed_height: roi_Red.height
    property alias roiGreen_x: roi_Green.x
    property alias roiGreen_y: roi_Green.y
    property alias roiGreen_width: roi_Green.width
    property alias roiGreen_height: roi_Green.height

    signal roi_red_changed(string roi)
    signal roi_green_changed(string roi)

    onRoiRed_xChanged: {
//        roi_red_changed( '${roiRed_x},${roiRed_y},${roiRed_width},${roiRed_height}' )
        roi_red_changed( roiRed_x + "," +  roiRed_y + "," + roiRed_width + "," + roiRed_height)
    }
    onRoiRed_yChanged: {
        roi_red_changed( roiRed_x + "," +  roiRed_y + "," + roiRed_width + "," + roiRed_height)
    }
    onRoiRed_widthChanged: {
        roi_red_changed( roiRed_x + "," +  roiRed_y + "," + roiRed_width + "," + roiRed_height)
    }
    onRoiRed_heightChanged: {
        roi_red_changed( roiRed_x + "," +  roiRed_y + "," + roiRed_width + "," + roiRed_height)
    }


    onRoiGreen_xChanged: {
        roi_green_changed( roiGreen_x + "," +  roiGreen_y + "," + roiGreen_width + "," + roiGreen_height )
    }
    onRoiGreen_yChanged: {
        roi_green_changed( roiGreen_x + "," +  roiGreen_y + "," + roiGreen_width + "," + roiGreen_height )
    }
    onRoiGreen_widthChanged: {
        roi_green_changed( roiGreen_x + "," +  roiGreen_y + "," + roiGreen_width + "," + roiGreen_height )
    }
    onRoiGreen_heightChanged: {
        roi_green_changed( roiGreen_x + "," +  roiGreen_y + "," + roiGreen_width + "," + roiGreen_height )
    }

    enum RoiMode {
        None,
        Same,
        Include
    }
    property int roi_mode: MirrorImage.RoiMode.None

    Item{

    anchors{
        left: parent.left
        top: parent.top
        topMargin: 45
    }
    width: imageWidth
    height: imageHeight

    PaintImage{
        id: paintImage
        width: 1280
        height: 720
        Timer{
            id: timerImage
            repeat: true
            running: if(imageSoucre.currentText === "Device Image"){return true}
                     else{ return false}
            interval: 1000

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
    }


    Rectangle{
        id: roi_Green // 默认第二个是 back
        width: 100
        height: 100
        color: "transparent"
        border.width: 3
        border.color: "green"
        ResizableRectangle{
            resizeTarget: roi_Green//设置调整目标ID
        }
    }

    Rectangle{
        id: roi_Red // 默认第一个是红色的front
        width: 100
        height: 100
        color: "transparent"
        border.width: 1
        border.color: "red"

        ResizableRectangle{
            resizeTarget: roi_Red//设置调整目标ID
        }
        onXChanged: {
            if(roi_mode ===  MirrorImage.RoiMode.Include){
                if(roi_Red.x < roi_Green.x || roi_Red.x+roi_Red.width > roi_Green.x+roi_Green.width){
                    roi_Red.x = roi_Green.x + roi_Green.width/2 - roi_Red.width/2

                }
            }
            else if(roi_mode ===  MirrorImage.RoiMode.Same){
                roi_Green.x = roi_Red.x
            }
        }
        onYChanged: {
            if(roi_mode ===  MirrorImage.RoiMode.Include){
                if(roi_Red.y < roi_Green.y || roi_Red.y+roi_Red.height > roi_Green.y+roi_Green.height){
                    roi_Red.y = roi_Green.y + roi_Green.height/2 - roi_Red.height/2

                }
            }
            else if(roi_mode ===  MirrorImage.RoiMode.Same){
                roi_Green.y = roi_Red.y
            }
        }
        onWidthChanged: {
            if(roi_mode ===  MirrorImage.RoiMode.Include){
                if(roi_Red.width > roi_Green.width){
                    roi_Red.width = roi_Green.width - 5
                }
            }
            else if(roi_mode ===  MirrorImage.RoiMode.Same){
                roi_Green.width = roi_Red.width
            }
        }
        onHeightChanged: {
            if(roi_mode ===  MirrorImage.RoiMode.Include){
                if(roi_Red.height > roi_Green.height){
                    roi_Red.height = roi_Green.height - 5
                }
            }
            else if(roi_mode ===  MirrorImage.RoiMode.Same){
                roi_Green.height = roi_Red.height
            }
        }
    }
    }





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
                model: ["None", "Same Size", "Include", ]

                function setMode(){
                    if(currentText === "None"){
                        imageItem.roi_mode = MirrorImage.RoiMode.None
                    }
                    else if(currentText === "Same Size"){
                        imageItem.roi_mode = MirrorImage.RoiMode.Same
                    }
                    else{
                        imageItem.roi_mode = MirrorImage.RoiMode.Include
                    }
                }

                function updateRoi(){
                    if(roi_mode ===  MirrorImage.RoiMode.Include){
                        roi_Red.x = roi_Green.x + 5
                        roi_Red.y = roi_Green.y + 5
                        roi_Red.width = roi_Green.width - 5
                        roi_Red.height = roi_Green.height - 5

                    }
                    else if(roi_mode ===  MirrorImage.RoiMode.Same){
                        roi_Red.x = roi_Green.x
                        roi_Red.y = roi_Green.y
                        roi_Red.width = roi_Green.width
                        roi_Red.height = roi_Green.height
                    }
                }

                onActivated: {
                    setMode()
                    updateRoi()
                }
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
        // 帮助
        Item{
            width: imageExpander.width
            height: 50
            FluText{
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: "python+qml 就别想着高帧率了，而且是以截图方式而不是视频流"
            }
        }

        }
    }

    function save_target_image(roi, file){
        paintImage.save_target_image(roi, file)
    }
}
