#include "Zh.h"

Zh::Zh(QObject *parent)
    : Lang{parent}
{
    setObjectName("Zh");
    home("首页");
    basic_input("基本输入");
    form("表单");
    surface("表面");
    popus("弹窗");
    navigation("导航");
    theming("主题");
    media("媒体");
    dark_mode("夜间模式");
    sys_dark_mode("跟随系统");
    search("查找");
    about("关于");
    settings("设置");
    locale("语言环境");
    navigation_view_display_mode("导航视图显示模式");
}
