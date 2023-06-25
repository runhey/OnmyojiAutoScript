import QtQuick
import QtQuick.Controls
import FluentUI
import QtQuick.Dialogs
import Oas

FluArea {
    id: root
    property string file: ""  //完整的文件路径带后缀
    property alias folder: folderButton.text
    property alias list_model: listModel
    property alias rule_file: ruleFile

    property var currentItem: listModel.get(0)
    property var addFunc: function(){}
    property var editFunc: function(){}
    property var saveFunc: function(){}
    ListModel{
        id: listModel
    }

    RuleFile{
        id: ruleFile
    }

    Column{
        id: coi
        anchors{
            top: parent.top
//            topMargin: 10
            bottom: parent.bottom
            left: parent.left
            leftMargin: 20
            right: parent.right
            rightMargin: 20
        }

        spacing: 5
        // 头
        Item{
            width: coi.width
            height: 40
            FluText{
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: "Select rule"
                font: FluTextStyle.BodyStrong
            }
        }
        //路径
        Item{
            width: coi.width
            height: 40
            FluText{
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: "Folder"
                font: FluTextStyle.BodyStrong
            }
            FluButton{
                id: folderButton
                anchors{
                    right: parent.right
                    verticalCenter: parent.verticalCenter
                }
                disabled: true
                text:"Select folder"
                width: 200
                onClicked: {

                }
            }
        }
        // 文件名
        Item{
            width: coi.width
            height: 40
            FluText{
                anchors.left: parent.left
                anchors.verticalCenter: parent.verticalCenter
                text: "File"
                font: FluTextStyle.BodyStrong
            }
            FluButton{
                id: fileButton
                anchors{
                    right: parent.right
                    verticalCenter: parent.verticalCenter
                }
                text:"Select file"
                width: 200
                onClicked: {
                    jsonFileDialog.open()
                }
            }
            FileDialog{
                   id: jsonFileDialog
                   title: "select your json file"
                   nameFilters: ["(*.json)"]
                   onAccepted: {
                       const selectedUrl = jsonFileDialog.selectedFile.toString()
                       if(!selectedUrl.startsWith("file:///")){
                           console.error("请你选择正确的文件路径")
                           return
                       }
                       const filePath = selectedUrl.substring("file:///".length)
                       const lastSlashIndex = filePath.lastIndexOf("/"); // 获取最后一个斜杠的索引
                       const secondLastSlashIndex = filePath.lastIndexOf("/", lastSlashIndex - 1); // 获取倒数第二个斜杠的索引

                       const filename = filePath.substring(lastSlashIndex + 1); // 获取文件名（带后缀）
                       const directory = filePath.substring(secondLastSlashIndex+1, lastSlashIndex); // 获取文件所在的目录

                       root.file = filePath
                       folderButton.text = directory
                       fileButton.text = filename
                       listModel.clear()
                       loadFile()
                   }
               }
        }
        // new
        Item{
            width: coi.width
            height: 40
            FluFilledButton{
                id: saveItemButton
                anchors{
                    right: parent.right
                    verticalCenter: parent.verticalCenter
                }
                text:"New"
                disabled: root.file === ""? true : false
                width: parent.width
                onClicked: {
                    listModel.append(addFunc())
                }
            }
        }
        // 保存 文件
        Item{
            width: coi.width
            height: 40
            FluFilledButton{
                id: saveFileButton
                anchors{
                    right: parent.right
                    verticalCenter: parent.verticalCenter
                }
                text:"Save file"
                width: parent.width
                disabled: root.file === ""? true : false
                onClicked: {
                    root.saveFunc()
                }
            }
        }
        //表格视图
        Item{
            width: coi.width
            height: 370
            ListView{
                id: listView
                width: 200
                height: parent.height
                anchors{
                    right: parent.right
                }
                model: listModel
                delegate: listDelegate
            }
            Component{
                id: listDelegate
                Item{
                    width: 200
                    height: 40
                FluTextBox{
                    id: itemName
                    width: parent.width
                    anchors{
                        verticalCenter: parent.verticalCenter
                    }
                    placeholderText:"item name"
                    text: model.itemName
                    validator: RegularExpressionValidator { regularExpression: /^[a-z0-9_]*$/ }
                    onActiveFocusChanged: {
                        if(activeFocus){
                            currentItem = listModel.get(index)
                        }
                    }
                    onEditingFinished: {
                        model.itemName = text
                        root.editFunc(model)
                    }
                    onAccepted: {

                    }
                }
                }
            }
        }
    }

    // 加载文件，前提是文件的路径是加载好的
    function loadFile(){
        const getData = ruleFile.read_file(file)
        var data = []
        if (getData === "" || typeof getData === "undefined") {
            console.log("String is empty or undefined.")
            // 如果是空的表示这个是一个刚刚建立的rule文件
            return
        }
        data = JSON.parse(getData)
        for(let item of data){
            listModel.append(item)
        }
    }

}
