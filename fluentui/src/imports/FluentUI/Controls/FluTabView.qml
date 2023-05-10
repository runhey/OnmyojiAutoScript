import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import FluentUI

Item {

    enum TabWidthBehavior {
        Equal,
        SizeToContent,
        Compact
    }

    enum CloseButtonVisibility{
        Nerver,
        Always,
        OnHover
    }

    property int tabWidthBehavior : FluTabView.Equal
    property int closeButtonVisibility : FluTabView.Always
    property int itemWidth: 146
    property bool addButtonVisibility: true
    signal newPressed

    id:control
    implicitHeight: height
    implicitWidth: width
    anchors.fill: {
        if(parent)
            return parent
        return undefined
    }

    QtObject {
        id: d
        property int dragIndex: -1
        property bool dragBehavior: false
        property bool itemPress: false
        property int maxEqualWidth: 240
    }

    MouseArea{
        anchors.fill: parent
        preventStealing: true
    }

    ListModel{
        id:tab_model
    }

    FluIconButton{
        id:btn_new
        visible: addButtonVisibility
        width: 34
        height: 34
        x:Math.min(tab_nav.contentWidth,tab_nav.width)
        anchors.top: parent.top
        iconSource: FluentIcons.Add
        onClicked: {
            newPressed()
        }
    }

    ListView{
        id:tab_nav
        height: 34
        orientation: ListView.Horizontal
        anchors{
            top: parent.top
            left: parent.left
            right: parent.right
            rightMargin: 34
        }
        interactive: false
        model: tab_model
        move: Transition {
            NumberAnimation { properties: "x"; duration: 100; easing.type: Easing.OutCubic }
            NumberAnimation { properties: "y"; duration: 100; easing.type: Easing.OutCubic }
        }
        moveDisplaced: Transition {
            NumberAnimation { properties: "x"; duration: 300; easing.type: Easing.OutCubic}
            NumberAnimation { properties: "y"; duration: 100;  easing.type: Easing.OutCubic }
        }
        clip: true
        ScrollBar.horizontal: ScrollBar{
            id: scroll_nav
            policy: ScrollBar.AlwaysOff
        }
        delegate:  Item{

            width: item_layout.width
            height: item_container.height
            z: item_mouse_drag.pressed ? 1000 : 1

            Item{
                id:item_layout
                width: item_container.width
                height: item_container.height

                FluItem{
                    id:item_container

                    property real timestamp: new Date().getTime()

                    height: tab_nav.height
                    width: {
                        if(tabWidthBehavior === FluTabView.Equal){
                            return Math.max(Math.min(d.maxEqualWidth,tab_nav.width/tab_nav.count),41 + item_btn_close.width)
                        }
                        if(tabWidthBehavior === FluTabView.SizeToContent){
                            return itemWidth
                        }
                        if(tabWidthBehavior === FluTabView.Compact){
                            return item_mouse_hove.containsMouse || item_btn_close.hovered || tab_nav.currentIndex === index  ? itemWidth : 41 + item_btn_close.width
                        }
                        return Math.max(Math.min(d.maxEqualWidth,tab_nav.width/tab_nav.count),41 + item_btn_close.width)
                    }
                    radius: [6,6,0,0]
                    Behavior on x { enabled: d.dragBehavior; NumberAnimation { duration: 200 } }
                    Behavior on y { enabled: d.dragBehavior; NumberAnimation { duration: 200 } }

                    MouseArea{
                        id:item_mouse_hove
                        anchors.fill: parent
                        hoverEnabled: true
                    }

                    MouseArea{
                        id:item_mouse_drag
                        anchors.fill: parent
                        drag.target: item_container
                        drag.axis: Drag.XAxis

                        onWheel: (wheel)=>{
                                     if (wheel.angleDelta.y > 0) scroll_nav.decrease()
                                     else scroll_nav.increase()
                                 }

                        onPressed: {
                            d.itemPress = true
                            item_container.timestamp = new Date().getTime();
                            d.dragBehavior = false;
                            var pos = tab_nav.mapFromItem(item_container, 0, 0)
                            d.dragIndex = model.index
                            item_container.parent = tab_nav
                            item_container.x = pos.x
                            item_container.y = pos.y
                        }

                        onReleased: {
                            d.itemPress = false
                            timer.stop()
                            var timeDiff = new Date().getTime() - item_container.timestamp
                            if (timeDiff < 300) {
                                tab_nav.currentIndex = index
                            }
                            d.dragIndex = -1;
                            var pos = tab_nav.mapToItem(item_layout, item_container.x, item_container.y)
                            item_container.parent = item_layout;
                            item_container.x = pos.x;
                            item_container.y = pos.y;
                            d.dragBehavior = true;
                            item_container.x = 0;
                            item_container.y = 0;
                        }

                        onPositionChanged: {
                            var pos = tab_nav.mapFromItem(item_container, 0, 0)
                            updatePosition(pos)
                            if(pos.x<0){
                                timer.isIncrease = false
                                timer.restart()
                            }else if(pos.x>tab_nav.width-itemWidth){
                                timer.isIncrease = true
                                timer.restart()
                            }else{
                                timer.stop()
                            }
                        }
                        Timer{
                            id:timer
                            property bool isIncrease: true
                            interval: 10
                            repeat: true
                            onTriggered: {
                                if(isIncrease){
                                    if(tab_nav.contentX>=tab_nav.contentWidth-tab_nav.width){
                                        return
                                    }
                                    tab_nav.contentX = tab_nav.contentX+2
                                }else{
                                    if(tab_nav.contentX<=0){
                                        return
                                    }
                                    tab_nav.contentX = tab_nav.contentX-2
                                }
                                item_mouse_drag.updatePosition(tab_nav.mapFromItem(item_container, 0, 0))
                            }
                        }
                        function updatePosition(pos){
                            var idx = tab_nav.indexAt(pos.x+tab_nav.contentX+1, pos.y)
                            var firstIdx = tab_nav.indexAt(tab_nav.contentX+1, pos.y)
                            var lastIdx = tab_nav.indexAt(tab_nav.width+tab_nav.contentX-1, pos.y)
                            if(lastIdx === -1){
                                lastIdx = tab_nav.count-1
                            }
                            if (idx!==-1 && idx >= firstIdx && idx <= lastIdx && d.dragIndex !== idx) {
                                tab_model.move(d.dragIndex, idx, 1)
                                d.dragIndex = idx;
                            }
                        }
                    }

                    Rectangle{
                        anchors.fill: parent
                        color: {
                            if(FluTheme.dark){
                                if(item_mouse_hove.containsMouse || item_btn_close.hovered){
                                    return Qt.rgba(1,1,1,0.03)
                                }
                                if(tab_nav.currentIndex === index){
                                    return Qt.rgba(1,1,1,0.06)
                                }
                                return Qt.rgba(0,0,0,0)
                            }else{
                                if(item_mouse_hove.containsMouse || item_btn_close.hovered){
                                    return Qt.rgba(0,0,0,0.03)
                                }
                                if(tab_nav.currentIndex === index){
                                    return Qt.rgba(0,0,0,0.06)
                                }
                                return Qt.rgba(0,0,0,0)
                            }
                        }
                    }

                    RowLayout{
                        spacing: 0
                        height: parent.height
                        Image{
                            source:model.icon
                            Layout.leftMargin: 10
                            Layout.preferredWidth: 14
                            Layout.preferredHeight: 14
                            Layout.alignment: Qt.AlignVCenter
                        }
                        FluText{
                            id:item_text
                            text: model.text
                            Layout.leftMargin: 10
                            visible: {
                                if(tabWidthBehavior === FluTabView.Equal){
                                    return true
                                }
                                if(tabWidthBehavior === FluTabView.SizeToContent){
                                    return true
                                }
                                if(tabWidthBehavior === FluTabView.Compact){
                                    return item_mouse_hove.containsMouse || item_btn_close.hovered || tab_nav.currentIndex === index
                                }
                                return false
                            }
                            Layout.preferredWidth: visible?item_container.width - 41 - item_btn_close.width:0
                            elide: Text.ElideRight
                            Layout.alignment: Qt.AlignVCenter
                            FluTooltip{
                                visible: item_mouse_hove.containsMouse
                                text:item_text.text
                                delay: 1000
                            }
                        }
                    }

                    FluIconButton{
                        id:item_btn_close
                        iconSource: FluentIcons.ChromeClose
                        iconSize: 10
                        width: visible ? 24 : 0
                        height: 24
                        visible: {
                            if(closeButtonVisibility === FluTabView.Nerver)
                                return false
                            if(closeButtonVisibility === FluTabView.OnHover)
                                return item_mouse_hove.containsMouse || item_btn_close.hovered
                            return true
                        }
                        anchors{
                            right: parent.right
                            rightMargin: 5
                            verticalCenter: parent.verticalCenter
                        }
                        onClicked: {
                            tab_model.remove(index)
                        }
                    }

                    FluDivider{
                        width: 1
                        height: 16
                        anchors{
                            verticalCenter: parent.verticalCenter
                            right: parent.right
                        }
                    }
                }
            }
        }
    }


    Item{
        id:container
        anchors{
            top: tab_nav.bottom
            left: parent.left
            right: parent.right
            bottom: parent.bottom
        }

        Repeater{
            model:tab_model
            Loader{
                property var argument: model.argument
                anchors.fill: parent
                sourceComponent: model.page
                visible: tab_nav.currentIndex === index
            }
        }
    }


    function createTab(icon,text,page,argument={}){
        return {icon:icon,text:text,page:page,argument:argument}
    }

    function appendTab(icon,text,page,argument){
        tab_model.append(createTab(icon,text,page,argument))
    }

    function setTabList(list){
        tab_model.clear()
        tab_model.append(list)
    }

    function count(){
        return tab_nav.count
    }

}
