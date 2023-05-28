import QtQuick
import QtQuick.Controls
import FluentUI
import "../Global"

Item {
    id: splitPanel
    property string title: ""

    // 左边菜单
    FluArea{
        id: menuArea
        anchors.left: parent.left
        height: parent.height
        width: 200
        FluTreeView{
            id: menu_tree
            anchors.fill: parent
            selectionMode: FluTabView.SizeToContent

            onItemClicked:(model)=>{
                    MainEvent.menuTitle = model.text
                    splitPanel.title = model.text
                    showSuccess(model.text)
                }
        }
    }
    // 右边内容
    Loader{
        id: contentDefalut
        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.left: menuArea.right
        anchors.leftMargin: 12
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
    }
    Loader{
        id: contentLoader
        anchors.right: parent.right
        anchors.rightMargin: 12
        anchors.left: menuArea.right
        anchors.leftMargin: 12
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.bottomMargin: 12
    }

    //创建左边的菜单，最多两级
    //['home', 'xxx':['x1', 'x2']]  是英文的
    function create(data){
        var datas = []
        for(var items in data){
            if(items.length === 0){
                datas.push(menu_tree.createItem(qsTr(items),false))
            }else{
                var da = []
                for(var item in data[items]){
                    da.push(menu_tree.createItem(qsTr(data[items][item]), false))
                }
                datas.push(menu_tree.createItem(qsTr(items), true, da))
            }
        }
        menu_tree.updateData(datas)
    }

    //右侧的分为两个部分一个部分是contentDefalut表示固定的不动的
    //第二个部分是一个加载器动态加载不同的组件
    //显示固定的部分
    function showDefalut(){
        contentDefalut.visible = true
        contentLoader.visible = false
    }
    //显示不固定的
    function showLoader(){
        contentDefalut.visible = false
        contentLoader.visible = true
    }

    //设置固定的部分的具体内容  主要是传一个组件
    function setDefalut(component){
        contentDefalut.sourceComponent = component
        showDefalut()
    }
    //
    function setLoader(component){
        contentLoader.sourceComponent = component
        showLoader()
    }

    //获取固定的部分的对象的，方便更改属性
//    function getDefalut(){
//        return contentDefalut.item
//    }
//    //方便更改属性
//    function getDefalut(){
//        return contentLoader.item
//    }


}
