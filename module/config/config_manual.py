# This Python file uses the following encoding: utf-8
# @author runhey
# github https://github.com/runhey

class ConfigManual:
    """
    module.device
    """

    SCHEDULER_PRIORITY = """
        Restart
        > KekkaiUtilize > KekkaiActivation > DemonEncounter
        > AreaBoss > GoldYoukai > ExperienceYoukai > Nian > Tako > RealmRaid > RyouToppa > DailyTrifles > Exploration
        > Hunt 
        > Orochi > OrochiMoans > OrochiJudgement > Sougenbi > FallenSun > EternitySea
        > ActivityShikigami > WantedQuests
        > BondlingFairyland > EvoZone > GoryouRealm
        > TrueOrochi > RichMan
        > CollectiveMissions
        > Pets > TalismanPass > SoulsTidy > Delegation
        > Secret > WeeklyTrifles > MysteryShop > Duel > MetaDemon > FrogBoss
        """

    DEVICE_OVER_HTTP = False
    FORWARD_PORT_RANGE = (20000, 21000)
    REVERSE_SERVER_PORT = 7903

    # ASCREENCAP_FILEPATH_LOCAL = './bin/ascreencap'
    # ASCREENCAP_FILEPATH_REMOTE = '/data/local/tmp/ascreencap'

    # 'DroidCast', 'DroidCast_raw'
    DROIDCAST_VERSION = 'DroidCast'
    DROIDCAST_FILEPATH_LOCAL = './bin/droidcast/DroidCast-debug-1.2.0.apk'
    DROIDCAST_FILEPATH_REMOTE = '/data/local/tmp/DroidCast.apk'
    DROIDCAST_RAW_FILEPATH_LOCAL = './bin/droidcast/DroidCastS-release-1.1.5.apk'
    DROIDCAST_RAW_FILEPATH_REMOTE = '/data/local/tmp/DroidCastS.apk'

    MINITOUCH_FILEPATH_REMOTE = '/data/local/tmp/minitouch'

    HERMIT_FILEPATH_LOCAL = './bin/hermit/hermit.apk'


