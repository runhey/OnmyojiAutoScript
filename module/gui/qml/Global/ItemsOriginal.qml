pragma Singleton

import QtQuick
import FluentUI
import "../Global/"

FluObject{
    id: itemsOriginal

    property var navigationView
    FluPaneItem{
        title: "home"
        icon:FluentIcons.Home
        onTap:{
            navigationView.push(Qt.resolvedUrl("../../qml/Page/O_Home.qml"))
        }
    }
    FluPaneItem{
        title: "add"
        icon: FluentIcons.Add
        onTap:{
            MainEvent.addOpen = !MainEvent.addOpen
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

}
