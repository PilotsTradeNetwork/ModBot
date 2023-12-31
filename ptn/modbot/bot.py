"""
bot.py

This is where we define our bot object and setup_hook (replacement for on_ready)

Dependencies: Constants, Metadata

"""
# import libraries
import asyncio
import re

# import discord
import discord
from discord import Forbidden
from discord.ext import commands

# import constants
from ptn.modbot._metadata import __version__
from ptn.modbot.constants import channel_botspam, EMBED_COLOUR_OK, dev_channel




"""
Bot object
"""


# define bot object
class ModBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True

        super().__init__(command_prefix=commands.when_mentioned_or('🎢'), intents=intents)

    async def on_ready(self):
        try:
            # TODO: this should be moved to an on_setup hook
            print('-----')
            print(f'{bot.user.name} version: {__version__} has connected to Discord!')
            print('-----')
            global spamchannel
            spamchannel = bot.get_channel(dev_channel())
            embed = discord.Embed(
                title="🟢 MODBOT ONLINE",
                description=f"🔨<@{bot.user.id}> connected, version **{__version__}**.",
                color=EMBED_COLOUR_OK
            )
            await spamchannel.send(embed=embed)

        except Exception as e:
            print(e)

    async def on_disconnect(self):
        print('-----')
        print(f'🔌modbot has disconnected from discord server, version: {__version__}.')
        print('-----')


bot = ModBot()
