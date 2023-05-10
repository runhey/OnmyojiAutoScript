import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import FluentUI

Item {
    id: control
    signal requestPage(int page,int count)
    property string previousText: "<上一页"
    property string nextText: "下一页>"
    property int pageCurrent: 0
    property int itemCount: 0
    property int pageCount: itemCount>0?Math.ceil(itemCount/__itemPerPage):0
    property int __itemPerPage: 10
    property int pageButtonCount: 5
    property int __pageButtonHalf: Math.floor(pageButtonCount/2)+1


    implicitHeight: 40
    implicitWidth: content.width

    Row{
        id: content
        height: control.height
        spacing: 25
        padding: 10


        FluToggleButton{
            visible: control.pageCount>1
            disabled: control.pageCurrent<=1
            text:control.previousText
            onClicked: {
                control.calcNewPage(control.pageCurrent-1);
            }
        }

        Row{
            spacing: 5
            FluToggleButton{
                property int pageNumber:1
                visible: control.pageCount>0
                enabled: control.pageCurrent>1
                selected: pageNumber === control.pageCurrent
                text:String(pageNumber)
                onClicked: {
                    control.calcNewPage(pageNumber);
                }
            }
            FluText{
                visible: (control.pageCount>control.pageButtonCount&&
                          control.pageCurrent>control.__pageButtonHalf)
                text: "..."
            }
            Repeater{
                id: button_repeator
                model: (control.pageCount<2)?0:(control.pageCount>=control.pageButtonCount)?(control.pageButtonCount-2):(control.pageCount-2)
                delegate:FluToggleButton{
                    property int  pageNumber: {
                        return (control.pageCurrent<=control.__pageButtonHalf)
                                ?(2+index)
                                :(control.pageCount-control.pageCurrent<=control.pageButtonCount-control.__pageButtonHalf)
                                  ?(control.pageCount-button_repeator.count+index)
                                  :(control.pageCurrent+2+index-control.__pageButtonHalf)
                    }
                    text:String(pageNumber)
                    selected: pageNumber === control.pageCurrent
                    onClicked: {
                        control.calcNewPage(pageNumber);
                    }
                }
            }
            FluText{
                visible: (control.pageCount>control.pageButtonCount&&
                          control.pageCount-control.pageCurrent>control.pageButtonCount-control.__pageButtonHalf)
                text: "..."
            }
            FluToggleButton{
                property int pageNumber:control.pageCount
                visible: control.pageCount>1
                selected: pageNumber === control.pageCurrent
                text:String(pageNumber)
                onClicked: {
                    control.calcNewPage(pageNumber);
                }
            }
        }
        FluToggleButton{
            visible: control.pageCount>1
            disabled: control.pageCurrent>=control.pageCount
            text:control.nextText
            onClicked: {
                control.calcNewPage(control.pageCurrent+1);
            }
        }
    }

    function calcNewPage(page)
    {
        if(!page)
            return
        let page_num=Number(page)
        if(page_num<1||page_num>control.pageCount||page_num===control.pageCurrent)
            return
        control.pageCurrent=page_num
        control.requestPage(page_num,control.__itemPerPage)
    }


}
