import QtQuick
import QtQuick.Layouts
import QtQuick.Window
import QtQuick.Controls
import FluentUI
import "../component"

FluScrollablePage {

    title:"TreeView"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    function randomName() {
        var names = ["张三", "李四", "王五", "赵六", "钱七", "孙八", "周九", "吴十"]
        return names[Math.floor(Math.random() * names.length)]
    }

    function randomCompany() {
        var companies = ["阿里巴巴", "腾讯", "百度", "京东", "华为", "小米", "字节跳动", "美团", "滴滴"]
        return companies[Math.floor(Math.random() * companies.length)]
    }

    function randomDepartment() {
        var departments = ["技术部", "销售部", "市场部", "人事部", "财务部", "客服部", "产品部", "设计部", "运营部"]
        return departments[Math.floor(Math.random() * departments.length)]
    }

    function createEmployee() {
        var name = randomName()
        return tree_view.createItem(name, false)
    }

    function createSubtree(numEmployees) {
        var employees = []
        for (var i = 0; i < numEmployees; i++) {
            employees.push(createEmployee())
        }
        return tree_view.createItem(randomDepartment(), true, employees)
    }

    function createOrg(numLevels, numSubtrees, numEmployees) {
        if (numLevels === 0) {
            return []
        }
        var subtrees = []
        for (var i = 0; i < numSubtrees; i++) {
            subtrees.push(createSubtree(numEmployees))
        }
        return [tree_view.createItem(randomCompany(), true, subtrees)].concat(createOrg(numLevels - 1, numSubtrees, numEmployees))
    }

    FluArea{
        id:layout_actions
        Layout.fillWidth: true
        Layout.topMargin: 20
        height: 50
        paddings: 10
        RowLayout{
            spacing: 14
            FluDropDownButton{
                id:btn_selection_model
                Layout.preferredWidth: 140
                text:"None"
                items:[
                    FluMenuItem{
                        text:"None"
                        onClicked: {
                            btn_selection_model.text = text
                            tree_view.selectionMode = FluTabView.Equal
                        }
                    },
                    FluMenuItem{
                        text:"Single"
                        onClicked: {
                            btn_selection_model.text = text
                            tree_view.selectionMode = FluTabView.SizeToContent
                        }
                    },
                    FluMenuItem{
                        text:"Muiltple"
                        onClicked: {
                            btn_selection_model.text = text
                            tree_view.selectionMode = FluTabView.Compact
                        }
                    }
                ]
            }
            FluFilledButton{
                text:"获取选中的数据"
                onClicked: {
                    if(tree_view.selectionMode === FluTreeView.None){
                        showError("当前非选择模式,没有选中的数据")
                    }
                    if(tree_view.selectionMode === FluTreeView.Single){
                        if(!tree_view.signleData()){
                            showError("没有选中数据")
                            return
                        }
                        showSuccess(tree_view.signleData().text)
                    }
                    if(tree_view.selectionMode === FluTreeView.Multiple){
                        if(tree_view.multipData().length===0){
                            showError("没有选中数据")
                            return
                        }
                        var info = []
                        tree_view.multipData().map((value)=>info.push(value.text))
                        showSuccess(info.join(","))
                    }
                }
            }
        }
    }
    FluArea{
        Layout.fillWidth: true
        Layout.topMargin: 10
        paddings: 10
        height: 400
        FluTreeView{
            id:tree_view
            width:240
            anchors{
                top:parent.top
                left:parent.left
                bottom:parent.bottom
            }
            onItemClicked:
                (model)=>{
                    showSuccess(model.text)
                }

            Component.onCompleted: {
                var org = createOrg(3, 3, 3)
                createItem()
                updateData(org)
            }
        }
    }

    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluTreeView{
    id:tree_view
    width:240
    height:600
    Component.onCompleted: {
        var datas = []
        datas.push(createItem("Node1",false))
        datas.push(createItem("Node2",false))
        datas.push(createItem("Node2",true,[createItem("Node2-1",false),createItem("Node2-2",false)]))
        updateData(datas)
    }
}
'
    }


}
