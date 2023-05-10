#include "AppInfo.h"
#include "lang/En.h"
#include "lang/Zh.h"
#include <QDebug>

#define STR(x) #x
#define VER_JOIN(a,b,c,d) STR(a.b.c.d)
#define VER_JOIN_(x) VER_JOIN x
#define VER_STR VER_JOIN_((VERSION))

AppInfo::AppInfo(QObject *parent)
    : QObject{parent}
{
    version(VER_STR);
    lang(new En());
}

void AppInfo::changeLang(const QString& locale){
    if(_lang){
        _lang->deleteLater();
    }
    if(locale=="Zh"){
        lang(new Zh());
    }else if(locale=="En"){
        lang(new En());
    }else {
        lang(new En());
    }

}
