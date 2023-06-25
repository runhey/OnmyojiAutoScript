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
//            ruleFile.currentItem.roiBack = roi
            ruleFile.roiBack = roi
        }
    }
    RuleFile2{
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
        }
        onRoiBackChanged: {
            var [x, y, width, height] = ruleFile.roiBack.split(',')
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
            // name 这个参数项的名称
            Item{
                width: coi.width
                height: 40
                FluText{
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: "List name"
                    font: FluTextStyle.BodyStrong
                }
                FluTextBox{
                    id: itemName
                    anchors{
                        right: parent.right
                        verticalCenter: parent.verticalCenter
                    }
                    placeholderText:"itemName"
                    disabled: false
                    text: ruleFile.name
                    width: 200
                    onEditingFinished: {
                        ruleFile.name = text
                    }
                }
            }
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
                    text: ruleFile.roiBack
                    placeholderText:"0,0,100,100"
                    width: 200


                }
            }
            //水平还是竖直方向
            Item{
                width: coi.width
                height: 40
                FluText{
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Direction"
                    font: FluTextStyle.BodyStrong
                }
                FComboBox{
                    id: direction
                    anchors{
                        right: parent.right
                        verticalCenter: parent.verticalCenter
                    }
                    width: 200
                    currentIndex: if(ruleFile.direction === "vertical"){
                                      return 0
                                  }else{
                                      return 1
                                  }
                    model: ["vertical", "horizontal"]

                    onActivated: {
                        if(currentIndex === 0){
                            ruleFile.direction = "vertical"
                        }
                        else{
                            ruleFile.direction = "horizontal"
                        }
                    }
                }
            }
            // 类型 图片还是ocr
            Item{
                width: coi.width
                height: 40
                FluText{
                    anchors.left: parent.left
                    anchors.verticalCenter: parent.verticalCenter
                    text: "Type"
                    font: FluTextStyle.BodyStrong
                }
                FComboBox{
                    id: type
                    anchors{
                        right: parent.right
                        verticalCenter: parent.verticalCenter
                    }
                    width: 200
                    model: ["image", "ocr"]
                    currentIndex: {if(ruleFile.type === "image"){
                                      return 0
                                  }else{
                                      return 1
                                  }}

                    onActivated: {
                        if(currentIndex === 0){
                            ruleFile.type = "image"
                        }
                        else{
                            ruleFile.type = "ocr"
                        }
                    }
                }
            }
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
                    text:ruleFile.description
                    placeholderText:"input your description"
                    onEditingFinished: {
                        ruleFile.description = text
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
            text: "红色的框(Roi front)表示这一个项要匹配的图片，绿色的框(Roi back)表示匹配的范围。
在移动边框时右边的roi并不会实时显示，当切换软件的焦点时更新显示。但是具体的数值是更新的，可以放心的保存截图"
        }
        FluFilledButton{
            anchors{
                right: parent.right
                rightMargin: 10
                top: parent.top
                topMargin: 10
            }

            text:"Save image"
            onClicked: {
                const i = ruleFile.file.lastIndexOf("/")
                const imagepath = ruleFile.file.substring(0, i)
                mirrorImage.save_target_image(ruleFile.currentItem.roiFront, imagepath +"/"+ruleFile.currentItem.itemName+'.png')
                showSuccess("Save target image")
            }
        }
    }

    function add(){
        const item ={}
        item["itemName"] = "new"
        item["roiFront"] = "0,0,100,100"
        showSuccess("Add new item")
        return item
    }

    function edit(model){

    }

    function save(){
        const data = {}
        const list = []
        for(var i=0; i<ruleFile.list_model.count; i++){
            const item = ruleFile.list_model.get(i)
            const itemData = {}
            itemData["itemName"] = item["itemName"]
            itemData["roiFront"] = item["roiFront"]
            list.push(itemData)
        }
        data["name"] = ruleFile.name
        data["direction"] = ruleFile.direction
        data["type"] = ruleFile.type
        data["roiBack"] = ruleFile.roiBack
        data["description"] = ruleFile.description
        data["list"] = list

        ruleFile.rule_file.write_file(ruleFile.file, JSON.stringify(data, null, "  "))
        showSuccess("Save file")

    }


}
