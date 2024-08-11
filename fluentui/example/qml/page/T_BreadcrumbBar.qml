import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import FluentUI
import "../component"

FluScrollablePage{

    title:"BreadcurmbBar"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    Component.onCompleted: {
        var items = []
        for(var i=0;i<10;i++){
            items.push({title:"Item_"+(i+1)})
        }
        breadcrumb_1.items = items
        breadcrumb_2.items = items
    }

    FluArea{
        Layout.fillWidth: true
        height: 68
        paddings: 10
        Layout.topMargin: 20

        FluBreadcrumbBar{
            id:breadcrumb_1
            width:parent.width
            anchors.verticalCenter: parent.verticalCenter
            onClickItem:
                (model)=>{
                    showSuccess(model.title)
                }
        }
    }


    FluArea{
        Layout.fillWidth: true
        height: 100
        paddings: 10
        Layout.topMargin: 20

        ColumnLayout{
            anchors.verticalCenter: parent.verticalCenter
            width:parent.width
            spacing: 10

            FluFilledButton{
                text:"Reset sample"
                onClicked:{
                    var items = []
                    for(var i=0;i<10;i++){
                        items.push({title:"Item_"+(i+1)})
                    }
                     breadcrumb_2.items = items
                }
            }

            FluBreadcrumbBar{
                id:breadcrumb_2
                separator:">"
                spacing:8
                textSize:18
                Layout.fillWidth: true
                onClickItem:
                    (model)=>{
                        //不是点击最后一个item元素
                        if(model.index+1!==count()){
                            breadcrumb_2.remove(model.index+1,count()-model.index-1)
                        }
                        showSuccess(model.title)
                    }
            }
        }
    }

    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluBreadcrumbBar{
    width:parent.width
    separator:">"
    spacing:8
    textSize:18
    onClickItem: (model)=>{

    }
}'
    }


}
