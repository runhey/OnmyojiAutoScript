from tasks.GameUi.assets import GameUiAssets as G
from tasks.GameUi.page import Page, page_guild
from tasks.GuildShardDonation.assets import GuildShardDonationAssets as D


page_guild_shard_donation = Page(D.I_PRAYER_PAGE)
page_guild_shard_donation.link(button=G.I_BACK_Y, destination=page_guild)
page_guild.link(button=D.I_PRAYER_ENTRY, destination=page_guild_shard_donation)
