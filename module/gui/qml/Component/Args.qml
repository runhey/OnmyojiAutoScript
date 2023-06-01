import QtQuick
import QtQuick.Controls
import FluentUI
import QtQuick.Layouts
import "./ModelParse.js" as MP

Item {
    property string argsData: ""
    property string valueData: ""
    signal updataData
    FluScrollablePage{
        id: contentScrollable
        width: 700
        height: parent.height
        spacing: 12
        anchors.horizontalCenter: parent.horizontalCenter
    }

    Component{
        id: group_item
        FluExpander{
            id: expander
            property string groupName: ""
            property string groupTitle: ""
            property var argumentValue: {""}
            headerText: qsTr(groupTitle) +" "+ qsTr("Setting")
            width: contentScrollable.width
            contentHeight: group_column.height
            Column{
                id: group_column
                spacing: 4
                clip: true
                anchors{
                    top: parent.top
                    topMargin: 12
                    left: parent.left
                    leftMargin: 15
                    right: parent.right
                    rightMargin: 15
                    bottomMargin: 12
                }
            }
            onArgumentValueChanged: {
                for(let index in argumentValue){
                    const arg = argumentValue[index]
                    createItem(arg)
//                    expander.contentHeight = group_column.height
                }
            }
            /**
             * 创建某个具体的字段
             * @param {Object} arg 打包的变量大概长这样的：
                {
                    "name": "handle_error",
                    "title": "Handle Error",
                    "description": "none",
                    "default": false,
                    "type": "boolean",
                    "value": false
                }
             * @returns {Object}
             */
            function createItem(arg){
                if(arg === null){
                    console.error("it is emtry when create arg")
                    return
                }

                var object = null
                if(arg.type === "string"){
                    object = string_item.createObject(group_column)
                    if(object === null){
                        console.error("can not create component string_item", arg.title)
                        return
                    }
                }
                else if(arg.type === "integer"){
                    object = int_item.createObject(group_column)
                    if(object === null){
                        console.error("can not create component integer_item", arg.title)
                        return
                    }
                }
                else if(arg.type === "number"){
                    object = float_item.createObject(group_column)
                    if(object === null){
                        console.error("can not create component float_item", arg.title)
                        return
                    }
                }
                else if(arg.type === "boolean"){
                    object = bool_item.createObject(group_column)
                    if(object === null){
                        console.error("can not create component boolean_item", arg.title)
                        return
                    }
                }
                else if(arg.type === "enum"){
                    object = enum_item.createObject(group_column)
                    if(object === null){
                        console.error("can not create component enum_item", arg.title)
                        return
                    }
                }

                if(object === null){
                    console.error("can not create component ", arg.title)
                    return
                }
                object.modelData = arg
                group_column.data.push(object)
            }
        }

    }

    Component{
        id: string_item
        Item{
            id: stringItem
            property var modelData: null
            width: parent.width
            implicitHeight: string_title.implicitHeight + string_description.implicitHeight
            Layout.fillHeight: true
            FluTextBox{
                id: string_text
                anchors{
                    top: parent.top
                    topMargin: 2
                    right: parent.right
                }
                placeholderText: ""
            }

            FluText{
                id: string_title
                anchors{
                    top: parent.top
                    left: parent.left
                    right: string_text.left
                }
                text: ""
                font: FluTextStyle.BodyStrong
                wrapMode: Text.WrapAnywhere
                topPadding: 6
            }
            FluText{
                id: string_description
                anchors{
                    top: string_title.bottom
                    left: parent.left
                }
                width: string_title.width
                text: ""
                font: FluTextStyle.Caption
                wrapMode: Text.WrapAnywhere
                topPadding: 6
                rightPadding: 6
            }
            onModelDataChanged: {
                if(modelData === null){
                    console.error("string model is null")
                    return
                }
                string_text.text = modelData.value
                string_text.placeholderText = modelData["default"]
                string_title.text = modelData.title
                if( typeof modelData.description === 'undefined'){
                    return
                }
                string_description.text = modelData.description
            }
        }
    }
    Component{
        id: int_item
        Item{
            id: itemArg
            property var modelData: null
            width: parent.width
            implicitHeight: itemArg_title.implicitHeight + itemArg_description.implicitHeight
            Layout.fillHeight: true
            FluTextBox{
                id: itemArg_text
                anchors{
                    top: parent.top
                    topMargin: 2
                    right: parent.right
                }
                placeholderText: ""
            }

            FluText{
                id: itemArg_title
                anchors{
                    top: parent.top
                    left: parent.left
                    right: itemArg_text.left
                }
                text: ""
                font: FluTextStyle.BodyStrong
                wrapMode: Text.WrapAnywhere
                topPadding: 6
            }
            FluText{
                id: itemArg_description
                anchors{
                    top: itemArg_title.bottom
                    left: parent.left
                }
                width: itemArg_title.width
                text: ""
                font: FluTextStyle.Caption
                wrapMode: Text.WrapAnywhere
                topPadding: 6
                rightPadding: 6
            }
            onModelDataChanged: {
                if(modelData === null){
                    console.error("int model is null")
                    return
                }
                itemArg_text.text = modelData.value
                itemArg_text.placeholderText = modelData["default"]
                itemArg_title.text = modelData.title
                if( typeof modelData.description === 'undefined'){
                    return
                }
                itemArg_description.text = modelData.description
            }
        }
    }
    Component{
        id: float_item
        Item{
            id: itemArg
            property var modelData: null
            width: parent.width
            implicitHeight: itemArg_title.implicitHeight + itemArg_description.implicitHeight
            Layout.fillHeight: true
            FluTextBox{
                id: itemArg_text
                anchors{
                    top: parent.top
                    topMargin: 2
                    right: parent.right
                }
                placeholderText: ""
            }

            FluText{
                id: itemArg_title
                anchors{
                    top: parent.top
                    left: parent.left
                    right: itemArg_text.left
                }
                text: ""
                font: FluTextStyle.BodyStrong
                wrapMode: Text.WrapAnywhere
                topPadding: 6
            }
            FluText{
                id: itemArg_description
                anchors{
                    top: itemArg_title.bottom
                    left: parent.left
                }
                width: itemArg_title.width
                text: ""
                font: FluTextStyle.Caption
                wrapMode: Text.WrapAnywhere
                topPadding: 6
                rightPadding: 6
            }
            onModelDataChanged: {
                if(modelData === null){
                    console.error("float model is null")
                    return
                }
                itemArg_text.text = modelData.value
                itemArg_text.placeholderText = modelData["default"]
                itemArg_title.text = modelData.title
                if( typeof modelData.description === 'undefined'){
                    return
                }
                itemArg_description.text = modelData.description
            }
        }
    }
    Component{
        id: bool_item
        Item{
            id: itemArg
            property var modelData: null
            width: parent.width
            implicitHeight: itemArg_title.implicitHeight + itemArg_description.implicitHeight
            Layout.fillHeight: true
            FluCheckBox{
                id: itemArg_text
                anchors{
                    top: parent.top
                    topMargin: 2
                    right: parent.right
                    rightMargin: 300 - 24
                }
                selected: true
            }

            FluText{
                id: itemArg_title
                anchors{
                    top: parent.top
                    left: parent.left
                    right: itemArg_text.left
                }
                text: ""
                font: FluTextStyle.BodyStrong
                wrapMode: Text.WrapAnywhere
                topPadding: 6
            }
            FluText{
                id: itemArg_description
                anchors{
                    top: itemArg_title.bottom
                    left: parent.left
                }
                width: itemArg_title.width
                text: ""
                font: FluTextStyle.Caption
                wrapMode: Text.WrapAnywhere
                topPadding: 6
                rightPadding: 6
            }
            onModelDataChanged: {
                if(modelData === null){
                    console.error("bool model is null")
                    return
                }
                itemArg_text.selected = modelData.value
                itemArg_title.text = modelData.title
                if( typeof modelData.description === 'undefined'){
                    return
                }
                itemArg_description.text = modelData.description
            }
        }
    }
    Component{
        id: enum_item
        Item{
            id: itemArg
            property var modelData: null
            width: parent.width
            implicitHeight: itemArg_title.implicitHeight + itemArg_description.implicitHeight
            Layout.fillHeight: true
            FComboBox{
                id: itemArg_text
                width: 300
                anchors{
                    top: parent.top
                    topMargin: 2
                    right: parent.right
                }
                model: ["0", "1", "2"]
            }

            FluText{
                id: itemArg_title
                anchors{
                    top: parent.top
                    left: parent.left
                    right: itemArg_text.left
                }
                text: ""
                font: FluTextStyle.BodyStrong
                wrapMode: Text.WrapAnywhere
                topPadding: 6
            }
            FluText{
                id: itemArg_description
                anchors{
                    top: itemArg_title.bottom
                    left: parent.left
                }
                width: itemArg_title.width
                text: ""
                font: FluTextStyle.Caption
                wrapMode: Text.WrapAnywhere
                topPadding: 6
                rightPadding: 6
            }
            onModelDataChanged: {
                if(modelData === null){
                    console.error("enum model is null")
                    return
                }
                itemArg_text.model = modelData.options
                itemArg_text.show(modelData.value)
                itemArg_title.text = modelData.title
                if( typeof modelData.description === 'undefined'){
                    return
                }
                itemArg_description.text = modelData.description
            }
        }
    }

    onArgsDataChanged: {

    }
    onValueDataChanged: {

    }
    onUpdataData: {
        if(argsData === ""){
            console.error("解析 顺序出问题了")
            return
        }
        if(valueData === ""){
            console.debug("没有数据")
        }

        var args = JSON.parse(argsData)
        var values = JSON.parse(valueData)
        var group = MP.parseGroup(args["properties"])
        var groups = MP.parseGroups(args["properties"])

        for(let task in group){
            var argument = MP.parseArgument(args.definitions, group[task])
            const groupLetter = groups[group[task]]
            var argumentVuale = MP.mergeArgument(argument, values[groupLetter])
//            console.debug(JSON.stringify( argumentVuale ))
//            console.debug("---------------------------------------------------------------")
            createGroup(groupLetter, group[task], argumentVuale)
        }
    }

    /**
     * 创建某个组 的显示组件并显示
     * @param {Object} groupName 变量的名字 是小写的
     * @param {Object} groupTitle 用于向用户显示的名字 大写的
     * @param {Object} argumentVaule 总的显示的参数
     * @returns {Object}
     */
    function createGroup(groupName, groupTitle, argumentValue){
        if(!groupName){
            console.error("no group name")
            return
        }
        if(!groupTitle){
            console.error("no group title")
            return
        }

        var object = group_item.createObject()
        if(object !== null){
            object.groupName = groupName
            object.groupTitle = groupTitle
            object.argumentValue = argumentValue

            contentScrollable.content.push(object)
        }
        else{
            console.error('create group item failed!')
        }
    }


}
