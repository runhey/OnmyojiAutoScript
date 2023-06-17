import QtQuick
import QtQuick.Controls
import FluentUI
import "../Component"

Item {

    MirrorImage{
        id: mirrorImage
        anchors{
            left: parent.left
            top: parent.top
        }
        width: 1280
        height: 720 + 50
        imageWidth: 1280
        imageHeight: 720

        onRoi_red_changed: function(roi){
            if(typeof ruleFile.currentItem === "undefined"){
                return
            }
            ruleFile.currentItem.roiFront = roi
        }

        onRoi_green_changed: function(roi){
            if(typeof ruleFile.currentItem === "undefined"){
                return
            }
            ruleFile.currentItem.roiBack = roi
        }
    }
    RuleFile{
        id: ruleFile
        anchors{
            left: mirrorImage.right
            leftMargin: 10
            right: parent.right
            top: parent.top
        }
        height: 600
        addFunc: add
        editFunc: edit
        saveFunc: save

        onCurrentItemChanged: {
            if(currentItem === "" || typeof currentItem === "undefined"){
                return
            }
            var [x, y, width, height] = currentItem.roiFront.split(',')
            mirrorImage.roiRed_x = parseInt(x)
            mirrorImage.roiRed_y = parseInt(y)
            mirrorImage.roiRed_width = parseInt(width)
            mirrorImage.roiRed_height = parseInt(height)
            var [x, y, width, height] = currentItem.roiBack.split(',')
            mirrorImage.roiGreen_x = parseInt(x)
            mirrorImage.roiGreen_y = parseInt(y)
            mirrorImage.roiGreen_width = parseInt(width)
            mirrorImage.roiGreen_height = parseInt(height)

        }
    }

    FluArea {
        id: ruleArea
        anchors{
            left: mirrorImage.right
            leftMargin: 10
            right: parent.right
            top: ruleFile.bottom
            topMargin: 12
            bottom: parent.bottom
        }
        Column{
            id: coi
            anchors{
                top: parent.top
                bottom: parent.bottom
                left: parent.left
                leftMargin: 20
                right: parent.right
                rightMargin: 20
            }
            spacing: 5
            //头
            Item{
                width: coi.width
                height: 40
                FluText{
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Editing rule"
                    font: FluTextStyle.Subtitle
                }
            }
            //item name 这个参数项的名称
            Item{
                width: coi.width
                height: 40
                FluText{
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Item name"
                    font: FluTextStyle.BodyStrong
                }
                FluTextBox{
                    id: itemName
                    anchors{
                        right: parent.right
                        verticalCenter: parent.verticalCenter
                    }
                    placeholderText:"单行输入框"
                    disabled: true
                    text: (typeof ruleFile.currentItem === "undefined")? "" : ruleFile.currentItem.itemName
                    width: 200
                }
            }
            // 文件名
//            Item{
//                width: coi.width
//                height: 40
//                FluText{
//                    anchors.left: parent.left
//                    anchors.verticalCenter: parent.verticalCenter
//                    text: "Image name"
//                    font: FluTextStyle.BodyStrong
//                }
//                FluTextBox{
//                    id: imageName
//                    anchors{
//                        right: parent.right
//                        verticalCenter: parent.verticalCenter
//                    }
//                    disabled: true
//                    text:(typeof ruleFile.currentItem === "undefined")? "" : ruleFile.currentItem.imageName
//                    placeholderText:"Save image name"
//                    width: 200
//                }
//            }
            // roi front
            Item{
                width: coi.width
                height: 40
                FluText{
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Roi front"
                    font: FluTextStyle.BodyStrong
                }
                FluTextBox{
                    id: roiFront
                    anchors{
                        right: parent.right
                        verticalCenter: parent.verticalCenter
                    }
                    disabled: true
                    text:(typeof ruleFile.currentItem === "undefined")? "" : ruleFile.currentItem.roiFront
                    placeholderText:"0,0,100,100"
                    width: 200
                }
            }
            //roi back
            Item{
                width: coi.width
                height: 40
                FluText{
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Roi Back"
                    font: FluTextStyle.BodyStrong
                }
                FluTextBox{
                    id: roiBack
                    anchors{
                        right: parent.right
                        verticalCenter: parent.verticalCenter
                    }
                    disabled: true
                    text:(typeof ruleFile.currentItem === "undefined")? "" : ruleFile.currentItem.roiBack
                    placeholderText:"0,0,100,100"
                    width: 200


                }
            }
            //找图的方法
//            Item{
//                width: coi.width
//                height: 40
//                FluText{
//                    anchors.left: parent.left
//                    anchors.verticalCenter: parent.verticalCenter
//                    text: "Find method"
//                    font: FluTextStyle.BodyStrong
//                }
//                FComboBox{
//                    id: method
//                    anchors{
//                        right: parent.right
//                        verticalCenter: parent.verticalCenter
//                    }
//                    width: 200
//                    currentIndex: 0
//                    model: ["Template matching"]
//                    onActivated: {

//                    }
//                }
//            }
            //阈值
//            Item{
//                width: coi.width
//                height: 40
//                FluText{
//                    anchors.left: parent.left
//                    anchors.verticalCenter: parent.verticalCenter
//                    text: "Threshod"
//                    font: FluTextStyle.BodyStrong
//                }
//                FluTextBox{
//                    id: threshold
//                    anchors{
//                        right: parent.right
//                        verticalCenter: parent.verticalCenter
//                    }
//                    width: 200
//                    text:(typeof ruleFile.currentItem === "undefined")? "" : ruleFile.currentItem.threshold
//                    placeholderText:"0.8"
//                    onEditingFinished: {
//                        if(typeof ruleFile.currentItem === "undefined"){
//                            return
//                        }
//                        ruleFile.currentItem.threshold = parseFloat(text)
//                    }
//                }
//            }
            //描述 description
            Item{
                width: coi.width
                height: 40
                FluText{
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Description"
                    font: FluTextStyle.BodyStrong
                }
                FluTextBox{
                    id: description
                    anchors{
                        right: parent.right
                        verticalCenter: parent.verticalCenter
                    }
                    width: 200
                    text:(typeof ruleFile.currentItem === "undefined")? "" : ruleFile.currentItem.description
                    placeholderText:"input your description"
                    onEditingFinished: {
                        if(typeof ruleFile.currentItem === "undefined"){
                            return
                        }
                        ruleFile.currentItem.description = text
                    }
                }
            }

        }

    }

    // 帮助
    FluArea{
        id: ruleHelp
        anchors{
            left: parent.left
            right: ruleArea.left
            rightMargin: 10
            top: mirrorImage.bottom
            topMargin: 10
            bottom: parent.bottom
        }
        FluText{
            leftPadding: 12
            topPadding: 12
            text: "红色的框(Roi front)表示这一个项点击的默认范围，绿色的框(Roi back)表示备用的范围。
在移动边框时右边的roi并不会实时显示，当切换软件的焦点时更新显示，但是具体的数值是更新的。
投屏的设置最上边点击即可"
        }

    }

    function add(){
        const item ={}
        item["itemName"] = "new"
        item["roiFront"] = "0,0,100,100"
        item["roiBack"] = "0,0,100,100"
        item["description"] = "description"
        showSuccess("Add new item")
        return item
    }

    function edit(model){

    }

    function save(){
        const data = []
        for(var i=0; i<ruleFile.list_model.count; i++){
            const item = ruleFile.list_model.get(i)
            const itemData = {}
            itemData["itemName"] = item["itemName"]
            itemData["roiFront"] = item["roiFront"]
            itemData["roiBack"] = item["roiBack"]
            itemData["description"] = item["description"]
            data.push(itemData)
        }

        ruleFile.rule_file.write_file(ruleFile.file, JSON.stringify(data, null, "  "))
        showSuccess("Save file")

    }


}
