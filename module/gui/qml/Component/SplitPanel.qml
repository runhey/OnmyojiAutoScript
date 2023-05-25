import QtQuick
import QtQuick.Controls
import FluentUI

Item {
    signal clickMessage(string text)

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
                    clickMessage(model.text)
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

    Component.onCompleted: {
        var datas = []
        datas.push(menu_tree.createItem("Home",false))
        datas.push(menu_tree.createItem("Update",false))
//        datas.push(menu_tree.createItem("Node2",true,[createItem("Node2-1",false),createItem("Node2-2",false)]))
        menu_tree.updateData(datas)
    }
    //创建左边的菜单，最多两级
    //['home', 'xxx':['x1', 'x2']]
    function create(data){
        var datas = []
        for(var items in data){
            if(items.length === 0){
                datas.push(menu_tree.createItem(items,false))
            }else{
                var da = []
                for(var item in data[items]){
                    da.push(menu_tree.createItem(data[items][item], false))
                }
                datas.push(menu_tree.createItem(items, true, da))
            }
        }
        menu_tree.updateData(datas)

//        for(let items of data){
//        if(items.length === 'string'){
//            datas.push(menu_tree.createItem(items,false))
//        }else{
//            var da = []
//            for(let item of items){
//                da.push(menu_tree.createItem(item,false))
//            }
//            datas.push(menu_tree.createItem(items, true, da))
//        }

//        }
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
