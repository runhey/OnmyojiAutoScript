import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import QtQuick.Window
import FluentUI
import "../component"

FluScrollablePage{

    title:"FlipView"
    leftPadding:10
    rightPadding:10
    bottomPadding:20
    spacing: 0

    FluArea{
        Layout.fillWidth: true
        height: 340
        paddings: 10
        Layout.topMargin: 20
        ColumnLayout{
            anchors.verticalCenter: parent.verticalCenter
            FluText{
                text:"水平方向的FlipView"
            }
            FluFlipView{
                Image{
                    source: "qrc:/example/res/image/banner_1.jpg"
                    asynchronous: true
                    fillMode:Image.PreserveAspectCrop
                }
                Image{
                    source: "qrc:/example/res/image/banner_2.jpg"
                    asynchronous: true
                    fillMode:Image.PreserveAspectCrop
                }
                Image{
                    source: "qrc:/example/res/image/banner_3.jpg"
                    asynchronous: true
                    fillMode:Image.PreserveAspectCrop
                }
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluFlipView{
    Image{
        source: "qrc:/example/res/image/banner_1.jpg"
        asynchronous: true
        fillMode:Image.PreserveAspectCrop
    }
    Image{
        source: "qrc:/example/res/image/banner_1.jpg"
        asynchronous: true
        fillMode:Image.PreserveAspectCrop
    }
    Image{
        source: "qrc:/example/res/image/banner_1.jpg"
        asynchronous: true
        fillMode:Image.PreserveAspectCrop
    }
}
'
    }

    FluArea{
        Layout.fillWidth: true
        height: 340
        paddings: 10
        Layout.topMargin: 20
        ColumnLayout{
            anchors.verticalCenter: parent.verticalCenter
            FluText{
                text:"垂直方向的FlipView"
            }
            FluFlipView{
                vertical:true
                Image{
                    source: "qrc:/example/res/image/banner_1.jpg"
                    asynchronous: true
                    sourceSize: Qt.size(400,300)
                    fillMode:Image.PreserveAspectCrop
                }
                Image{
                    source: "qrc:/example/res/image/banner_2.jpg"
                    asynchronous: true
                    fillMode:Image.PreserveAspectCrop
                }
                Image{
                    source: "qrc:/example/res/image/banner_3.jpg"
                    asynchronous: true
                    fillMode:Image.PreserveAspectCrop
                }
            }
        }
    }
    CodeExpander{
        Layout.fillWidth: true
        Layout.topMargin: -1
        code:'FluFlipView{
    vertical:true
    Image{
        source: "qrc:/example/res/image/banner_1.jpg"
        asynchronous: true
        fillMode:Image.PreserveAspectCrop
    }
    Image{
        source: "qrc:/example/res/image/banner_1.jpg"
        asynchronous: true
        fillMode:Image.PreserveAspectCrop
    }
    Image{
        source: "qrc:/example/res/image/banner_1.jpg"
        asynchronous: true
        fillMode:Image.PreserveAspectCrop
    }
}
'
    }
}
