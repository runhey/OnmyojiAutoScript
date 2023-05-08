import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Controls.Basic
import QtQuick.Layouts
import FluentUI

Item {

    enum DisplayMode {
        Open,
        Compact,
        Minimal,
        Auto
    }

    property url logo
    property string title: ""
    property FluObject items
    property FluObject footerItems
    property int displayMode: FluNavigationView.Auto
    property Component  autoSuggestBox
    property var window : {
        if(Window.window == null)
            return null
        return Window.window
    }

    id:control

    QtObject{
        id:d
        property bool enableStack: true
        property int displayMode: {
            if(control.displayMode !==FluNavigationView.Auto){
                return control.displayMode
            }
            if(control.width<=700){
                return FluNavigationView.Minimal
            }else if(control.width<=900){
                return FluNavigationView.Compact
            }else{
                return FluNavigationView.Open
            }
        }
        property var stackItems: []
        property bool enableNavigationPanel: false
        property bool isCompact: d.displayMode === FluNavigationView.Compact
        property bool isMinimal: d.displayMode === FluNavigationView.Minimal
        property bool isCompactAndPanel: d.displayMode === FluNavigationView.Compact && d.enableNavigationPanel
        property bool isCompactAndNotPanel:d.displayMode === FluNavigationView.Compact && !d.enableNavigationPanel
        property bool isMinimalAndPanel: d.displayMode === FluNavigationView.Minimal && d.enableNavigationPanel

        onIsCompactAndNotPanelChanged: {
            collapseAll()
        }

        onDisplayModeChanged: {
            if(d.displayMode === FluNavigationView.Compact){
                collapseAll()
            }
            if(d.displayMode === FluNavigationView.Minimal){
                anim_layout_list_x.enabled = false
                d.enableNavigationPanel = false
                timer_anim_x_enable.restart()
            }
        }

        function handleItems(){
            var idx = 0
            var data = []
            if(items){
                for(var i=0;i<items.children.length;i++){
                    var item = items.children[i]
                    item.idx = idx
                    data.push(item)
                    idx++
                    if(item instanceof FluPaneItemExpander){
                        for(var j=0;j<item.children.length;j++){
                            var itemChild = item.children[j]
                            itemChild.parent = item
                            itemChild.idx = idx
                            data.push(itemChild)
                            idx++
                        }
                    }
                }
                if(footerItems){
                    var comEmpty = Qt.createComponent("FluPaneItemEmpty.qml");
                    for(var k=0;k<footerItems.children.length;k++){
                        var itemFooter = footerItems.children[k]
                        if (comEmpty.status === Component.Ready) {
                            var objEmpty = comEmpty.createObject(items,{idx:idx});
                            itemFooter.idx = idx;
                            data.push(objEmpty)
                            idx++
                        }
                    }
                }
            }
            return data
        }
    }

    Component{
        id:com_panel_item_empty
        Item{
            visible: false
        }
    }

    Component{
        id:com_panel_item_separatorr
        FluDivider{
            width: layout_list.width
            height: {
                if(model.parent){
                    return model.parent.isExpand ? 1 : 0
                }
                return 1
            }
            Behavior on height {
                NumberAnimation{
                    duration: 167
                    easing.type: Easing.BezierSpline
                    easing.bezierCurve: [ 0, 0, 0, 1 ]
                }
            }
        }
    }

    Component{
        id:com_panel_item_header
        Item{
            height: {
                if(model.parent){
                    return model.parent.isExpand ? 30 : 0
                }
                return 30
            }
            Behavior on height {
                NumberAnimation{
                    duration: 167
                    easing.type: Easing.BezierSpline
                    easing.bezierCurve: [ 0, 0, 0, 1 ]
                }
            }
            width: layout_list.width
            FluText{
                text:model.title
                fontStyle: FluText.BodyStrong
                anchors{
                    bottom: parent.bottom
                    left:parent.left
                    leftMargin: 10
                }
            }
        }
    }

    Component{
        id:com_panel_item_expander
        Item{
            height: 38
            width: layout_list.width
            Rectangle{
                radius: 4
                anchors{
                    top: parent.top
                    bottom: parent.bottom
                    left: parent.left
                    right: parent.right
                    topMargin: 2
                    bottomMargin: 2
                    leftMargin: 6
                    rightMargin: 6
                }
                Rectangle{
                    width: 3
                    height: 18
                    radius: 1.5
                    color: FluTheme.primaryColor.dark
                    visible: {
                        for(var i=0;i<model.children.length;i++){
                            var item = model.children[i]
                            if(item.idx === nav_list.currentIndex && !model.isExpand){
                                return true
                            }
                        }
                        return false
                    }
                    anchors{
                        verticalCenter: parent.verticalCenter
                    }
                }
                FluIcon{
                    rotation: model.isExpand?0:180
                    iconSource:FluentIcons.ChevronUp
                    iconSize: 15
                    anchors{
                        verticalCenter: parent.verticalCenter
                        right: parent.right
                        rightMargin: 12
                    }
                    opacity: {
                        if(d.isCompactAndNotPanel){
                            return false
                        }
                        return true
                    }
                    visible:opacity
                    Behavior on opacity {
                        NumberAnimation{
                            duration: 83
                        }
                    }
                    Behavior on rotation {
                        NumberAnimation{
                            duration: 83
                        }
                    }
                }
                MouseArea{
                    id:item_mouse
                    hoverEnabled: true
                    anchors.fill: parent
                    onClicked: {
                        if(d.isCompactAndNotPanel){
                            control_popup.showPopup(Qt.point(50,mapToItem(control,0,0).y),model.children)
                            return
                        }
                        model.isExpand = !model.isExpand
                    }
                }
                color: {
                    if(FluTheme.dark){
                        if((nav_list.currentIndex === idx)&&type===0){
                            return Qt.rgba(1,1,1,0.06)
                        }
                        if(item_mouse.containsMouse){
                            return Qt.rgba(1,1,1,0.03)
                        }
                        return Qt.rgba(0,0,0,0)
                    }else{
                        if(nav_list.currentIndex === idx&&type===0){
                            return Qt.rgba(0,0,0,0.06)
                        }
                        if(item_mouse.containsMouse){
                            return Qt.rgba(0,0,0,0.03)
                        }
                        return Qt.rgba(0,0,0,0)
                    }
                }
                Component{
                    id:com_icon
                    FluIcon{
                        iconSource: {
                            if(model.icon){
                                return model.icon
                            }
                            return 0
                        }
                        iconSize: 15
                    }
                }

                Item{
                    id:item_icon
                    width: 30
                    height: 30
                    anchors{
                        verticalCenter: parent.verticalCenter
                        left:parent.left
                        leftMargin: 3
                    }
                    Loader{
                        anchors.centerIn: parent
                        sourceComponent: {
                            if(model.cusIcon){
                                return model.cusIcon
                            }
                            return com_icon
                        }
                    }
                }
                FluText{
                    id:item_title
                    text:model.title
                    opacity: {
                        if(d.isCompactAndNotPanel){
                            return false
                        }
                        return true
                    }
                    visible:opacity
                    Behavior on opacity {
                        NumberAnimation{
                            duration: 83
                        }
                    }
                    anchors{
                        verticalCenter: parent.verticalCenter
                        left:item_icon.right
                    }
                    color:{
                        if(item_mouse.pressed){
                            return FluTheme.dark ? FluColors.Grey80 : FluColors.Grey120
                        }
                        return FluTheme.dark ? FluColors.White : FluColors.Grey220
                    }
                }
            }
        }
    }

    Component{
        id:com_panel_item
        Item{
            Behavior on height {
                NumberAnimation{
                    duration: 167
                    easing.type: Easing.BezierSpline
                    easing.bezierCurve: [ 0, 0, 0, 1 ]
                }
            }
            clip: true
            height: {
                if(model.parent){
                    return model.parent.isExpand ? 38 : 0
                }
                return 38
            }
            width: layout_list.width
            Rectangle{
                radius: 4
                anchors{
                    top: parent.top
                    bottom: parent.bottom
                    left: parent.left
                    right: parent.right
                    topMargin: 2
                    bottomMargin: 2
                    leftMargin: 6
                    rightMargin: 6
                }
                MouseArea{
                    id:item_mouse
                    hoverEnabled: true
                    anchors.fill: parent
                    onClicked: {
                        if(type === 0){
                            if(model.tapFunc){
                                model.tapFunc()
                            }else{
                                nav_list.currentIndex = idx
                                layout_footer.currentIndex = -1
                                if(d.isMinimal || d.isCompact){
                                    d.enableNavigationPanel = false
                                }
                            }
                        }else{
                            if(model.tapFunc){
                                model.tapFunc()
                            }else{
                                model.tap()
                                d.stackItems.push(model)
                                nav_list.currentIndex = nav_list.count-layout_footer.count+idx
                                layout_footer.currentIndex = idx
                                if(d.isMinimal || d.isCompact){
                                    d.enableNavigationPanel = false
                                }
                            }
                        }
                    }
                }
                color: {
                    if(FluTheme.dark){
                        if(type===0){
                            if(nav_list.currentIndex === idx){
                                return Qt.rgba(1,1,1,0.06)
                            }
                        }else{
                            if(nav_list.currentIndex === (nav_list.count-layout_footer.count+idx)){
                                return Qt.rgba(1,1,1,0.06)
                            }
                        }
                        if(item_mouse.containsMouse){
                            return Qt.rgba(1,1,1,0.03)
                        }
                        return Qt.rgba(0,0,0,0)
                    }else{
                        if(type===0){
                            if(nav_list.currentIndex === idx){
                                return Qt.rgba(0,0,0,0.06)
                            }
                        }else{
                            if(nav_list.currentIndex === (nav_list.count-layout_footer.count+idx)){
                                return Qt.rgba(0,0,0,0.06)
                            }
                        }
                        if(item_mouse.containsMouse){
                            return Qt.rgba(0,0,0,0.03)
                        }
                        return Qt.rgba(0,0,0,0)
                    }
                }
                Component{
                    id:com_icon
                    FluIcon{
                        iconSource: {
                            if(model.icon){
                                return model.icon
                            }
                            return 0
                        }
                        iconSize: 15
                    }
                }

                Item{
                    id:item_icon
                    width: 30
                    height: 30
                    anchors{
                        verticalCenter: parent.verticalCenter
                        left:parent.left
                        leftMargin: 3
                    }
                    Loader{
                        anchors.centerIn: parent
                        sourceComponent: {
                            if(model.cusIcon){
                                return model.cusIcon
                            }
                            return com_icon
                        }
                    }
                }

                FluText{
                    id:item_title
                    text:model.title
                    opacity: {
                        if(d.isCompactAndNotPanel){
                            return false
                        }
                        return true
                    }
                    visible:opacity
                    Behavior on opacity {
                        NumberAnimation{
                            duration: 83
                        }
                    }
                    color:{
                        if(item_mouse.pressed){
                            return FluTheme.dark ? FluColors.Grey80 : FluColors.Grey120
                        }
                        return FluTheme.dark ? FluColors.White : FluColors.Grey220
                    }
                    anchors{
                        verticalCenter: parent.verticalCenter
                        left:item_icon.right
                    }
                }
            }
        }
    }


    Item {
        id:nav_app_bar
        width: parent.width
        height: 50
        z:999
        RowLayout{
            height:parent.height
            spacing: 0
            FluIconButton{
                iconSource: FluentIcons.ChromeBack
                Layout.leftMargin: 5
                Layout.preferredWidth: 40
                Layout.preferredHeight: 40
                Layout.alignment: Qt.AlignVCenter
                disabled:  nav_swipe.depth === 1
                iconSize: 13
                onClicked: {
                    nav_swipe.pop()
                    d.stackItems.pop()
                    var item = d.stackItems[d.stackItems.length-1]
                    d.enableStack = false
                    if(item.idx<(nav_list.count - layout_footer.count)){
                        layout_footer.currentIndex = -1
                    }else{
                        console.debug(item.idx-(nav_list.count-layout_footer.count))
                        layout_footer.currentIndex = item.idx-(nav_list.count-layout_footer.count)
                    }
                    nav_list.currentIndex = item.idx
                    d.enableStack = true
                }
            }
            FluIconButton{
                id:btn_nav
                iconSource: FluentIcons.GlobalNavButton
                iconSize: 15
                Layout.preferredWidth: d.isMinimal ? 40 : 0
                Layout.preferredHeight: 40
                Layout.alignment: Qt.AlignVCenter
                onClicked: {
                    d.enableNavigationPanel = !d.enableNavigationPanel
                }
                visible: Layout.preferredWidth !== 0
                Behavior on Layout.preferredWidth{
                    NumberAnimation{
                        duration: 167
                        easing.type: Easing.BezierSpline
                        easing.bezierCurve: [ 0, 0, 0, 1 ]
                    }
                }
            }
            Image{
                id:image_logo
                Layout.preferredHeight: 20
                Layout.preferredWidth: 20
                source: control.logo
                Layout.leftMargin: {
                    if(btn_nav.visible){
                        return 12
                    }
                    return 5
                }
                Layout.alignment: Qt.AlignVCenter
            }
            FluText{
                Layout.alignment: Qt.AlignVCenter
                text:control.title
                Layout.leftMargin: 12
                fontStyle: FluText.Body
            }
        }
    }

    Item{
        anchors{
            left: d.isMinimal || d.isCompactAndPanel  ? parent.left : layout_list.right
            top: nav_app_bar.bottom
            right: parent.right
            bottom: parent.bottom
            leftMargin: d.isCompactAndPanel ? 50 : 0
        }
        StackView{
            id:nav_swipe
            anchors.fill: parent
            clip: true
            popEnter : Transition{}
            popExit : Transition {
                NumberAnimation {
                    properties: "y"
                    from: 0
                    to: nav_swipe.height
                    duration: 167
                    easing.type: Easing.BezierSpline
                    easing.bezierCurve: [ 1, 0, 0, 0 ]
                }
            }
            pushEnter: Transition {
                NumberAnimation {
                    properties: "y";
                    from: nav_swipe.height;
                    to: 0
                    duration: 167
                    easing.type: Easing.BezierSpline
                    easing.bezierCurve: [ 0, 0, 0, 1 ]
                }
            }
            pushExit : Transition{}
            replaceEnter : Transition{}
            replaceExit : Transition{}
        }
    }

    MouseArea{
        anchors.fill: parent
        visible: d.isMinimalAndPanel||d.isCompactAndPanel
        onClicked: {
            d.enableNavigationPanel = false
        }
    }

    Rectangle{
        id:layout_list
        width: {
            if(d.isCompactAndNotPanel){
                return 50
            }
            return 300
        }
        Behavior on width{
            NumberAnimation{
                duration: 167
                easing.type: Easing.BezierSpline
                easing.bezierCurve: [ 0, 0, 0, 1 ]
            }
        }
        Behavior on x{
            id:anim_layout_list_x
            NumberAnimation{
                duration: 167
                easing.type: Easing.BezierSpline
                easing.bezierCurve: [ 0, 0, 0, 1 ]
            }
        }
        anchors{
            top: parent.top
            bottom: parent.bottom
        }
        border.color: FluTheme.dark ? Qt.rgba(45/255,45/255,45/255,1) : Qt.rgba(226/255,230/255,234/255,1)
        border.width:  d.isMinimal || d.isCompactAndPanel ? 1 : 0
        color: {
            if(d.isMinimal || d.isCompactAndPanel){
                return FluTheme.dark ? Qt.rgba(61/255,61/255,61/255,1) : Qt.rgba(243/255,243/255,243/255,1)
            }
            if(window && window.active){
                return FluTheme.dark ? Qt.rgba(26/255,34/255,41/255,1) : Qt.rgba(238/255,244/255,249/255,1)
            }
            return FluTheme.dark ? Qt.rgba(32/255,32/255,32/255,1) : Qt.rgba(243/255,243/255,243/255,1)
        }
        Behavior on color{
            ColorAnimation {
                duration: 300
            }
        }
        x: {
            if(d.displayMode !== FluNavigationView.Minimal)
                return 0
            return d.isMinimalAndPanel  ? 0 : -width
        }
        Item{
            id:layout_header
            width: layout_list.width
            clip: true
            y:nav_app_bar.height
            height: autoSuggestBox ? 38 : 0
            Loader{
                id:loader_auto_suggest_box
                anchors.centerIn: parent
                sourceComponent: autoSuggestBox
                opacity: {
                    if(d.isCompactAndNotPanel){
                        return false
                    }
                    return true
                }
                visible: opacity
                Behavior on opacity{
                    NumberAnimation{
                        duration: 83
                    }
                }
            }

            FluIconButton{
                visible:opacity
                opacity:d.isCompactAndNotPanel
                Behavior on opacity{
                    NumberAnimation{
                        duration: 83
                    }
                }
                hoverColor: FluTheme.dark ? Qt.rgba(1,1,1,0.03) : Qt.rgba(0,0,0,0.03)
                pressedColor: FluTheme.dark ? Qt.rgba(1,1,1,0.03) : Qt.rgba(0,0,0,0.03)
                normalColor: FluTheme.dark ? Qt.rgba(0,0,0,0) : Qt.rgba(0,0,0,0)
                width:38
                height:34
                x:6
                y:2
                iconSize: 15
                iconSource: {
                    if(loader_auto_suggest_box.item){
                        return loader_auto_suggest_box.item.autoSuggestBoxReplacement
                    }
                    return 0
                }
                onClicked: {
                    d.enableNavigationPanel = !d.enableNavigationPanel
                }
            }
        }

        ListView{
            id:nav_list
            clip: true
            ScrollBar.vertical: FluScrollBar {}
            model:d.handleItems()
            highlightMoveDuration: 150
            highlight: Item{
                clip: true
                Rectangle{
                    height: 18
                    radius: 1.5
                    color: FluTheme.primaryColor.dark
                    width: 3
                    anchors{
                        verticalCenter: parent.verticalCenter
                        left: parent.left
                        leftMargin: 6
                    }
                }
            }
            onCurrentIndexChanged: {
                if(d.enableStack){
                    var item = model[currentIndex]
                    if(item instanceof FluPaneItem){
                        item.tap()
                        d.stackItems.push(item)
                    }
                }
            }
            currentIndex: -1
            anchors{
                top: layout_header.bottom
                topMargin: 6
                left: parent.left
                right: parent.right
                bottom: layout_footer.top
            }
            delegate: Loader{
                property var model: modelData
                property var idx: index
                property int type: 0
                sourceComponent: {
                    if(modelData instanceof FluPaneItem){
                        return com_panel_item
                    }
                    if(modelData instanceof FluPaneItemHeader){
                        return com_panel_item_header
                    }
                    if(modelData instanceof FluPaneItemSeparator){
                        return com_panel_item_separatorr
                    }
                    if(modelData instanceof FluPaneItemExpander){
                        return com_panel_item_expander
                    }
                    if(modelData instanceof FluPaneItemEmpty){
                        return com_panel_item_empty
                    }
                }
            }
        }
        ListView{
            id:layout_footer
            clip: true
            width: layout_list.width
            height: childrenRect.height
            anchors.bottom: parent.bottom
            interactive: false
            currentIndex: -1
            model: {
                if(footerItems){
                    return footerItems.children
                }
            }
            highlightMoveDuration: 150
            highlight: Item{
                clip: true
                Rectangle{
                    height: 18
                    radius: 1.5
                    color: FluTheme.primaryColor.dark
                    width: 3
                    anchors{
                        verticalCenter: parent.verticalCenter
                        left: parent.left
                        leftMargin: 6
                    }
                }
            }
            delegate: Loader{
                property var model: modelData
                property var idx: index
                property int type: 1
                sourceComponent: {
                    if(modelData instanceof FluPaneItem){
                        return com_panel_item
                    }
                    if(modelData instanceof FluPaneItemHeader){
                        return com_panel_item_header
                    }
                    if(modelData instanceof FluPaneItemSeparator){
                        return com_panel_item_separatorr
                    }
                }
            }
        }
    }

    Popup{
        property var childModel
        id:control_popup
        enter: Transition {
            NumberAnimation {
                property: "opacity"
                from:0
                to:1
                duration: 83
            }
        }
        background: Rectangle{
            width: 160
            radius: 4
            FluShadow{
                radius: 4
            }
            color: FluTheme.dark ? Qt.rgba(51/255,48/255,48/255,1) : Qt.rgba(248/255,250/255,253/255,1)
            height: 38*Math.min(Math.max(list_view.count,1),8)
            ListView{
                id:list_view
                anchors.fill: parent
                clip: true
                currentIndex: -1
                model: control_popup.childModel
                ScrollBar.vertical: FluScrollBar {}
                delegate:Button{
                    width: 160
                    padding:10
                    background: Rectangle{
                        color:  {
                            if(hovered){
                                return FluTheme.dark ? Qt.rgba(63/255,60/255,61/255,1) : Qt.rgba(237/255,237/255,242/255,1)
                            }
                            return FluTheme.dark ? Qt.rgba(51/255,48/255,48/255,1) : Qt.rgba(0,0,0,0)
                        }
                    }
                    contentItem: FluText{
                        text:modelData.title
                        anchors{
                            verticalCenter: parent.verticalCenter
                        }
                    }
                    onClicked: {
                        if(modelData.tapFunc){
                            modelData.tapFunc()
                        }else{
                            nav_list.currentIndex = idx
                            layout_footer.currentIndex = -1
                            if(d.isMinimal || d.isCompact){
                                d.enableNavigationPanel = false
                            }
                        }
                        control_popup.close()
                    }
                }
            }
        }
        function showPopup(pos,model){
            control_popup.x = pos.x
            control_popup.y = pos.y
            control_popup.childModel = model
            control_popup.open()
        }
    }

    Timer{
        id:timer_anim_x_enable
        interval: 150
        onTriggered: {
            anim_layout_list_x.enabled = true
        }
    }

    function collapseAll(){
        for(var i=0;i<nav_list.model.length;i++){
            var item = nav_list.model[i]
            if(item instanceof FluPaneItemExpander){
                item.isExpand = false
            }
        }
    }

    function setCurrentIndex(index){
        nav_list.currentIndex = index

    }

    function getItems(){
        return nav_list.model
    }

    function push(url){
        nav_swipe.push(url)
    }

    function getCurrentIndex(){
        return nav_list.currentIndex
    }

    function startPageByItem(data){
        var items = getItems();
        for(var i=0;i<items.length;i++){
            var item =  items[i]
            if(item.key === data.key){
                if(getCurrentIndex() === i){
                    return
                }
                setCurrentIndex(i)
                if(item.parent && !d.isCompactAndNotPanel){
                    item.parent.isExpand = true
                }
                return
            }
        }
    }

}
