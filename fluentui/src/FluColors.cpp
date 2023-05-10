#include "FluColors.h"

FluColors::FluColors(QObject *parent)
    : QObject{parent}
{
    Black("#000000");
    White("#ffffff");
    Grey10("#faf9f8");
    Grey20("#f3f2f1");
    Grey30("#edebe9");
    Grey40("#e1dfdd");
    Grey50("#d2d0ce");
    Grey60("#c8c6c4");
    Grey70("#beb9b8");
    Grey80("#b3b0ad");
    Grey90("#a19f9d");
    Grey100("#979592");
    Grey110("#8a8886");
    Grey120("#797775");
    Grey130("#605e5c");
    Grey140("#484644");
    Grey150("#3b3a39");
    Grey160("#323130");
    Grey170("#292827");
    Grey180("#252423");
    Grey190("#201f1e");
    Grey200("#1b1a19");
    Grey210("#161514");
    Grey220("#11100f");

    FluColorSet *yellow = new FluColorSet();
    yellow->darkest("#f9a825");
    yellow->darker("#fbc02d");
    yellow->dark("#fdd435");
    yellow->normal("#ffeb3b");
    yellow->light("#ffee58");
    yellow->lighter("#fff176");
    yellow->lightest("#fff59b");
    Yellow(yellow);

    FluColorSet *orange = new FluColorSet();
    orange->darkest("#993d07");
    orange->darker("#ac4408");
    orange->dark("#d1580a");
    orange->normal("#f7630c");
    orange->light("#f87a30");
    orange->lighter("#f99154");
    orange->lightest("#fac06a");
    Orange(orange);

    FluColorSet *red = new FluColorSet();
    red->darkest("#8f0a15");
    red->darker("#a20b18");
    red->dark("#b90d1c");
    red->normal("#e81123");
    red->light("#ec404f");
    red->lighter("#ee5865");
    red->lightest("#f06b76");
    Red(red);

    FluColorSet *magenta = new FluColorSet();
    magenta->darkest("#6f004f");
    magenta->darker("#a0076c");
    magenta->dark("#b50d7d");
    magenta->normal("#e3008c");
    magenta->light("#ea4da8");
    magenta->lighter("#ee6ec1");
    magenta->lightest("#f18cd5");
    Magenta(magenta);

    FluColorSet *purple = new FluColorSet();
    purple->darkest("#2c0f76");
    purple->darker("#3d0f99");
    purple->dark("#4e11ae");
    purple->normal("#68217a");
    purple->light("#7b4c9d");
    purple->lighter("#8d6ebd");
    purple->lightest("#9e8ed9");
    Purple(purple);

    FluColorSet *blue = new FluColorSet();
    blue->darkest("#004A83");
    blue->darker("#005494");
    blue->dark("#0066B4");
    blue->normal("#0078D4");
    blue->light("#268CDC");
    blue->lighter("#4CA0E0");
    blue->lightest("#60ABE4");
    Blue(blue);

    FluColorSet *teal = new FluColorSet();
    teal->darkest("#006E5B");
    teal->darker("#007C67");
    teal->dark("#00977D");
    teal->normal("#00B294");
    teal->light("#26BDA4");
    teal->lighter("#4DC9B4");
    teal->lightest("#60CFBC");
    Teal(teal);

    FluColorSet *green = new FluColorSet();
    green->darkest("#094C09");
    green->darker("#0C5D0C");
    green->dark("#0E6F0E");
    green->normal("#107C10");
    green->light("#278939");
    green->lighter("#4C9C4C");
    green->lightest("#6AAD6A");
    Green(green);
}
