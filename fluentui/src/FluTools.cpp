#include "FluTools.h"
#include <QGuiApplication>
#include <QClipboard>
#include <QUuid>

FluTools::FluTools(QObject *parent)
    : QObject{parent}
{

}

void FluTools::clipText(const QString& text){
    QGuiApplication::clipboard()->setText(text);
}

QString FluTools::uuid(){
    return QUuid::createUuid().toString();
}
