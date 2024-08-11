import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Controls.Basic
import QtQuick.Layouts
import FluentUI

Item {
    id: control
    enum DisplayMode {
        Open,
        Compact,
        Minimal,
        Auto
    }

    property Component autoSuggestBox
    property int displayMode: FluNavigationView.Auto
    property FluObject footerItems
    property FluObject items
    property url logo
    property string title: ""
    property var window: {
        if (Window.window == null)
            return null;
        return Window.window;
    }

    function collapseAll() {
        for (var i = 0; i < nav_list.model.length; i++) {
            var item = nav_list.model[i];
            if (item instanceof FluPaneItemExpander) {
                item.isExpand = false;
            }
        }
    }
    //閫氳繃configName鎵惧埌index
    function configName2index(configName) {
        if (nav_swipe.count <= 0) {
            return -1;
        }
        for (var i = 0; i < nav_swipe.count; i++) {
            var item = nav_swipe.itemAt(i);
            if (item.configName === configName) {
                return i;
            }
        }
        return -1;
    }
    function getCurrentIndex() {
        return nav_list.currentIndex;
    }
    function getItems() {
        return nav_list.model;
    }
    function push(url) {
        var component = Qt.createComponent(url);
        if (component.status === Component.Ready) {
            var object = component.createObject(nav_swipe);
            if (object !== null) {
                nav_swipe.addItem(object);
                nav_swipe.setCurrentIndex(nav_swipe.count - 1);
            } else // 鍒涘缓澶辫触
            {
            }
        } else // 缁勪欢鍔犺浇澶辫触
        {
        }
    }

    // z閽堝鑴氭湰鐨勬坊鍔犵殑
    function pushScript(url, configName) {
        var index = configName2index(configName);
        if (index === -1) {
            //濡傛灉鎵句笉鍒版垨鑰呭帇鏍硅繕娌℃湁Page,灏卞垱寤哄苟鍘嬪叆
            var component = Qt.createComponent(url);
            if (component.status === Component.Ready) {
                var object = component.createObject(nav_swipe);
                if (object !== null) {
                    object.configName = configName;
                    if(configName === "home"){
                        nav_swipe.insertItem(0, object)
                        nav_swipe.setCurrentIndex(0)
                    }else if(configName === "settings"){
                        nav_swipe.addItem(object);
                        nav_swipe.setCurrentIndex(nav_swipe.count - 1);
                    }else{
                        var settings_index = configName2index("settings")
                        if(settings_index !== -1){
                            nav_swipe.insertItem(settings_index, object)
                            nav_swipe.setCurrentIndex(settings_index);
                        }else{
                           nav_swipe.addItem(object);
                            nav_swipe.setCurrentIndex(nav_swipe.count - 1);
                        }
                    }


                } else {
                    // 鍒涘缓澶辫触
                    console.debug('瀵硅薄鍒涘缓澶辫触');
                }
            } else {
                // 缁勪欢鍔犺浇澶辫触
                console.debug('缁勪欢鍔犺浇澶辫触');
            }
        } else {
            // 鎵惧緱鍒扮洿鎺ヨ缃埌褰撳墠鐨�
            nav_swipe.setCurrentIndex(index);
        }
    }
    function setCurrentIndex(index) {
        nav_list.currentIndex = index;
    }
    function startPageByItem(data) {
        var items = getItems();
        for (var i = 0; i < items.length; i++) {
            var item = items[i];
            if (item.key === data.key) {
                if (getCurrentIndex() === i) {
                    return;
                }
                setCurrentIndex(i);
                if (item.parent && !d.isCompactAndNotPanel) {
                    item.parent.isExpand = true;
                }
                return;
            }
        }
    }

    QtObject {
        id: d

        property int displayMode: {
            if (control.displayMode !== FluNavigationView.Auto) {
                return control.displayMode;
            }
            if (control.width <= 700) {
                return FluNavigationView.Minimal;
            } else if (control.width <= 900) {
                return FluNavigationView.Compact;
            } else {
                return FluNavigationView.Open;
            }
        }
        property bool enableNavigationPanel: false
        property bool enableStack: true
        property bool isCompact: d.displayMode === FluNavigationView.Compact
        property bool isCompactAndNotPanel: d.displayMode === FluNavigationView.Compact && !d.enableNavigationPanel
        property bool isCompactAndPanel: d.displayMode === FluNavigationView.Compact && d.enableNavigationPanel
        property bool isMinimal: d.displayMode === FluNavigationView.Minimal
        property bool isMinimalAndPanel: d.displayMode === FluNavigationView.Minimal && d.enableNavigationPanel
        property var stackItems: []

        function handleItems() {
            var idx = 0;
            var data = [];
            if (items) {
                for (var i = 0; i < items.children.length; i++) {
                    var item = items.children[i];
                    item.idx = idx;
                    data.push(item);
                    idx++;
                    if (item instanceof FluPaneItemExpander) {
                        for (var j = 0; j < item.children.length; j++) {
                            var itemChild = item.children[j];
                            itemChild.parent = item;
                            itemChild.idx = idx;
                            data.push(itemChild);
                            idx++;
                        }
                    }
                }
                if (footerItems) {
                    var comEmpty = Qt.createComponent("FluPaneItemEmpty.qml");
                    for (var k = 0; k < footerItems.children.length; k++) {
                        var itemFooter = footerItems.children[k];
                        if (comEmpty.status === Component.Ready) {
                            var objEmpty = comEmpty.createObject(items, {
                                    "idx": idx
                                });
                            itemFooter.idx = idx;
                            data.push(objEmpty);
                            idx++;
                        }
                    }
                }
            }
            return data;
        }

        onDisplayModeChanged: {
            if (d.displayMode === FluNavigationView.Compact) {
                collapseAll();
            }
            if (d.displayMode === FluNavigationView.Minimal) {
                anim_layout_list_x.enabled = false;
                d.enableNavigationPanel = false;
                timer_anim_x_enable.restart();
            }
        }
        onIsCompactAndNotPanelChanged: {
            collapseAll();
        }
    }
    Component {
        id: com_panel_item_empty
        Item {
            visible: false
        }
    }
    Component {
        id: com_panel_item_separatorr
        FluDivider {
            height: {
                if (model.parent) {
                    return model.parent.isExpand ? 1 : 0;
                }
                return 1;
            }
            width: layout_list.width

            Behavior on height  {
                NumberAnimation {
                    duration: 167
                    easing.bezierCurve: [0, 0, 0, 1]
                    easing.type: Easing.BezierSpline
                }
            }
        }
    }
    Component {
        id: com_panel_item_header
        Item {
            height: {
                if (model.parent) {
                    return model.parent.isExpand ? 30 : 0;
                }
                return 30;
            }
            width: layout_list.width

            Behavior on height  {
                NumberAnimation {
                    duration: 167
                    easing.bezierCurve: [0, 0, 0, 1]
                    easing.type: Easing.BezierSpline
                }
            }

            FluText {
                font: FluTextStyle.BodyStrong
                text: model.title

                anchors {
                    bottom: parent.bottom
                    left: parent.left
                    leftMargin: 10
                }
            }
        }
    }
    Component {
        id: com_panel_item_expander
        Item {
            height: 38
            width: layout_list.width

            Rectangle {
                color: {
                    if (FluTheme.dark) {
                        if ((nav_list.currentIndex === idx) && type === 0) {
                            return Qt.rgba(1, 1, 1, 0.06);
                        }
                        if (item_mouse.containsMouse) {
                            return Qt.rgba(1, 1, 1, 0.03);
                        }
                        return Qt.rgba(0, 0, 0, 0);
                    } else {
                        if (nav_list.currentIndex === idx && type === 0) {
                            return Qt.rgba(0, 0, 0, 0.06);
                        }
                        if (item_mouse.containsMouse) {
                            return Qt.rgba(0, 0, 0, 0.03);
                        }
                        return Qt.rgba(0, 0, 0, 0);
                    }
                }
                radius: 4

                anchors {
                    bottom: parent.bottom
                    bottomMargin: 2
                    left: parent.left
                    leftMargin: 6
                    right: parent.right
                    rightMargin: 6
                    top: parent.top
                    topMargin: 2
                }
                Rectangle {
                    color: FluTheme.primaryColor.dark
                    height: 18
                    radius: 1.5
                    visible: {
                        for (var i = 0; i < model.children.length; i++) {
                            var item = model.children[i];
                            if (item.idx === nav_list.currentIndex && !model.isExpand) {
                                return true;
                            }
                        }
                        return false;
                    }
                    width: 3

                    anchors {
                        verticalCenter: parent.verticalCenter
                    }
                }
                FluIcon {
                    iconSize: 15
                    iconSource: FluentIcons.ChevronUp
                    opacity: {
                        if (d.isCompactAndNotPanel) {
                            return false;
                        }
                        return true;
                    }
                    rotation: model.isExpand ? 0 : 180
                    visible: opacity

                    Behavior on opacity  {
                        NumberAnimation {
                            duration: 83
                        }
                    }
                    Behavior on rotation  {
                        NumberAnimation {
                            duration: 83
                        }
                    }

                    anchors {
                        right: parent.right
                        rightMargin: 12
                        verticalCenter: parent.verticalCenter
                    }
                }
                MouseArea {
                    id: item_mouse
                    anchors.fill: parent
                    hoverEnabled: true

                    onClicked: {
                        if (d.isCompactAndNotPanel) {
                            control_popup.showPopup(Qt.point(50, mapToItem(control, 0, 0).y), model.children);
                            return;
                        }
                        model.isExpand = !model.isExpand;
                    }
                }
                Component {
                    id: com_icon
                    FluIcon {
                        iconSize: 15
                        iconSource: {
                            if (model.icon) {
                                return model.icon;
                            }
                            return 0;
                        }
                    }
                }
                Item {
                    id: item_icon
                    height: 30
                    width: 30

                    anchors {
                        left: parent.left
                        leftMargin: 3
                        verticalCenter: parent.verticalCenter
                    }
                    Loader {
                        anchors.centerIn: parent
                        sourceComponent: {
                            if (model.cusIcon) {
                                return model.cusIcon;
                            }
                            return com_icon;
                        }
                    }
                }
                FluText {
                    id: item_title
                    color: {
                        if (item_mouse.pressed) {
                            return FluTheme.dark ? FluColors.Grey80 : FluColors.Grey120;
                        }
                        return FluTheme.dark ? FluColors.White : FluColors.Grey220;
                    }
                    opacity: {
                        if (d.isCompactAndNotPanel) {
                            return false;
                        }
                        return true;
                    }
                    text: model.title
                    visible: opacity

                    Behavior on opacity  {
                        NumberAnimation {
                            duration: 83
                        }
                    }

                    anchors {
                        left: item_icon.right
                        verticalCenter: parent.verticalCenter
                    }
                }
            }
        }
    }
    Component {
        id: com_panel_item
        Item {
            clip: true
            height: {
                if (model.parent) {
                    return model.parent.isExpand ? 38 : 0;
                }
                return 38;
            }
            width: layout_list.width

            Behavior on height  {
                NumberAnimation {
                    duration: 167
                    easing.bezierCurve: [0, 0, 0, 1]
                    easing.type: Easing.BezierSpline
                }
            }

            Rectangle {
                color: {
                    if (FluTheme.dark) {
                        if (type === 0) {
                            if (nav_list.currentIndex === idx) {
                                return Qt.rgba(1, 1, 1, 0.06);
                            }
                        } else {
                            if (nav_list.currentIndex === (nav_list.count - layout_footer.count + idx)) {
                                return Qt.rgba(1, 1, 1, 0.06);
                            }
                        }
                        if (item_mouse.containsMouse) {
                            return Qt.rgba(1, 1, 1, 0.03);
                        }
                        return Qt.rgba(0, 0, 0, 0);
                    } else {
                        if (type === 0) {
                            if (nav_list.currentIndex === idx) {
                                return Qt.rgba(0, 0, 0, 0.06);
                            }
                        } else {
                            if (nav_list.currentIndex === (nav_list.count - layout_footer.count + idx)) {
                                return Qt.rgba(0, 0, 0, 0.06);
                            }
                        }
                        if (item_mouse.containsMouse) {
                            return Qt.rgba(0, 0, 0, 0.03);
                        }
                        return Qt.rgba(0, 0, 0, 0);
                    }
                }
                radius: 4

                anchors {
                    bottom: parent.bottom
                    bottomMargin: 2
                    left: parent.left
                    leftMargin: 6
                    right: parent.right
                    rightMargin: 6
                    top: parent.top
                    topMargin: 2
                }
                MouseArea {
                    id: item_mouse
                    anchors.fill: parent
                    hoverEnabled: true

                    onClicked: {
                        if (type === 0) {
                            if (model.tapFunc) {
                                model.tapFunc();
                            } else {
                                nav_list.currentIndex = idx;
                                layout_footer.currentIndex = -1;
                                if (d.isMinimal || d.isCompact) {
                                    d.enableNavigationPanel = false;
                                }
                            }
                        } else {
                            if (model.tapFunc) {
                                model.tapFunc();
                            } else {
                                model.tap();
                                d.stackItems.push(model);
                                nav_list.currentIndex = nav_list.count - layout_footer.count + idx;
                                layout_footer.currentIndex = idx;
                                if (d.isMinimal || d.isCompact) {
                                    d.enableNavigationPanel = false;
                                }
                            }
                        }
                        nav_app_bar_pane_title.text = model.title;
                    }
                }
                Component {
                    id: com_icon
                    FluIcon {
                        iconSize: 15
                        iconSource: {
                            if (model.icon) {
                                return model.icon;
                            }
                            return 0;
                        }
                    }
                }
                Item {
                    id: item_icon
                    height: 30
                    width: 30

                    anchors {
                        left: parent.left
                        leftMargin: 3
                        verticalCenter: parent.verticalCenter
                    }
                    Loader {
                        anchors.centerIn: parent
                        sourceComponent: {
                            if (model.cusIcon) {
                                return model.cusIcon;
                            }
                            return com_icon;
                        }
                    }
                }
                FluText {
                    id: item_title
                    color: {
                        if (item_mouse.pressed) {
                            return FluTheme.dark ? FluColors.Grey80 : FluColors.Grey120;
                        }
                        return FluTheme.dark ? FluColors.White : FluColors.Grey220;
                    }
                    opacity: {
                        if (d.isCompactAndNotPanel) {
                            return false;
                        }
                        return true;
                    }
                    text: model.title
                    visible: opacity

                    Behavior on opacity  {
                        NumberAnimation {
                            duration: 83
                        }
                    }

                    anchors {
                        left: item_icon.right
                        verticalCenter: parent.verticalCenter
                    }
                }
            }
        }
    }
    Item {
        id: nav_app_bar
        height: 40
        width: parent.width
        z: 999

        RowLayout {
            height: parent.height
            spacing: 0

            //            FluIconButton{
            //                iconSource: FluentIcons.ChromeBack
            //                Layout.leftMargin: 5
            //                Layout.preferredWidth: 40
            //                Layout.preferredHeight: 40
            //                Layout.alignment: Qt.AlignVCenter
            //                disabled:  nav_swipe.depth === 1
            //                iconSize: 13
            //                onClicked: {
            //                    nav_swipe.pop()
            //                    d.stackItems.pop()
            //                    var item = d.stackItems[d.stackItems.length-1]
            //                    d.enableStack = false
            //                    if(item.idx<(nav_list.count - layout_footer.count)){
            //                        layout_footer.currentIndex = -1
            //                    }else{
            //                        console.debug(item.idx-(nav_list.count-layout_footer.count))
            //                        layout_footer.currentIndex = item.idx-(nav_list.count-layout_footer.count)
            //                    }
            //                    nav_list.currentIndex = item.idx
            //                    d.enableStack = true
            //                }
            //            }
            FluIconButton {
                id: btn_nav
                Layout.alignment: Qt.AlignVCenter
                Layout.preferredHeight: 40
                Layout.preferredWidth: d.isMinimal ? 40 : 0
                iconSize: 15
                iconSource: FluentIcons.GlobalNavButton
                visible: d.isMinimal

                Behavior on Layout.preferredWidth  {
                    NumberAnimation {
                        duration: 167
                        easing.bezierCurve: [0, 0, 0, 1]
                        easing.type: Easing.BezierSpline
                    }
                }

                onClicked: {
                    d.enableNavigationPanel = !d.enableNavigationPanel;
                }
            }
            Item {
                Layout.alignment: Qt.AlignVCenter
                Layout.leftMargin: 5
                Layout.preferredHeight: 40
                Layout.preferredWidth: 40

                Image {
                    id: image_logo
                    anchors.centerIn: parent
                    height: 20
                    source: control.logo
                    width: 20
                }
                MouseArea {
                    anchors.fill: parent

                    onClicked: Qt.openUrlExternally("https://github.com/runhey/OnmyojiAutoScript")
                }
            }
            FluText {
                Layout.alignment: Qt.AlignVCenter
                Layout.leftMargin: 12
                font: FluTextStyle.BodyStrong
                text: control.title
            }
            FluText {
                Layout.alignment: Qt.AlignVCenter
                Layout.leftMargin: 2
                font: FluTextStyle.Body
                text: ">"
            }
            FluText {
                id: nav_app_bar_pane_title
                Layout.alignment: Qt.AlignVCenter
                Layout.leftMargin: 2
                font: FluTextStyle.Body
                text: "home"
            }
        }
    }
    Item {
        anchors {
            bottom: parent.bottom
            left: d.isMinimal || d.isCompactAndPanel ? parent.left : layout_list.right
            leftMargin: d.isCompactAndPanel ? 50 : 0
            right: parent.right
            top: nav_app_bar.bottom
        }
        //        StackView{
        //            id:nav_swipe
        //            anchors.fill: parent
        //            clip: true
        //            popEnter : Transition{}
        //            popExit : Transition {
        //                NumberAnimation {
        //                    properties: "y"
        //                    from: 0
        //                    to: nav_swipe.height
        //                    duration: 167
        //                    easing.type: Easing.BezierSpline
        //                    easing.bezierCurve: [ 1, 0, 0, 0 ]
        //                }
        //            }
        //            pushEnter: Transition {
        //                NumberAnimation {
        //                    properties: "y";
        //                    from: nav_swipe.height;
        //                    to: 0
        //                    duration: 167
        //                    easing.type: Easing.BezierSpline
        //                    easing.bezierCurve: [ 0, 0, 0, 1 ]
        //                }
        //            }
        //            pushExit : Transition{}
        //            replaceEnter : Transition{}
        //            replaceExit : Transition{}
        //        }
        SwipeView {
            id: nav_swipe
            anchors.fill: parent
            clip: true
            interactive: false
            orientation: Qt.Vertical
        }
    }
    MouseArea {
        anchors.fill: parent
        visible: d.isMinimalAndPanel || d.isCompactAndPanel

        onClicked: {
            d.enableNavigationPanel = false;
        }
    }

    //鏈�宸﹁竟鐨刵av
    Rectangle {
        id: layout_list
        border.color: FluTheme.dark ? Qt.rgba(45 / 255, 45 / 255, 45 / 255, 1) : Qt.rgba(226 / 255, 230 / 255, 234 / 255, 1)
        border.width: d.isMinimal || d.isCompactAndPanel ? 1 : 0
        color: {
            if (d.isMinimal || d.isCompactAndPanel) {
                return FluTheme.dark ? Qt.rgba(61 / 255, 61 / 255, 61 / 255, 1) : Qt.rgba(243 / 255, 243 / 255, 243 / 255, 1);
            }
            if (window && window.active) {
                return FluTheme.dark ? Qt.rgba(26 / 255, 34 / 255, 41 / 255, 1) : Qt.rgba(238 / 255, 244 / 255, 249 / 255, 1);
            }
            return FluTheme.dark ? Qt.rgba(32 / 255, 32 / 255, 32 / 255, 1) : Qt.rgba(243 / 255, 243 / 255, 243 / 255, 1);
        }
        width: {
            if (d.isCompactAndNotPanel) {
                return 50;
            }
            return 200;
        }
        x: {
            if (d.displayMode !== FluNavigationView.Minimal)
                return 0;
            return d.isMinimalAndPanel ? 0 : -width;
        }

        Behavior on color  {
            ColorAnimation {
                duration: 300
            }
        }
        Behavior on width  {
            NumberAnimation {
                duration: 167
                easing.bezierCurve: [0, 0, 0, 1]
                easing.type: Easing.BezierSpline
            }
        }
        Behavior on x  {
            id: anim_layout_list_x
            NumberAnimation {
                duration: 167
                easing.bezierCurve: [0, 0, 0, 1]
                easing.type: Easing.BezierSpline
            }
        }

        anchors {
            bottom: parent.bottom
            top: parent.top
        }
        // 鏄剧ず鐨勬悳绱㈡锛燂紵
        Item {
            id: layout_header
            clip: true
            height: autoSuggestBox ? 38 : 0
            width: layout_list.width
            y: nav_app_bar.height

            Loader {
                id: loader_auto_suggest_box
                anchors.centerIn: parent
                opacity: {
                    if (d.isCompactAndNotPanel) {
                        return false;
                    }
                    return true;
                }
                sourceComponent: autoSuggestBox
                visible: opacity

                Behavior on opacity  {
                    NumberAnimation {
                        duration: 83
                    }
                }
            }
            FluIconButton {
                height: 34
                hoverColor: FluTheme.dark ? Qt.rgba(1, 1, 1, 0.03) : Qt.rgba(0, 0, 0, 0.03)
                iconSize: 15
                iconSource: {
                    if (loader_auto_suggest_box.item) {
                        return loader_auto_suggest_box.item.autoSuggestBoxReplacement;
                    }
                    return 0;
                }
                normalColor: FluTheme.dark ? Qt.rgba(0, 0, 0, 0) : Qt.rgba(0, 0, 0, 0)
                opacity: d.isCompactAndNotPanel
                pressedColor: FluTheme.dark ? Qt.rgba(1, 1, 1, 0.03) : Qt.rgba(0, 0, 0, 0.03)
                visible: opacity
                width: 38
                x: 6
                y: 2

                Behavior on opacity  {
                    NumberAnimation {
                        duration: 83
                    }
                }

                onClicked: {
                    d.enableNavigationPanel = !d.enableNavigationPanel;
                }
            }
        }
        ListView {
            id: nav_list
            clip: true
            currentIndex: -1
            highlightMoveDuration: 150
            model: d.handleItems()

            ScrollBar.vertical: FluScrollBar {
            }
            delegate: Loader {
                property var idx: index
                property var model: modelData
                property int type: 0

                sourceComponent: {
                    if (modelData instanceof FluPaneItem) {
                        return com_panel_item;
                    }
                    if (modelData instanceof FluPaneItemHeader) {
                        return com_panel_item_header;
                    }
                    if (modelData instanceof FluPaneItemSeparator) {
                        return com_panel_item_separatorr;
                    }
                    if (modelData instanceof FluPaneItemExpander) {
                        return com_panel_item_expander;
                    }
                    if (modelData instanceof FluPaneItemEmpty) {
                        return com_panel_item_empty;
                    }
                }
            }
            highlight: Item {
                clip: true

                Rectangle {
                    color: FluTheme.primaryColor.dark
                    height: 18
                    radius: 1.5
                    width: 3

                    anchors {
                        left: parent.left
                        leftMargin: 6
                        verticalCenter: parent.verticalCenter
                    }
                }
            }

            onCurrentIndexChanged: {
                if (d.enableStack) {
                    var item = model[currentIndex];
                    if (item instanceof FluPaneItem) {
                        item.tap();
                        d.stackItems.push(item);
                    }
                }
            }

            anchors {
                bottom: layout_footer.top
                left: parent.left
                right: parent.right
                top: layout_header.bottom
                topMargin: 0
            }
        }
        ListView {
            id: layout_footer
            anchors.bottom: parent.bottom
            clip: true
            currentIndex: -1
            height: childrenRect.height
            highlightMoveDuration: 150
            interactive: false
            model: {
                if (footerItems) {
                    return footerItems.children;
                }
            }
            width: layout_list.width

            delegate: Loader {
                property var idx: index
                property var model: modelData
                property int type: 1

                sourceComponent: {
                    if (modelData instanceof FluPaneItem) {
                        return com_panel_item;
                    }
                    if (modelData instanceof FluPaneItemHeader) {
                        return com_panel_item_header;
                    }
                    if (modelData instanceof FluPaneItemSeparator) {
                        return com_panel_item_separatorr;
                    }
                }
            }
            highlight: Item {
                clip: true

                Rectangle {
                    color: FluTheme.primaryColor.dark
                    height: 18
                    radius: 1.5
                    width: 3

                    anchors {
                        left: parent.left
                        leftMargin: 6
                        verticalCenter: parent.verticalCenter
                    }
                }
            }
        }
    }
    Popup {
        id: control_popup

        property var childModel

        function showPopup(pos, model) {
            control_popup.x = pos.x;
            control_popup.y = pos.y;
            control_popup.childModel = model;
            control_popup.open();
        }

        background: Rectangle {
            color: FluTheme.dark ? Qt.rgba(51 / 255, 48 / 255, 48 / 255, 1) : Qt.rgba(248 / 255, 250 / 255, 253 / 255, 1)
            height: 38 * Math.min(Math.max(list_view.count, 1), 8)
            radius: 4
            width: 160

            FluShadow {
                radius: 4
            }
            ListView {
                id: list_view
                anchors.fill: parent
                clip: true
                currentIndex: -1
                model: control_popup.childModel

                ScrollBar.vertical: FluScrollBar {
                }
                delegate: Button {
                    padding: 10
                    width: 160

                    background: Rectangle {
                        color: {
                            if (hovered) {
                                return FluTheme.dark ? Qt.rgba(63 / 255, 60 / 255, 61 / 255, 1) : Qt.rgba(237 / 255, 237 / 255, 242 / 255, 1);
                            }
                            return FluTheme.dark ? Qt.rgba(51 / 255, 48 / 255, 48 / 255, 1) : Qt.rgba(0, 0, 0, 0);
                        }
                    }
                    contentItem: FluText {
                        text: modelData.title

                        anchors {
                            verticalCenter: parent.verticalCenter
                        }
                    }

                    onClicked: {
                        if (modelData.tapFunc) {
                            modelData.tapFunc();
                        } else {
                            nav_list.currentIndex = idx;
                            layout_footer.currentIndex = -1;
                            if (d.isMinimal || d.isCompact) {
                                d.enableNavigationPanel = false;
                            }
                        }
                        control_popup.close();
                    }
                }
            }
        }
        enter: Transition {
            NumberAnimation {
                duration: 83
                from: 0
                property: "opacity"
                to: 1
            }
        }
    }
    Timer {
        id: timer_anim_x_enable
        interval: 150

        onTriggered: {
            anim_layout_list_x.enabled = true;
        }
    }
}
