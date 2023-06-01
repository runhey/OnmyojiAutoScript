import QtQuick
import QtQuick.Controls
import FluentUI
import "./ModelParse.js" as MP

Item {
    property string argsData: ""
    property string valueData: ""
    signal updataData

    FluText{
        text: 'this args '
    }
    FluScrollablePage{
        id: contentScrollable
        width: 700
        height: parent.height
        anchors.horizontalCenter: parent.horizontalCenter
    }

    Component{
        id: group_item
        property string groupName: ""
        property string groupTitle: ""
        property var argumentValue: {""}
        FluExpander{
            headerText: group_item.groupTitle
            width: contentScrollable.width
            Column{
                id: group_column
                anchors.fill: parent
                spacing: 4

                FluTextBox{
                    placeholderText:"单行输入框"
                }

                FluTextBox{
                    placeholderText:"单行输入框"
                }

                FluTextBox{
                    placeholderText:"单行输入框"
                }

            }
        }

    }

//    Component{
//        id: string_item
//        property var modelData: {""}

//        Item{
//            width: contentScrollable.width
//            FluTextBox{
//                id: string_text
//                anchors{
//                    top: parent.top
//                    right: parent.right
//                }
//                placeholderText: modelData.default
//            }

//            FluText{
//                id: string_title
//                anchors{
//                    top: parent.top
//                    left: parent.left
//                    right: string_text.left
//                }
//                text: modelData.title
//                font: FluTextStyle.BodyStrong
//                wrapMode: Text.WrapAnywhere
//                padding: 6
//            }
//            FluText{
//                id: string_description
//                anchors{
//                    top: string_title.bottom
//                }
//                width: string_title.width
//                text: modelData.description
//                font: FluTextStyle.Caption
//                wrapMode: Text.WrapAnywhere
//                padding: 6
//            }
//        }
//    }
//    Component{
//        id: int_item
//    }
//    Component{
//        id: float_item
//    }
//    Component{
//        id: bool_item
//    }
//    Compoenent{
//        id: enum_item
//    }

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
            console.debug(JSON.stringify( argumentVuale ))
            console.debug("---------------------------------------------------------------")
//            createGroup(groupLetter, group[task], argumentVuale)
        }
    }

    /**
     * 创建某个组 的显示组件并显示
     * @param {Object} groupName 变量的名字 是小写的
     * @param {Object} groupTitle 用于向用户显示的名字 大写的
     * @param {Object} argumentVaule 总的显示的参数
     * @returns {Object}
     */
//    function createGroup(groupName, groupTitle, argumentValue){
//        var object = group_item.createObject(contentScrollable)
//        if(object !== null){
//            object.groupName = groupName
//            object.groupTitle = groupTitle
//            object.argumentVale = argumentValue
//        }
//    }
}
