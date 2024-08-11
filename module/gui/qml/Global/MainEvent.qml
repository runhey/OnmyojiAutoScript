pragma Singleton

import QtQuick
import QtQuick.Controls
import FluentUI


QtObject {
    id: mainEvent
    enum RunStatus {
        Error,
        Run,
        Free, //空闲
        Empty, //不显示
        Init  //初始化
    }

    // 界面的自定义设置
    property var settings: {""}
    property bool settingInit: true  // 表示这个时候是初始化的，初始化后变为false
    property int displayMode : FluNavigationView.Compact
    property int darkMode: FluDarkMode.System
    property QtObject primaryColor: FluColors.Orange
    property bool nativeText: true
    property string language: ""
    property string dpiStrategy: ""
    property string branch: ""

    property int runStatus: MainEvent.RunStatus.Empty
    property string menuTitle: ""
    property bool addOpen: false
    property string scriptName: ""  // 是设置脚本的名字

    //切换语言中文是"zh_CN" 英文是"en_US"
    function switchLocale(locale) {

    }

    Component.onCompleted:{
        var set = JSON.parse(setting.read())
        mainEvent.settings = set
        if(mainEvent.settings === ""){
            mainEvent.settings = {
                "displayMode": 1,
                "darkMode": 2,
                "primaryColor": "Orange",
                "nativeText": true,
                "language": "简体中文",
                "dpiStrategy": ""}
        }

        mainEvent.displayMode = set["displayMode"]
        mainEvent.darkMode = set["darkMode"]
        mainEvent.nativeText = set["nativeText"]
        mainEvent.language = set["language"]
        mainEvent.dpiStrategy = set["dpiStrategy"]
        if ('branch' in set){
            mainEvent.branch = set['branch']
        }else{
            mainEvent.branch = "master"
            mainEvent.settings["branch"] = mainEvent.branch
            setting.update(JSON.stringify(mainEvent.settings, null, "  "))
        }

        var primary_color = set["primaryColor"]
        if(primary_color === "Yellow"){mainEvent.primaryColor = FluColors.Yellow}
        else if(primary_color === "Orange"){mainEvent.primaryColor = FluColors.Orange}
        else if(primary_color === "Red"){mainEvent.primaryColor = FluColors.Red}
        else if(primary_color === "Magenta"){mainEvent.primaryColor = FluColors.Magenta}
        else if(primary_color === "Purple"){mainEvent.primaryColor = FluColors.Purple}
        else if(primary_color === "Blue"){mainEvent.primaryColor = FluColors.Blue}
        else if(primary_color === "Teal"){mainEvent.primaryColor = FluColors.Teal}
        else if(primary_color === "Green"){mainEvent.primaryColor = FluColors.Green}

        settingInit = false
    }
    onDisplayModeChanged: {

        if(mainEvent.settings === ""){
            console.debug('display mode and is none')
        }

        mainEvent.settings["displayMode"] = mainEvent.displayMode
        if(settingInit){
            return
        }
        setting.update(JSON.stringify(mainEvent.settings, null, "  "))
    }
    onDarkModeChanged: {

        if(mainEvent.settings === ""){
            console.debug('darkMode and is none')
        }
        FluTheme.darkMode = mainEvent.darkMode
        mainEvent.settings["darkMode"] = FluTheme.darkMode
        if(settingInit){
            return
        }
        setting.update(JSON.stringify(mainEvent.settings, null, "  "))
    }
    onPrimaryColorChanged: {
        if(mainEvent.settings === ""){
            console.debug('primaryColor and is none')
            var set = JSON.parse(setting.read())
            mainEvent.settings = set
            return
        }

        FluTheme.primaryColor = mainEvent.primaryColor
        var primary_color = "Yellow"
        if(FluTheme.primaryColor === FluColors.Yellow){primary_color="Yellow"}
        else if(FluTheme.primaryColor === FluColors.Orange){primary_color="Orange"}
        else if(FluTheme.primaryColor === FluColors.Red){primary_color="Red"}
        else if(FluTheme.primaryColor === FluColors.Magenta){primary_color="Magenta"}
        else if(FluTheme.primaryColor === FluColors.Purple){primary_color="Purple"}
        else if(FluTheme.primaryColor === FluColors.Blue){primary_color="Blue"}
        else if(FluTheme.primaryColor === FluColors.Teal){primary_color="Teal"}
        else if(FluTheme.primaryColor === FluColors.Green){primary_color="Green"}
        mainEvent.settings["primaryColor"] = primary_color
        if(settingInit){
            return
        }
        setting.update(JSON.stringify(mainEvent.settings, null, "  "))
    }
    onNativeTextChanged: {

        if(mainEvent.settings === ""){
            console.debug('nativeText and is none')
        }

        FluTheme.nativeText = mainEvent.nativeText
        mainEvent.settings["nativeText"] = FluTheme.nativeText
        if(settingInit){
            return
        }
        setting.update(JSON.stringify(mainEvent.settings, null, "  "))
    }
    onLanguageChanged: {
        if(mainEvent.settings === ""){
            console.debug('language and is none')
        }

        mainEvent.settings["language"] = mainEvent.language
        translator.set_language(mainEvent.language)
        if(settingInit){
            return
        }
        setting.update(JSON.stringify(mainEvent.settings, null, "  "))

    }
    onDpiStrategyChanged: {
        if(mainEvent.settings === ""){
            console.debug('dpiStrategy and is none')
        }
        mainEvent.settings["dpiStrategy"] = mainEvent.dpiStrategy
        dpi.set_dpi_scale(mainEvent.dpiStrategy)
        if(settingInit){
            return
        }
        setting.update(JSON.stringify(mainEvent.settings, null, "  "))
    }
}
