# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

class ConfigManual:
    """
    module.device
    """

    SCHEDULER_PRIORITY = """
        Restart > SoulsTidy
        > KekkaiUtilize > KekkaiActivation > DemonEncounter
        > AreaBoss > GoldYoukai > ExperienceYoukai > Nian > Tako > RealmRaid > RyouToppa > DailyTrifles > Exploration
        > Dokan > AbyssShadows > Hunt 
        > Orochi > OrochiMoans > OrochiJudgement > Sougenbi > FallenSun > EternitySea > SixRealms
        > ActivityShikigami > WantedQuests
        > BondlingFairyland > EvoZone > GoryouRealm > HeroTest
        > TrueOrochi > RichMan
        > CollectiveMissions
        > Pets > TalismanPass > Delegation > Hyakkiyakou
        > Secret > WeeklyTrifles > MysteryShop > Duel > MetaDemon > FrogBoss > FloatParade > Quiz > KittyShop
        """

    DEVICE_OVER_HTTP = False
    FORWARD_PORT_RANGE = (20000, 21000)
    REVERSE_SERVER_PORT = 7903

    # ASCREENCAP_FILEPATH_LOCAL = './bin/ascreencap'
    # ASCREENCAP_FILEPATH_REMOTE = '/data/local/tmp/ascreencap'

    # 'DroidCast', 'DroidCast_raw'
    DROIDCAST_VERSION = 'DroidCast'
    DROIDCAST_FILEPATH_LOCAL = './bin/droidcast/DroidCast_raw-release-1.0.apk'
    DROIDCAST_FILEPATH_REMOTE = '/data/local/tmp/DroidCast_raw.apk'

    MINITOUCH_FILEPATH_REMOTE = '/data/local/tmp/minitouch'

    HERMIT_FILEPATH_LOCAL = './bin/hermit/hermit.apk'
