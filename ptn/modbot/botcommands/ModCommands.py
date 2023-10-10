# discord.py
import discord
from discord import app_commands
from discord.app_commands import describe
from discord.ext import commands

import ptn.modbot.constants as constants
# local constants
from ptn.modbot._metadata import __version__
# import bot
from ptn.modbot.bot import bot
from ptn.modbot.constants import role_council, role_mod, channel_rules
# local modules
from ptn.modbot.modules.ErrorHandler import on_app_command_error
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
class ModCommands(commands.Cog):
    def __init__(self, bot: commands.Cog):
        self.bot = bot

    def cog_load(self):
        tree = self.bot.tree
        self._old_tree_error = tree.on_error
        tree.on_error = on_app_command_error

    def cog_unload(self):
        tree = self.bot.tree
        tree.on_error = self._old_tree_error

        # ping command to check if the bot is responding
    @commands.command(name='ping', aliases=['hello', 'ehlo', 'helo'],
                      help='Use to check if modbot is online and responding.')
    @commands.has_any_role(*constants.any_elevated_role)
    async def ping(self, ctx):
        print(f"{ctx.author} used PING in {ctx.channel.name}")
        embed = discord.Embed(
            title="🟢 MOD BOT ONLINE",
            description=f"🔨<@{bot.user.id}> connected, version **{__version__}**.",
            color=constants.EMBED_COLOUR_OK
        )
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

    @app_commands.command(name='rule', description='Prints a rule buy its number, with option to mention a member')
    @commands.has_any_role(*constants.any_elevated_role)
    @describe(rule_number='Number of the rule you wish to print')
    @describe(member='[Optional] Mention a user based off user id')
    async def rule(self, interaction: discord.Interaction, rule_number: int, member: str = None):
        if rule_number <= 0:
            await interaction.response.send_message("Rule number must be positive.", ephemeral=True)
            return

        guild = interaction.channel.guild
        # get rule channel from guild
        rules_channel_object = guild.get_channel(channel_rules())
        # fetch rules message from rules channel
        rules_message = await rules_channel_object.fetch_message(constants.rules_message())

        # get the rule embeds from the message
        rules_list = rules_message.embeds

        try:
            if member:
                try:
                    member = interaction.channel.guild.get_member(int(member))

                    await interaction.channel.send(member.mention)
                except Exception as e:
                    await interaction.response.send_message(f"Could not mention member. {e}", ephemeral=True)
            await interaction.channel.send(embed=rules_list[rule_number - 1])
            await interaction.response.send_message(f"Sent rule in {interaction.channel.name}", ephemeral=True)

        except IndexError:
            await interaction.response.send_message("That rule doesn't exist!", ephemeral=True)