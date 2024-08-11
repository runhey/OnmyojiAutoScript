# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey
from enum import Enum

from module.atom.image import RuleImage

from tasks.KekkaiUtilize.assets import KekkaiUtilizeAssets as KUA

class CardClass(str, Enum):

    UNKNOWN = 'unknown'  # 未知

    TAIKO6 = 'taiko_6'  # 太鼓
    TAIKO5 = 'taiko_5'
    TAIKO4 = 'taiko_4'
    TAIKO3 = 'taiko_3'
    TAIKO2 = 'taiko_2'
    TAIKO1 = 'taiko_1'
    TAIKO = 'taiko'

    FISH6 = 'fish_6'  # 斗鱼
    FISH5 = 'fish_5'
    FISH4 = 'fish_4'
    FISH3 = 'fish_3'
    FISH2 = 'fish_2'
    FISH1 = 'fish_1'
    FISH = 'fish'

    ROOM6 = 'room_6'  # 室内伞
    ROOM5 = 'room_5'
    ROOM4 = 'room_4'
    ROOM3 = 'room_3'
    ROOM2 = 'room_2'
    ROOM1 = 'room_1'
    ROOM = 'room'

    MOON6 = 'moon_6'  # 太阴
    MOON5 = 'moon_5'
    MOON4 = 'moon_4'
    MOON3 = 'moon_3'
    MOON2 = 'moon_2'
    MOON1 = 'moon_1'
    MOON = 'moon'

    OBOROGURUMA6 = 'oboroguruma_6'  # 胧车
    OBOROGURUMA5 = 'oboroguruma_5'
    OBOROGURUMA4 = 'oboroguruma_4'

    # 其他的太多了 统称为一个family
    # Onibiyaki 鬼火烧
    ONIBIYAKI_FAMILY = 'onibiyaki_family'
    # Gourd Wine 葫芦酒
    GOURD_WINE_FAMILY = 'gourd_wine_family'
    # Frog Chowder 口水蛙
    FROG_CHOWDER_FAMILY = 'frog_chowder_family'
    # Moubaa Soup 孟婆汤
    MOUBAA_SOUP_FAMILY = 'moubaa_soup_family'
    # Mein Mein Ice 绵绵冰
    MEIN_MEIN_ICE_FAMILY = 'mein_mein_ice_family'
    # Town Lute 阎琵琶
    TOWN_LUTE_FAMILY = 'town_lute_family'
    # Demon-fusing Lyre 炼妖琴
    DEMON_FUSING_LYRE_FAMILY = 'demon_fusing_lyre_family'
    # Thousand Year Flute 千年笛
    THOUSAND_YEAR_FLUTE_FAMILY = 'thousand_year_flute_family'
    # Kagura Suzu 神乐铃
    KAGURA_SUZU_FAMILY = 'kagura_suzu_family'
    # Heavenly Thunder Drum 天雷鼓
    HEAVENLY_THUNDER_DRUM_FAMILY = 'heavenly_thunder_drum_family'



def target_to_card_class(target: RuleImage) -> CardClass:
    """
    从匹配到的一张图片中获取卡片的类别
    !!! 这个取绝于 assets.py 中的 assets 所以请不要修改
    :param target:
    :return:
    """
    match = {KUA.I_U_TAIKO_6: CardClass.TAIKO6,
             KUA.I_U_TAIKO_5: CardClass.TAIKO5,
             KUA.I_U_TAIKO_4: CardClass.TAIKO4,
             KUA.I_U_TAIKO_3: CardClass.TAIKO3,
             KUA.I_U_FISH_6: CardClass.FISH6,
             KUA.I_U_FISH_5: CardClass.FISH5,
             KUA.I_U_FISH_4: CardClass.FISH4,
             KUA.I_U_FISH_3: CardClass.FISH3,
             KUA.I_U_MOON_6: CardClass.MOON6,
             KUA.I_U_MOON_5: CardClass.MOON5,
             KUA.I_U_MOON_4: CardClass.MOON4,
             KUA.I_U_MOON_3: CardClass.MOON3,
             KUA.I_U_MOON_2: CardClass.MOON2,}
    try:
        return match[target]
    except KeyError:
        return CardClass.UNKNOWN
