"""
Our main Cog for commands used by mods.

"""

# libraries
import asyncio
from datetime import datetime, timezone
import random

# discord.py
import discord
from discord.app_commands import Group, describe
from discord.ext import commands
from discord import app_commands

# local classes
from ptn.modbot.classes.InfractionData import InfractionData

# local constants
from ptn.modbot._metadata import __version__
import ptn.modbot.constants as constants
from ptn.modbot.constants import bot, channel_botspam, channel_evidence, role_council, role_mod, get_guild

# local modules
from ptn.modbot.database.database import find_infraction, delete_single_warning, delete_all_warnings_for_user
from ptn.modbot.modules.Embeds import None
from ptn.modbot.modules.ErrorHandler import on_app_command_error



"""
A primitive global error handler for text commands.

returns: error message to user and log
"""

@bot.listen()
async def on_command_error(ctx, error):
    gif = random.choice(constants.error_gifs)
    if isinstance(error, commands.BadArgument):
        await ctx.send(f'**Bad argument!** {error}')
        print({error})
    elif isinstance(error, commands.CommandNotFound):
        await ctx.send("**Invalid command.**")
        print({error})
    elif isinstance(error, commands.MissingRequiredArgument):
        print({error})
        await ctx.send("**Sorry, that didn't work**.\n• Check you've included all required arguments."
                       "\n• If using quotation marks, check they're opened *and* closed, and are in the proper place.\n• Check quotation"
                       " marks are of the same type, i.e. all straight or matching open/close smartquotes.")
    elif isinstance(error, commands.MissingPermissions):
        print({error})
        await ctx.send('**Sorry, you\'re missing the required permission for this command.**')
    else:
        await ctx.send(gif)
        print({error})
        await ctx.send(f"Sorry, that didn't work: {error}")


"""
MODERATOR BOT COMMANDS

"""

class ModCommands(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # custom global error handler
    # attaching the handler when the cog is loaded
    # and storing the old handler
    def cog_load(self):
        tree = self.bot.tree
        self._old_tree_error = tree.on_error
        tree.on_error = on_app_command_error

    # detaching the handler when the cog is unloaded
    def cog_unload(self):
        tree = self.bot.tree
        tree.on_error = self._old_tree_error

