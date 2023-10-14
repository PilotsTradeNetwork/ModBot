# discord.py
from datetime import datetime

import discord
from discord import app_commands, ui
from discord.app_commands import describe
from discord.ext import commands

import ptn.modbot.constants as constants

# local constants
from ptn.modbot._metadata import __version__

# import bot
from ptn.modbot.bot import bot
from ptn.modbot.constants import role_council, role_mod

# local modules
from ptn.modbot.modules.ErrorHandler import on_app_command_error
from ptn.modbot.modules.Helpers import find_thread, display_infractions, get_rule

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


'''
MODAL FOR MESSAGE DELETION
'''


class InfractionReport(ui.Modal, title='Delete and Report Message'):

    # pass variables into the modal for throughput
    def __init__(self, warned_user, warning_moderator, warning_time, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.warned_user = warned_user
        self.warning_moderator = warning_moderator
        self.warning_time = warning_time

    rule_number = ui.TextInput(
        label='Rule Broken',
        placeholder='Number (i.e. \'1\') of the rule broken...'
    )
    warning_reason = ui.TextInput(
        label='Warning Reason',
        style=discord.TextStyle.long,
        placeholder='Describe the infraction...',
        max_length=300
    )

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            f'EXAMPLE: \n'
            f'WARNED USER: {self.warned_user}\n'
            f'WARNING MODERATOR: {self.warning_moderator}\n'
            f'WARNING TIME: {self.warning_time}\n'
            f'RULE BROKEN: {self.rule_number}\n'
            f'WARNING REASON: {self.warning_reason}',
            ephemeral=True
        )


"""
COG FOR COMMANDS/SLASH COMMANDS
"""


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

    # command to display a rule with an option to ping a member
    @app_commands.command(name='rule', description='Prints a rule buy its number, with option to mention a member')
    @commands.has_any_role(*constants.any_elevated_role)
    @describe(rule_number='Number of the rule you wish to print')
    @describe(member='[Optional] Mention a user based off user id')
    async def rule(self, interaction: discord.Interaction, rule_number: int, member: str = None):

        # get member object
        if member:
            try:
                member = interaction.guild.get_member(int(member))
            except ValueError:
                interaction.response.send_message(f'\'{member}\' is not a valid user id.')
                return

        await get_rule(interaction=interaction, rule_number=rule_number, member=member)

    # relies on getting member infractions
    @app_commands.command(name='warn', description='view moderator infractions, with option to send warning DM')
    @commands.has_any_role(*constants.any_elevated_role)
    @describe(member_id='id of the member')
    async def warn(self, interaction: discord.Interaction, member_id: str):
        print(f"warn called by {interaction.user.display_name}")

        # get guild
        guild = interaction.guild

        # get member object
        member = guild.get_member(int(member_id))

        spamchannel = bot.get_channel(constants.channel_botspam())
        await display_infractions(guild=guild, member=member, interaction=interaction)

    # command to find a user's infraction thread, if exists
    @app_commands.command(name='find_thread', description='finds a thread given a user\'s id')
    @commands.has_any_role(*constants.any_elevated_role)
    @describe(id='id of the member')
    async def find_thread(self, interaction: discord.Interaction, id: str):
        # check if user is in guild
        guild = interaction.guild
        try:
            member_object = guild.get_member(int(id))

        except ValueError:
            embed = discord.Embed(
                description=f"❌ {id} is not a valid integer.",
                color=constants.EMBED_COLOUR_ERROR
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # find and send thread id
        await find_thread(member=member_object, guild=guild, interaction=interaction)


# An interaction to view a user's infractions
@bot.tree.context_menu(name='View Infractions')
@commands.has_any_role(*constants.any_elevated_role)
async def view_infractions(interaction: discord.Interaction, member: discord.Member):
    print(f"view_infractions called by {interaction.user.display_name} for {member.display_name}")
    guild = interaction.guild
    spamchannel = bot.get_channel(constants.channel_botspam())

    await display_infractions(interaction=interaction, member=member, guild=guild)


# An interaction to delete a violating message and send it to the infractions thread, with option to DM the user
@bot.tree.context_menu(name='Infraction Message')
@commands.has_any_role(*constants.any_elevated_role)
async def infraction_message(interaction: discord.Interaction, message: discord.Message):
    print(
        f"infraction_message by {interaction.user.display_name} for user {message.author.display_name}'s message in {message.channel.id}.")
    if message.author.bot:
        embed = discord.Embed(
            description=f"❌ You cannot warn bots!",
            color=constants.EMBED_COLOUR_ERROR
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Infractions need 3 things: warned_user id, warning_moderator id, warning_time

    warned_user = message.author.id
    warning_moderator = interaction.user.id
    warning_time = datetime.utcnow()

    await interaction.response.send_modal(
        InfractionReport(warned_user=warned_user, warning_time=warning_time, warning_moderator=warning_moderator))
