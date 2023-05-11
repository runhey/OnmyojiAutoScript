import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import FluentUI

Item{
//    leftPadding:10
//    rightPadding:10
//    bottomPadding:20
    FluTreeView{
        id: menu_tree
        anchors.left: parent.left
        width:200
        height:parent.height
        Component.onCompleted: {
            var datas = []
            datas.push(createItem("Node1",false))
            datas.push(createItem("Node2",false))
            datas.push(createItem("Node2",true,[createItem("Node2-1",false),createItem("Node2-2",false)]))
            updateData(datas)
        }
    }
    FluArea{
        anchors.right: parent.right
        anchors.left: menu_tree.right
        height: parent.height
    }
}
