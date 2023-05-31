pragma Singleton

import QtQuick
import FluentUI
import "../Global/"

FluObject{
    id: itemsOriginal

    property var navigationView
    FluPaneItem{
        title: qsTr("home")
        icon:FluentIcons.Home
        onTap:{
//            navigationView.push(Qt.resolvedUrl("../../qml/Page/O_Home.qml"))
            navigationView.pushScript(Qt.resolvedUrl("../../qml/Page/O_Home.qml"), "home")
        }
    }
    function getRecentlyAddedData(){
        var arr = []
        for(var i=0;i<children.length;i++){
            var item = children[i]
            if(item instanceof FluPaneItem && item.recentlyAdded){
                arr.push(item)
            }
            if(item instanceof FluPaneItemExpander){
                for(var j=0;j<item.children.length;j++){
                    var itemChild = item.children[j]
                    if(itemChild instanceof FluPaneItem && itemChild.recentlyAdded){
                        arr.push(itemChild)
                    }
                }
            }
        }
        arr.sort(function(o1,o2){ return o2.order-o1.order })
        return arr
    }

    function getRecentlyUpdatedData(){
        var arr = []
        var items = navigationView.getItems();
        for(var i=0;i<items.length;i++){
            var item = items[i]
            if(item instanceof FluPaneItem && item.recentlyUpdated){
                arr.push(item)
            }
        }
        return arr
    }

    function getSearchData(){
        var arr = []
        var items = navigationView.getItems();
        for(var i=0;i<items.length;i++){
            var item = items[i]
            if(item instanceof FluPaneItem){
                arr.push({title:item.title,key:item.key})
            }
        }
        return arr
    }

    function startPageByItem(data){
        navigationView.startPageByItem(data)
    }
    //获取现在存在的所有的Item
    function allPaneItems(){
        var arr = []
        var items = navigationView.getItems();
        for(var i=0;i<items.length;i++){
            var item = items[i]
            if(item instanceof FluPaneItem){
                arr.push(item.title)
            }
        }
        return arr
    }

    //动态添加Paneitem
    function createPaneItem(configName){
        var component = Qt.createComponent("../../qml/Component/ScriptItem.qml")
        if (component.status === Component.Ready) {
            var object = component.createObject(itemsOriginal, {
                title: configName
            });

            if (object !== null) {
                object.title = configName
                // 创建成功，可以进行操作
                children.push(object)
//                children.insert(children.length -1, object)
//                children.splice(children.length-1, object)
            } else {
                // 创建失败
            }
        } else {
            // 组件加载失败
        }
    }
    //给添加
    function addFluPaneItems(){
        var configs = add_config.all_script_files()
        var exists = allPaneItems()
        for(var i=0; i<configs.length; i++){
            if(exists.includes(configs[i])){
            }else{
            createPaneItem(configs[i])
            }
        }
    }

}
