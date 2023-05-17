import QtQuick
import QtQuick.Window
import QtQuick.Layouts
import QtQuick.Controls
import FluentUI

Item {

    enum TreeViewSelectionMode  {
        None,
        Single,
        Multiple
    }

    property int selectionMode: FluTreeView.None
    property var currentElement
    property var currentParentElement
    property var rootModel: tree_model.get(0).items
    signal itemClicked(var item)

    id:root
    ListModel{
        id:tree_model
        ListElement{
            text: "根节点"
            expanded:true
            items:[]
            key:"123456"
            multipSelected:false
            multipIndex:0
            multipParentKey:""
        }
    }

    Component{
        id: delegate_root
        Column{
            width: calculateWidth()
            property var itemModel: model
            Repeater{
                id: repeater_first_level
                model: items
                delegate: delegate_items
            }
            function calculateWidth(){
                var w = 0;
                for(var i = 0; i < repeater_first_level.count; i++) {
                    var child = repeater_first_level.itemAt(i)
                    if(w < child.width_hint){
                        w = child.width_hint;
                    }
                }
                return w;
            }
        }
    }

    Component{
        id:delegate_items

        Column{
            id:item_layout

            property real level: (mapToItem(list_root,0,0).x+list_root.contentX)/0.001
            property var text: model.text??"Item"
            property bool hasChild : (model.items !== undefined) && (model.items.count !== 0)
            property var items: model.items??[]
            property var expanded: model.expanded??true
            property int width_hint: calculateWidth()
            property bool singleSelected: currentElement === model
            property var itemModel: model

            function calculateWidth(){
                var w = Math.max(list_root.width, item_layout_row.implicitWidth + 10);
                if(expanded){
                    for(var i = 0; i < repeater_items.count; i++) {
                        var child = repeater_items.itemAt(i)
                        if(w < child.width_hint){
                            w = child.width_hint;
                        }
                    }
                }
                return w;
            }
            Item{
                id:item_layout_rect
                width: list_root.contentWidth
                height: item_layout_row.implicitHeight


                Rectangle{
                    anchors.fill: parent
                    anchors.margins: 2
                    color:{
                        if(FluTheme.dark){
                            if(item_layout.singleSelected && selectionMode === FluTreeView.Single){
                                return Qt.rgba(62/255,62/255,62/255,1)
                            }
                            return (item_layout_mouse.containsMouse || item_layout_expanded.hovered || item_layout_checkbox.hovered)?Qt.rgba(62/255,62/255,62/255,1):Qt.rgba(0,0,0,0)
                        }else{
                            if(item_layout.singleSelected && selectionMode === FluTreeView.Single){
                                return Qt.rgba(0,0,0,0.06)
                            }
                            return (item_layout_mouse.containsMouse || item_layout_expanded.hovered || item_layout_checkbox.hovered)?Qt.rgba(0,0,0,0.03):Qt.rgba(0,0,0,0)
                        }
                    }

                    Rectangle{
                        width: 3
                        color:FluTheme.primaryColor.dark
                        visible: item_layout.singleSelected && (selectionMode === FluTreeView.Single)
                        radius: 3
                        height: 20
                        anchors{
                            left: parent.left
                            verticalCenter: parent.verticalCenter
                        }
                    }

                    MouseArea{
                        id:item_layout_mouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: {
                            item_layout_rect.onClickItem()
                        }
                    }
                }


                function onClickItem(){
                    if(selectionMode === FluTreeView.None){
                        itemClicked(model)
                    }
                    if(selectionMode === FluTreeView.Single){
                        currentElement = model
                        if(item_layout.parent.parent.parent.itemModel){
                            currentParentElement = item_layout.parent.parent.parent.itemModel
                        }else{
                            if(item_layout.parent.itemModel){
                                currentParentElement = item_layout.parent.itemModel
                            }
                        }
                        itemClicked(model)
                    }
                    if(selectionMode === FluTreeView.Multiple){

                    }
                }

                RowLayout{
                    id:item_layout_row
                    anchors.verticalCenter: item_layout_rect.verticalCenter

                    Item{
                        width: 15*level
                        Layout.alignment: Qt.AlignVCenter
                    }

                    FluCheckBox{
                        id:item_layout_checkbox
                        text:""
                        selected: itemModel.multipSelected
                        visible: selectionMode === FluTreeView.Multiple
                        Layout.leftMargin: 5

                        function refreshCheckBox(){
                            const stack = [tree_model.get(0)];
                            const result = [];
                            while (stack.length > 0) {
                                const curr = stack.pop();
                                result.unshift(curr);
                                if (curr.items) {
                                    for(var i=0 ; i<curr.items.count ; i++){
                                        curr.items.setProperty(i,"multipIndex",i)
                                        curr.items.setProperty(i,"multipParentKey",curr.key)
                                        stack.push(curr.items.get(i));
                                    }
                                }
                            }
                            for(var j=0 ; j<result.length-1 ; j++){
                                var item = result[j]
                                let obj = result.find(function(o) {
                                    return o.key === item.multipParentKey;
                                });
                                if((item.items !== undefined) && (item.items.count !== 0)){
                                    var items = item.items
                                    for(var k=0 ; k<items.count ; k++){
                                        if(items.get(k).multipSelected === false){
                                            obj.items.setProperty(item.multipIndex,"multipSelected",false)
                                            break
                                        }
                                        obj.items.setProperty(item.multipIndex,"multipSelected",true)
                                    }
                                }
                            }
                        }

                        clickFunc:function(){
                            if(hasChild){
                                const stack = [itemModel];
                                while (stack.length > 0) {
                                    const curr = stack.pop();
                                    if (curr.items) {
                                        for(var i=0 ; i<curr.items.count ; i++){
                                            curr.items.setProperty(i,"multipSelected",!itemModel.multipSelected)
                                            stack.push(curr.items.get(i));
                                        }
                                    }
                                }
                                refreshCheckBox()
                            }else{
                                itemModel.multipSelected = !itemModel.multipSelected
                                refreshCheckBox()
                            }
                        }
                    }

                    FluIconButton{
                        id:item_layout_expanded
                        color:"#00000000"
                        iconSource:item_layout.expanded?FluentIcons.ChevronDown:FluentIcons.ChevronRight
                        opacity: item_layout.hasChild
                        iconSize: 15
                        width: 20
                        height: 20
                        onClicked: {
                            if(!item_layout.hasChild){
                                item_layout_rect.onClickItem()
                                return
                            }
                            model.expanded = !model.expanded
                        }
                    }

                    FluText {
                        text:  item_layout.text
                        Layout.alignment: Qt.AlignVCenter
                        topPadding: 7
                        bottomPadding: 7
                    }
                }
            }

            Item{
                id:item_sub
                visible: {
                    if(!hasChild){
                        return false
                    }
                    return item_layout.expanded??false
                }

                width: item_sub_layout.implicitWidth
                height: item_sub_layout.implicitHeight
                x:0.001
                Column{
                    id: item_sub_layout
                    Repeater{
                        id:repeater_items
                        model: item_layout.items
                        delegate: delegate_items
                    }
                }
            }
        }
    }

    ListView {
        id: list_root
        anchors.fill: parent
        delegate: delegate_root
        contentWidth: contentItem.childrenRect.width
        model: tree_model
        flickableDirection: Flickable.HorizontalAndVerticalFlick
        clip: true
        ScrollBar.vertical: FluScrollBar {}
        ScrollBar.horizontal: FluScrollBar { }
    }

    function updateData(items){
        rootModel.clear()
        rootModel.append(items)
    }

    function signleData(){
        return currentElement
    }

    function multipData(){
        const stack = [tree_model.get(0)];
        const result = [];
        while (stack.length > 0) {
            const curr = stack.pop();
            if(curr.multipSelected){
                result.push(curr)
            }

            for(var i=0 ; i<curr.items.count ; i++){
                stack.push(curr.items.get(i));
            }
        }
        return result
    }

    function createItem(text="",expanded=true,items=[],data={}){
        return {text:text,expanded:expanded,items:items,key:uniqueRandom(),multipSelected:false,multipIndex:0,multipParentKey:"",data:data};
    }

    function uniqueRandom() {
        var timestamp = Date.now();
        var random = Math.floor(Math.random() * 1000000);
        return timestamp.toString() + random.toString();
    }

}
