import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import FluentUI

Item {

    property var columns : []
    property var dataSource : []
    property int pageCurrent: 1
    property int itemCount: 1000
    property int pageCount: 10
    property int itemHeight: 56
    property bool pageVisible: true
    signal requestPage(int page,int count)

    id:control
    implicitHeight: layout_table.height

    QtObject{
        id:d
        property int coumnsWidth: parent.width
    }

    MouseArea{
        anchors.fill: parent
        preventStealing: true
    }

    ListModel{
        id:model_coumns
    }

    ListModel{
        id:model_data_source
    }

    onColumnsChanged: {
        model_coumns.clear()
        model_coumns.append(columns)
        var w = 0
        for(var i=0;i<model_coumns.count;i++){
            var item = model_coumns.get(i)
            w=w+item.width
        }
        d.coumnsWidth = w
    }

    onDataSourceChanged: {
        model_data_source.clear()
        model_data_source.append(dataSource)
    }

    Flickable{
        id:layout_flickable
        height: layout_table.height
        anchors{
            top: parent.top
            left: parent.left
            right: parent.right
        }
        contentWidth: layout_table.width
        clip:true
        ScrollBar.horizontal: FluScrollBar {
        }
        Rectangle{
            anchors.fill: layout_table
            radius: 5
            color: FluTheme.dark ? Qt.rgba(39/255,39/255,39/255,1) : Qt.rgba(251/255,251/255,253/255,1)
        }
        ListView{
            id:layout_table
            height: contentHeight
            width: Math.max(layout_flickable.width,d.coumnsWidth)
            clip:true
            interactive: false

            header: FluRectangle{
                id:layout_coumns
                height: control.itemHeight
                width: parent.width
                color:FluTheme.dark ? Qt.rgba(50/255,50/255,50/255,1) : Qt.rgba(247/255,247/255,247/255,1)
                radius: [5,5,0,0]

                Row{
                    id:list_coumns
                    spacing: 0
                    anchors.fill: parent
                    Repeater{
                        model: model_coumns
                        delegate: Item{
                            height: list_coumns.height
                            width: model.width
                            FluText{
                                text:model.title
                                wrapMode: Text.WordWrap
                                anchors{
                                    verticalCenter: parent.verticalCenter
                                    left: parent.left
                                    leftMargin: 14
                                }
                                font: FluTextStyle.BodyStrong
                            }
                            FluDivider{
                                width: 1
                                height: 40
                                anchors.right: parent.right
                                anchors.verticalCenter: parent.verticalCenter
                                visible: index !== model_coumns.count-1
                            }
                        }
                    }
                }
            }

            footer: Item{
                height: pageVisible ? 50 : 0
                clip: true
                width: layout_table.width
                FluPagination{
                    id:pagination
                    height: 40
                    pageCurrent: control.pageCurrent
                    onPageCurrentChanged: control.pageCurrent = pageCurrent
                    itemCount: control.itemCount
                    pageCount: control.pageCount
                    onRequestPage:
                        (page,count)=> {
                            control.requestPage(page,count)
                        }
                    anchors{
                        top: parent.top
                        right: parent.right
                    }
                    Connections{
                        target: control
                        function onPageCurrentChanged(){
                            if (control.pageCurrent!==pagination.pageCurrent)
                            {
                                pagination.calcNewPage(control.pageCurrent)
                            }
                        }
                    }
                }
            }
            model:model_data_source
            delegate: Item{
                height: table_row.maxHeight
                width: layout_table.width
                property var model_values : getObjectValues(index)
                property var itemObject: getObject(index)
                property var listModel: model
                Row{
                    id: table_row
                    spacing: 0
                    anchors.fill: parent
                    property int maxHeight: itemHeight
                    Repeater{
                        model: model_values
                        delegate:Item{
                            height: table_row.maxHeight
                            width: modelData.width
                            Loader{
                                property var model : modelData
                                property var dataModel : listModel
                                property var dataObject : itemObject
                                anchors.fill: parent
                                sourceComponent: {
                                    if(model.itemData instanceof Component){
                                        return model.itemData
                                    }
                                    return com_text
                                }
                                onHeightChanged:
                                {
                                    table_row.maxHeight = Math.max(table_row.maxHeight,height,itemHeight)
                                    parent.height = table_row.maxHeight
                                    table_row.parent.height = table_row.maxHeight
                                }
                            }
                        }
                    }
                }
                FluDivider{
                    width: parent.width
                    height: 1
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                }
            }
        }
    }


    Component{
        id:com_text
        Item{
            FluCopyableText{
                id:table_value
                text:String(model.itemData)
                width: Math.min(parent.width - 14,implicitWidth)
                wrapMode: Text.WordWrap
                onImplicitHeightChanged: parent.parent.parent.height = Math.max(implicitHeight + 20,itemHeight)
                anchors{
                    verticalCenter: parent.verticalCenter
                    left: parent.left
                    leftMargin: 14
                }
                MouseArea{
                    id:item_mouse
                    hoverEnabled: true
                    anchors.fill: parent
                    cursorShape: Qt.IBeamCursor
                    acceptedButtons: Qt.NoButton
                }
                FluTooltip{
                    visible: item_mouse.containsMouse
                    text:parent.text
                    delay: 1000
                }
            }
        }
    }

    function getObject(index){
        return model_data_source.get(index)
    }

    function getObjectValues(index) {
        var obj = model_data_source.get(index)
        if(!obj)
            return
        var data = []
        for(var i=0;i<model_coumns.count;i++){
            var item = model_coumns.get(i)
            data.push({itemData:obj[item.dataIndex],width:item.width})
        }
        return data;
    }

}
