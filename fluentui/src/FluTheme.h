#ifndef FLUTHEME_H
#define FLUTHEME_H

#include <QObject>
#include <QtQml/qqml.h>
#include "FluColorSet.h"
#include "stdafx.h"

/**
 * @brief The FluTheme class
 */
class FluTheme : public QObject
{
    Q_OBJECT
    /**
     * @brief dark 改变窗口夜间样式，只读属性，可以通过darkMode切换
     */
    Q_PROPERTY(bool dark READ dark NOTIFY darkChanged)

    /**
     * @brief primaryColor 主题颜色
     */
    Q_PROPERTY_AUTO(FluColorSet*,primaryColor)

    /**
     * @brief frameless 是否是无边框窗口，只支持windows部分电脑
     */
    Q_PROPERTY_AUTO(bool,frameless);

    /**
     * @brief darkMode 夜间模式，支持System=0、Light=1、Dark=2
     */
    Q_PROPERTY_AUTO(int,darkMode);

    /**
     * @brief nativeText 本地渲染文本
     */
    Q_PROPERTY_AUTO(bool,nativeText);

    QML_NAMED_ELEMENT(FluTheme)
    QML_SINGLETON
public:
    explicit FluTheme(QObject *parent = nullptr);
    bool dark();
    Q_SIGNAL void darkChanged();
private:
    bool _dark;
    bool eventFilter(QObject *obj, QEvent *event);
    bool systemDark();
};

#endif // FLUTHEME_H
