#ifndef FLUCOLORSET_H
#define FLUCOLORSET_H

#include <QObject>
#include "stdafx.h"

/**
 * @brief The FluColorSet class
 */
class FluColorSet : public QObject
{
    Q_OBJECT
    Q_PROPERTY_AUTO(QString,darkest)
    Q_PROPERTY_AUTO(QString,darker)
    Q_PROPERTY_AUTO(QString,dark)
    Q_PROPERTY_AUTO(QString,normal)
    Q_PROPERTY_AUTO(QString,light)
    Q_PROPERTY_AUTO(QString,lighter)
    Q_PROPERTY_AUTO(QString,lightest)
public:
    explicit FluColorSet(QObject *parent = nullptr);
};

#endif // FLUCOLORSET_H
