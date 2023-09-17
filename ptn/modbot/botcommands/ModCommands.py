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
from ptn.modbot.constants import bot, channel_botspam, channel_evidence, channel_botdev, role_council, role_mod, get_guild, infraction_color_mapping

# local modules
from ptn.modbot.database.database import find_infraction_by_user, find_infraction_by_dbid, delete_single_warning, delete_all_warnings_for_user
# from ptn.modbot.modules.Embeds import None
from ptn.modbot.modules.ErrorHandler import on_app_command_error, GenericError, on_generic_error
from ptn.modbot.modules.Helpers import check_roles



"""
A primitive global error handler for text commands.

returns: error message to user and log
"""

@bot.listen()
async def on_command_error(ctx, error):
    print(error)
    if isinstance(error, commands.BadArgument):
        message=f'Bad argument: {error}'

    elif isinstance(error, commands.CommandNotFound):
        message=f"Sorry, were you talking to me? I don't know that command."

    elif isinstance(error, commands.MissingRequiredArgument):
        message=f"Sorry, that didn't work.\n• Check you've included all required arguments." \
                 "\n• If using quotation marks, check they're opened *and* closed, and are in the proper place.\n• Check quotation" \
                 " marks are of the same type, i.e. all straight or matching open/close smartquotes."

    elif isinstance(error, commands.MissingPermissions):
        message='Sorry, you\'re missing the required permission for this command.'

    elif isinstance(error, commands.MissingAnyRole):
        message=f'You require one of the following roles to use this command:\n<@&{role_council()}> • <@&{role_mod()}>'

    else:
        message=f'Sorry, that didn\'t work: {error}'

    embed = discord.Embed(description=f"❌ {message}", color=constants.EMBED_COLOUR_ERROR)
    await ctx.send(embed=embed)


"""
CONTEXT COMMANDS
Cannot be placed in a Cog
Uses @bot.tree instead of @command.tree
"""
@bot.tree.context_menu(name="View Infractions")
@check_roles(constants.any_elevated_role)
async def context_view_infractions(interaction:  discord.Interaction, member: discord.Member):
    print(f"context_view_infractions called by {interaction.user.display_name} for {member.display_name}")

    try: # try/except block to catch and handle errors

        infractions = await find_infraction_by_user(member.id) # query the infractions db for target user
        if not infractions: # nothing found, return message
            embed = discord.Embed(
                description=f"✅ No infractions found for <@{member.id}>",
                color=constants.EMBED_COLOUR_OK
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
        else:
            embeds = [] # create an empty list to hold our embeds
            # alternatively we might send each warning individually with a delete button
            for index, infraction in enumerate(infractions, start=1):
                color = infraction_color_mapping.get(index, discord.Color.red()) # colours to use for successive embeds

                # create an embed with all the particulars
                # we'll need to retrieve the title of the rule from the rules db
                # or we could store the title along with the rule number
                # or we could pickle the entire rule object into the infractions db entry so that it reflects the state of the rule at the time of the warning
                embed = discord.Embed(
                    title=f"Infraction #{index} | Rule - Title | warning moderator",
                    description=infraction.warning_reason, # also want hammertime of the warning time
                    color=color
                )

            await interaction.response.send_message(embed=embeds, ephemeral=True)

    except Exception as e: # invoke our custom error handler
        try:
            raise GenericError(e)
        except Exception as e:
            await on_generic_error(interaction, e)


"""
MODERATOR BOT COMMANDS

"""

# define the Cog we'll use for our mod commands
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


    # processed when the bot achieves "ready" state, i.e. connected to Discord. Note this can fire several times during connection
    @commands.Cog.listener()
    async def on_ready(self):
        try:
            # TODO: this should be moved to an on_setup hook
            print(f'{bot.user.name} version: {__version__} has connected to Discord!')
            devchannel = bot.get_channel(channel_botdev())
            embed = discord.Embed(title="🟢 MODBOT ONLINE", description=f"🔨<@{bot.user.id}> connected, version **{__version__}**.", color=constants.EMBED_COLOUR_OK)
            await devchannel.send(embed=embed)
        except Exception as e:
            print(e)


    # processed on disconnect
    @commands.Cog.listener()
    async def on_disconnect(self):
        print(f'🔌ModBot has disconnected from discord server, version: {__version__}.')


    """
    ADMIN COMMANDS
    """


    # ping command to check if the bot is responding
    @commands.command(name='ping', aliases=['hello', 'ehlo', 'helo'], help='Use to check if modbot is online and responding.')
    @commands.has_any_role(*constants.any_elevated_role)
    async def ping(self, ctx):
        print(f"{ctx.author} used PING in {ctx.channel.name}")
        embed = discord.Embed(title="🟢 MODBOT ONLINE", description=f"🔨<@{bot.user.id}> connected, version **{__version__}**.", color=constants.EMBED_COLOUR_OK)
        await ctx.send(embed=embed)


    # command to sync interactions - must be done whenever the bot has appcommands added/removed
    @commands.command(name='sync', help='Synchronise modbot interactions with server')
    @commands.has_any_role(*constants.any_elevated_role)
    async def sync(self, ctx):
        print(f"Interaction sync called from {ctx.author.display_name}")
        async with ctx.typing():
            try:
                bot.tree.copy_global_to(guild=constants.guild_obj)
                await bot.tree.sync(guild=constants.guild_obj)
                print("Synchronised bot tree.")
                await ctx.send("Synchronised bot tree.")
            except Exception as e:
                print(f"Tree sync failed: {e}.")
                return await ctx.send(f"Failed to sync bot tree: {e}")
            

