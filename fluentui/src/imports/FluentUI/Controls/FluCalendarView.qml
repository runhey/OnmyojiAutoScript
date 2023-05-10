import QtQuick
import QtQuick.Controls
import FluentUI

Item {

    enum DisplayMode {
        Month,
        Year,
        Decade
    }

    property int displayMode: FluCalendarView.Month
    property var date: new Date()
    property var currentDate : new Date()
    property var toDay: new Date()
    signal dateClicked(var date)

    id:control
    width: 280
    height: 325

    Component.onCompleted: {
        updateMouth(date)
    }

    Component{
        id:com_week
        Item{
            height: 40
            width: 40
            FluText{
                text:name
                anchors.centerIn: parent
            }
        }
    }

    Component{
        id:com_year
        Button{
            id:item_control
            property bool isYear: control.toDay.getFullYear() === date.getFullYear()
            height: 70
            width: 70
            onClicked:{
                control.date = date
                displayMode = FluCalendarView.Year
                updateYear(date)
            }
            background: Item{
                Rectangle{
                    width: 60
                    height: 60
                    radius: 4
                    anchors.centerIn: parent
                    color:{
                        if(FluTheme.dark){
                            if(item_control.hovered){
                                return Qt.rgba(1,1,1,0.05)
                            }
                            return Qt.rgba(0,0,0,0)
                        }else{
                            if(item_control.hovered){
                                return Qt.rgba(0,0,0,0.05)
                            }
                            return Qt.rgba(0,0,0,0)
                        }
                    }
                }
                Rectangle{
                    id:backgound_selected
                    anchors.centerIn: parent
                    width: 50
                    height: 50
                    radius: 25
                    visible: isYear
                    color: FluTheme.primaryColor.dark
                }
                FluText{
                    text:date.getFullYear()
                    anchors.centerIn: parent
                    color: {
                        if(isYear){
                            return "#FFFFFF"
                        }
                        if(isDecade){
                            return FluTheme.dark ? "#FFFFFF" : "#1A1A1A"
                        }
                        return Qt.rgba(150/255,150/255,150/255,1)
                    }
                }
            }
            contentItem: Item{}
        }
    }

    Component{
        id:com_month
        Button{
            id:item_control
            property bool isYear: control.date.getFullYear() === date.getFullYear()
            property bool isMonth: control.toDay.getFullYear() === date.getFullYear() && control.toDay.getMonth() === date.getMonth()
            height: 70
            width: 70
            onClicked:{
                control.date = date
                displayMode = FluCalendarView.Month
                updateMouth(date)
            }
            background: Item{
                Rectangle{
                    width: 60
                    height: 60
                    radius: 4
                    anchors.centerIn: parent
                    color:{
                        if(FluTheme.dark){
                            if(item_control.hovered){
                                return Qt.rgba(1,1,1,0.05)
                            }
                            return Qt.rgba(0,0,0,0)
                        }else{
                            if(item_control.hovered){
                                return Qt.rgba(0,0,0,0.05)
                            }
                            return Qt.rgba(0,0,0,0)
                        }
                    }
                }
                Rectangle{
                    id:backgound_selected
                    anchors.centerIn: parent
                    width: 50
                    height: 50
                    radius: 25
                    visible: isMonth
                    color: FluTheme.primaryColor.dark
                }
                FluText{
                    text:(date.getMonth()+1)+"月"
                    anchors.centerIn: parent
                    color: {
                        if(isMonth){
                            return "#FFFFFF"
                        }
                        if(isYear){
                            return FluTheme.dark ? "#FFFFFF" : "#1A1A1A"
                        }
                        return Qt.rgba(150/255,150/255,150/255,1)
                    }
                }
            }
            contentItem: Item{}
        }
    }


    Component{
        id:com_day
        Button{
            id:item_control
            property bool isMonth: control.date.getMonth() === date.getMonth()
            property bool isDay: control.currentDate.getFullYear() === date.getFullYear() && control.currentDate.getMonth() === date.getMonth() && control.currentDate.getDate() === date.getDate()
            property bool isToDay: control.toDay.getFullYear() === date.getFullYear() && control.toDay.getMonth() === date.getMonth() && control.toDay.getDate() === date.getDate()
            height: 40
            width: 40
            onClicked: {
                currentDate = date
                control.dateClicked(date)
            }
            background: Item{
                Rectangle{
                    width: 36
                    height: 36
                    radius: 4
                    anchors.centerIn: parent
                    color:{
                        if(FluTheme.dark){
                            if(item_control.hovered){
                                return Qt.rgba(1,1,1,0.05)
                            }
                            return Qt.rgba(0,0,0,0)
                        }else{
                            if(item_control.hovered){
                                return Qt.rgba(0,0,0,0.05)
                            }
                            return Qt.rgba(0,0,0,0)
                        }
                    }
                }

                Rectangle{
                    id:backgound_today
                    anchors.centerIn: parent
                    width: 36
                    height: 36
                    radius: 18
                    color:"#00000000"
                    visible: isDay
                    border.color: FluTheme.primaryColor.dark
                    border.width: 1
                }

                Rectangle{
                    id:backgound_selected
                    anchors.centerIn: parent
                    width: 30
                    height: 30
                    radius: 15
                    visible: isToDay
                    color: FluTheme.primaryColor.dark
                }

                FluText{
                    text:date.getDate()
                    anchors.centerIn: parent
                    color: {
                        if(isToDay){
                            return "#FFFFFF"
                        }
                        if(isMonth){
                            return FluTheme.dark ? "#FFFFFF" : "#1A1A1A"
                        }
                        return Qt.rgba(150/255,150/255,150/255,1)
                    }
                }
            }
            contentItem: Item{}
        }
    }

    FluArea{
        anchors.fill: parent
        radius: 5

        FluShadow{
            radius: 5
        }

        Rectangle{
            id:layout_divider
            height: 1
            width: parent.width
            color: FluTheme.dark ? Qt.rgba(45/255,45/255,45/255,1) : Qt.rgba(226/255,229/255,234/255,1)
            anchors{
                top: parent.top
                topMargin: 44
            }
        }

        Item{
            id:layout_top
            anchors{
                left: parent.left
                right: parent.right
                top: parent.top
                bottom: layout_divider.top
            }

            FluTextButton{
                id:title
                leftPadding: 0
                rightPadding: 0
                anchors{
                    verticalCenter: parent.verticalCenter
                    left: parent.left
                    leftMargin: 14
                }
                disabled: displayMode === FluCalendarView.Decade
                onClicked:{
                    if(displayMode === FluCalendarView.Month){
                        displayMode = FluCalendarView.Year
                        updateYear(date)
                    }else if(displayMode === FluCalendarView.Year){
                        displayMode = FluCalendarView.Decade
                        updateDecade(date)
                    }
                }
            }

            FluIconButton{
                id:icon_up
                iconSource: FluentIcons.CaretUpSolid8
                iconSize: 10
                anchors{
                    verticalCenter: parent.verticalCenter
                    right: icon_down.left
                    rightMargin: 14
                }
                onClicked: {
                    var year = date.getFullYear()
                    var month = date.getMonth()
                    if(displayMode === FluCalendarView.Month){
                        var lastMonthYear = year;
                        var lastMonthMonth = month - 1
                        if (month === 0) {
                            lastMonthYear = year - 1
                            lastMonthMonth = 11
                        }
                        date = new Date(lastMonthYear,lastMonthMonth,1)
                        updateMouth(date)
                    }else if(displayMode === FluCalendarView.Year){
                        date = new Date(year-1,month,1)
                        updateYear(date)
                    }else if(displayMode === FluCalendarView.Decade){
                        date = new Date(Math.floor(year / 10) * 10-10,month,1)
                        updateDecade(date)
                    }
                }
            }

            FluIconButton{
                id:icon_down
                iconSource: FluentIcons.CaretDownSolid8
                iconSize: 10
                anchors{
                    verticalCenter: parent.verticalCenter
                    right: parent.right
                    rightMargin: 8
                }
                onClicked: {
                    var year = date.getFullYear()
                    var month = date.getMonth()
                    if(displayMode === FluCalendarView.Month){
                        var nextMonthYear = year
                        var nextMonth = month + 1
                        if (month === 11) {
                            nextMonthYear = year + 1
                            nextMonth = 0
                        }
                        date = new Date(nextMonthYear,nextMonth,1)
                        updateMouth(date)
                    }else if(displayMode === FluCalendarView.Year){
                        date = new Date(year+1,month,1)
                        updateYear(date)
                    }else if(displayMode === FluCalendarView.Decade){
                        date = new Date(Math.floor(year / 10) * 10+10,month,1)
                        updateDecade(date)
                    }
                }
            }
        }

        ListModel {
            id:list_model
        }

        Item{
            id:layout_bottom
            anchors{
                left: parent.left
                right: parent.right
                top: layout_divider.bottom
                bottom: parent.bottom
            }

            GridView{
                model: list_model
                anchors.fill: parent
                cellHeight: displayMode === FluCalendarView.Month ? 40 : 70
                cellWidth: displayMode === FluCalendarView.Month ? 40 : 70
                clip: true
                boundsBehavior:Flickable.StopAtBounds
                delegate: Loader{
                    property var modelData : model
                    property var name : model.name
                    property var date : model.date
                    property var isDecade: {
                        return model.isDecade
                    }
                    sourceComponent: {
                        if(model.type === 0){
                            return com_week
                        }
                        if(model.type === 1){
                            return com_day
                        }
                        if(model.type === 2){
                            return com_month
                        }
                        if(model.type === 3){
                            return com_year
                        }
                        return com_day
                    }
                }
            }
        }
    }

    function createItemWeek(name){
        return {type:0,date:new Date(),name:name,isDecade:false}
    }

    function createItemDay(date){
        return {type:1,date:date,name:"",isDecade:false}
    }

    function createItemMonth(date){
        return {type:2,date:date,name:"",isDecade:false}
    }

    function createItemYear(date,isDecade){
        return {type:3,date:date,name:"",isDecade:isDecade}
    }

    function updateDecade(date){
        list_model.clear()
        var year = date.getFullYear()
        const decadeStart = Math.floor(year / 10) * 10;
        for(var i = decadeStart ; i< decadeStart+10 ; i++){
            list_model.append(createItemYear(new Date(i,0,1),true));
        }
        for(var j =  decadeStart+10 ; j< decadeStart+16 ; j++){
            list_model.append(createItemYear(new Date(j,0,1),false));
        }
        title.text = decadeStart+"-"+(decadeStart+10)
    }

    function updateYear(date){
        list_model.clear()
        var year = date.getFullYear()
        for(var i = 0 ; i< 12 ; i++){
            list_model.append(createItemMonth(new Date(year,i)));
        }
        for(var j = 0 ; j< 4 ; j++){
            list_model.append(createItemMonth(new Date(year+1,j)));
        }
        title.text = year+"年"
    }

    function updateMouth(date){
        list_model.clear()
        list_model.append([createItemWeek("一"),createItemWeek("二"),createItemWeek("三"),createItemWeek("四"),createItemWeek("五"),createItemWeek("六"),createItemWeek("日")])
        var year = date.getFullYear()
        var month = date.getMonth()
        var day =  date.getDate()
        var firstDayOfMonth = new Date(year, month, 1)
        var dayOfWeek = firstDayOfMonth.getDay()
        var headerSize = (dayOfWeek===0?7:dayOfWeek)-1
        if(headerSize!==0){
            var lastMonthYear = year;
            var lastMonthMonth = month - 1
            if (month === 0) {
                lastMonthYear = year - 1
                lastMonthMonth = 11
            }
            var lastMonthDays = new Date(lastMonthYear, lastMonthMonth+1, 0).getDate()
            for (var i = headerSize-1; i >= 0; i--) {
                list_model.append(createItemDay(new Date(lastMonthYear, lastMonthMonth,lastMonthDays-i)))
            }
        }
        const lastDayOfMonth = new Date(year, month+1, 0).getDate()
        for (let day = 1; day <= lastDayOfMonth; day++) {
            list_model.append(createItemDay(new Date(year, month,day)))
        }
        var footerSize = 49-list_model.count
        var nextMonthYear = year
        var nextMonth = month + 1
        if (month === 11) {
            nextMonthYear = year + 1
            nextMonth = 0
        }
        const nextDayOfMonth = new Date(nextMonthYear, nextMonth+1, 0).getDate()
        for (let j = 1; j <= footerSize; j++) {
            list_model.append(createItemDay(new Date(nextMonthYear, nextMonth,j)))
        }
        title.text = year+"年"+(month+1)+"月"
    }


}
