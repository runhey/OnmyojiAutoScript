#ifndef ZH_H
#define ZH_H

#include <QObject>
#include "Lang.h"

class Zh : public Lang
{
    Q_OBJECT
public:
    explicit Zh(QObject *parent = nullptr);

signals:

};

#endif // ZH_H
