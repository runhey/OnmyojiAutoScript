#include "FluTextStyle.h"

FluTextStyle::FluTextStyle(QObject *parent)
    : QObject{parent}
{
    QFont caption;
    caption.setPixelSize(12);
    Caption(caption);

    QFont body;
    body.setPixelSize(14);
    Body(body);

    QFont bodyStrong;
    bodyStrong.setPixelSize(14);
    bodyStrong.setBold(true);
    BodyStrong(bodyStrong);

    QFont subtitle;
    subtitle.setPixelSize(20);
    subtitle.setBold(true);
    Subtitle(subtitle);

    QFont title;
    title.setPixelSize(28);
    title.setBold(true);
    Title(title);

    QFont titleLarge;
    titleLarge.setPixelSize(40);
    titleLarge.setBold(true);
    TitleLarge(titleLarge);

    QFont display;
    display.setPixelSize(68);
    display.setBold(true);
    Display(display);
}
