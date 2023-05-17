import QtQuick
import QtQuick.Controls
import FluentUI

Item {

    // 左边菜单
    FluArea{
        id: menuArea
        anchors.left: parent.left
        height: parent.height
        width: 200
        FluTreeView{
            id: menu_tree
            anchors.fill: parent
            Component.onCompleted: {
                var datas = []
                datas.push(createItem("Node1",false))
                datas.push(createItem("Node2",false))
                datas.push(createItem("Node2",true,[createItem("Node2-1",false),createItem("Node2-2",false)]))
                updateData(datas)
            }
        }
    }
    // 右边内容
    FluArea{
        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.left: menuArea.right
        anchors.leftMargin: 12
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
    }
}
