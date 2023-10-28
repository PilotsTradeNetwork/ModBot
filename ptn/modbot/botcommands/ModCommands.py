# discord.py
import time
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
from ptn.modbot.constants import role_council, role_mod, role_sommelier, bc_categories, channel_evidence
from ptn.modbot.database.database import insert_infraction, find_infraction

# local modules
from ptn.modbot.modules.ErrorHandler import on_app_command_error, on_generic_error, CustomError
from ptn.modbot.modules.Helpers import find_thread, display_infractions, get_rule, create_thread, warn_user, \
    get_message_attachments, is_image_url

"""
A primitive global error handler for text commands.

returns: error message to user and log
"""


@bot.listen()
async def on_command_error(ctx, error):
    print(error)
    if isinstance(error, commands.BadArgument):
        message = f'Bad argument: {error}'

    elif isinstance(error, commands.CommandNotFound):
        message = f"Sorry, were you talking to me? I don't know that command."

    elif isinstance(error, commands.MissingRequiredArgument):
        message = f"Sorry, that didn't work.\n• Check you've included all required arguments." \
                  "\n• If using quotation marks, check they're opened *and* closed, and are in the proper place.\n• Check quotation" \
                  " marks are of the same type, i.e. all straight or matching open/close smartquotes."

    elif isinstance(error, commands.MissingPermissions):
        message = 'Sorry, you\'re missing the required permission for this command.'

    elif isinstance(error, commands.MissingAnyRole):
        message = f'You require one of the following roles to use this command:\n<@&{role_council()}> • <@&{role_mod()}>'

    else:
        message = f'Sorry, that didn\'t work: {error}'

    embed = discord.Embed(description=f"❌ {message}", color=constants.EMBED_COLOUR_ERROR)
    await ctx.send(embed=embed)


'''
MODALS FOR WARNS
'''


class InfractionReport(ui.Modal, title='Warn User'):

    # pass variables into the modal for throughput
    def __init__(self, warned_user: discord.Member, warning_moderator: discord.Member, warning_time: int,
                 interaction: discord.Interaction, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.warned_user = warned_user
        self.warning_moderator = warning_moderator
        self.warning_time = warning_time
        self.interaction = interaction

    rule_number = ui.TextInput(
        label='Rule Broken',
        placeholder='Number (i.e. \'1\') of the rule broken...',
        required=True
    )
    warning_reason = ui.TextInput(
        label='Warning Reason',
        style=discord.TextStyle.long,
        placeholder='Describe the infraction...',
        max_length=300,
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # await interaction.response.send_message(
        #     f'EXAMPLE: \n'
        #     f'WARNED USER: {self.warned_user}\n'
        #     f'WARNING MODERATOR: {self.warning_moderator}\n'
        #     f'WARNING TIME: {self.warning_time}\n'
        #     f'RULE BROKEN: {self.rule_number}\n'
        #     f'WARNING REASON: {self.warning_reason}',
        #     ephemeral=True
        # )
        warning_reason = str(self.warning_reason)

        warning_data = {
            'warned_user': self.warned_user,
            'interaction': interaction,
            'warning_moderator': self.warning_moderator,
            'warning_reason': warning_reason,
            'warning_time': int(time.time()),
            'rule_number': int(str(self.rule_number))
        }
        await interaction.response.send_message(view=WarningAndDMConfirmation(warning_data=warning_data), ephemeral=True)
        # await warn_user(**warning_data)


# Class for confirming warning and asking for DM or not
class WarningAndDMConfirmation(discord.ui.View):
    def __init__(self, warning_data: dict):
        super().__init__(timeout=None)
        self.send_dm = False
        self.warning_data = warning_data

    @discord.ui.button(label='DM User', style=discord.ButtonStyle.secondary, emoji='💬', custom_id='dm user', row=0)
    async def dm_user_select_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.send_dm:
            print(f'{interaction.user.display_name} is deselecting DM User')
            self.send_dm = False
            button.style = discord.ButtonStyle.red  # Update button style here
        else:
            print(f'{interaction.user.display_name} is selecting DM User')
            self.send_dm = True
            button.style = discord.ButtonStyle.green  # Update button style here

        # Use the current view instance for updating the message
        await interaction.response.edit_message(view=self)

    @discord.ui.button(label='Confirm Infraction', style=discord.ButtonStyle.green, emoji='✔️',
                       custom_id='confirm_send', row=1)
    async def confirm_infraction(self, interaction: discord.Interaction, button: discord.ui.Button):
        print('received infraction confirmation')
        button.disabled = True
        print(f'{interaction.user.display_name} is reporting an infraction')

        try:
            await interaction.response.edit_message(content='Proceeding with warning...', view=None)
            await warn_user(warned_user=self.warning_data.get('warned_user'),
                            interaction=interaction,
                            warning_moderator=self.warning_data.get('warning_moderator'),
                            warning_time=self.warning_data.get('warning_time'),
                            warning_reason=self.warning_data.get('warning_reason'),
                            rule_number=self.warning_data.get('rule_number'),
                            send_dm=self.send_dm,
                            image=self.warning_data.get('image'))
        except Exception as e:
            return await on_generic_error(interaction, e)


# Class for reporting of infraction messages
class MessageInfractionReport(ui.Modal, title='Delete and create infraction from message'):
    def __init__(self, interaction: discord.Interaction, message: discord.Message, attachments: list, stickers: list):
        super().__init__()
        self.interaction = interaction
        self.message = message
        self.attachments = attachments
        self.stickers = stickers

    rule_number = ui.TextInput(
        label='Rule Broken',
        placeholder='Number (i.e. \'1\') of the rule broken...',
        required=True
    )
    warning_description = ui.TextInput(
        label='Warning Context [Optional]',
        style=discord.TextStyle.long,
        placeholder='Describe the infraction...',
        max_length=300,
        required=False
    )

    async def on_submit(self, interaction: discord.Interaction):
        warned_user = self.message.author
        warning_moderator = interaction.user
        warning_time = int(time.time())
        rule_broken = int(str(self.rule_number))
        image = None

        warning_reason = "**Infraction Message:**\n"

        if self.warning_description:
            warning_reason += f"**Context:** {self.warning_description}\n"

        if self.stickers:
            warning_reason += f'**Message Stickers:** \n'
            for sticker in self.stickers:
                warning_reason += f'{sticker.url}\n'

        if self.attachments:
            picture_loaded = False
            non_image_attachments = []

            for url in self.attachments:
                if not picture_loaded and is_image_url(url):
                    image = url
                    picture_loaded = True
                    warning_reason += f'**Image Link:** {url}\n'
                else:
                    non_image_attachments.append(url)

            if non_image_attachments:
                warning_reason += '**Message Attachments:**\n'
                for idx, att in enumerate(non_image_attachments, start=1):
                    warning_reason += f"{idx}. {att}\n"

        if self.message.content:
            warning_reason += f"**Message Text:** {self.message.content}"

        # await warn_user(warned_user=warned_user, interaction=interaction, warning_moderator=warning_moderator,
        #                 warning_reason=warning_reason, warning_time=warning_time, rule_number=rule_broken, image=image)

        warning_data = {
            'warned_user': warned_user,
            'interaction': interaction,
            'warning_moderator': warning_moderator,
            'warning_reason': warning_reason,
            'warning_time': int(time.time()),
            'rule_number': rule_broken,
            'image': image
        }

        await interaction.response.send_message(view=WarningAndDMConfirmation(warning_data=warning_data),
                                                ephemeral=True)


        await self.message.delete()


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
    async def rule(self, interaction: discord.Interaction, rule_number: int, member: discord.Member = None):
        await get_rule(interaction=interaction, rule_number=rule_number, member=member)

    # relies on getting member infractions
    @app_commands.command(name='warn', description='Warn a user')
    @commands.has_any_role(*constants.any_elevated_role)
    @describe(member='The member to be warned')
    async def warn(self, interaction: discord.Interaction, member: discord.Member):
        print(f"warn called by {interaction.user.display_name}")

        warned_user = member
        warning_moderator = interaction.user
        warning_time = int(time.time())

        await interaction.response.send_modal(
            InfractionReport(warned_user=warned_user, warning_time=warning_time, warning_moderator=warning_moderator,
                             interaction=interaction))

    # command to find a user's infraction thread, if exists
    @app_commands.command(name='find_thread', description='finds a thread given a user\'s id')
    @commands.has_any_role(*constants.any_elevated_role)
    @describe(id='id of the member')
    async def find_thread(self, interaction: discord.Interaction, id: str):
        # check if user is in guild
        guild = interaction.guild
        try:
            member_object = interaction.guild.get_member(int(id))
        except Exception as e:
            try:
                raise CustomError(f"ID input must be an number! \n`{e}`")
            except Exception as e:
                return await on_generic_error(interaction, e)

        # find and send thread id
        thread = await find_thread(member=member_object, guild=guild, interaction=interaction)
        if thread:
            await interaction.response.send_message(f"<#{thread.id}>", ephemeral=True)
        else:
            try:
                raise CustomError("That thread doesn't exist!")
            except Exception as e:
                return await on_generic_error(interaction, e)

    @app_commands.command(name='test_view')
    async def test_view(self, interaction: discord.Interaction):
        await interaction.response.send_message(view=WarningAndDMConfirmation())


# An interaction to view a user's infractions
@bot.tree.context_menu(name='View Infractions')
@commands.has_any_role(*constants.any_elevated_role)
async def view_infractions(interaction: discord.Interaction, member: discord.Member):
    print(f"view_infractions called by {interaction.user.display_name} for {member.display_name}")
    guild = interaction.guild
    spamchannel = bot.get_channel(constants.channel_botspam())

    await display_infractions(interaction=interaction, member=member, guild=guild)


# An interaction to delete a violating message and send it to the infractions thread, with option to DM the user
@bot.tree.context_menu(name='Delete & Warn')
@commands.has_any_role(*constants.any_elevated_role)
async def infraction_message(interaction: discord.Interaction, message: discord.Message):
    print(
        f"infraction_message by {interaction.user.display_name} for user {message.author.display_name}'s message in "
        f"{message.channel.id}.")

    # Get the message attachments if they exist
    attachments = get_message_attachments(message)
    stickers = message.stickers

    await interaction.response.send_modal(MessageInfractionReport(interaction=interaction, message=message,
                                                                  attachments=attachments, stickers=stickers))


@bot.tree.context_menu(name='Report to Mods')
@commands.has_any_role(role_council(), role_mod(), role_sommelier())
async def report_to_moderation(interaction: discord.Interaction, message: discord.Message):
    reporting_user = interaction.user
    reporting_user_roles = [role.id for role in reporting_user.roles]
    mod_role = interaction.guild.get_role(role_mod())
    evidence_channel = interaction.guild.get_channel(channel_evidence())

    if role_council() not in reporting_user_roles and role_mod() not in reporting_user_roles:
        if interaction.channel.category.id not in bc_categories():
            try:
                raise CustomError('You can only run this command in the Booze Cruise channels!')
            except Exception as e:
                return await on_generic_error(interaction=interaction, error=e)

    attachment_urls = get_message_attachments(message=message)

    reported_user = message.author
    report_time = datetime.utcnow()
    report_title = f'Report from <@{interaction.user.id}> on a message from <@{reported_user.id}> in ' \
                   f'<#{interaction.channel.id}>.\n'

    embed = discord.Embed(
        description=report_title,
        timestamp=report_time,
        color=constants.EMBED_COLOUR_QU
    )

    report_message = ''

    if message.content:
        report_message += f"Message Text: {message.clean_content}\n"

    if message.stickers:
        report_message += f'Message Stickers: \n'
        for sticker in message.stickers:
            report_message += f'{sticker.url}\n'

    if attachment_urls:
        picture_loaded = False
        for idx, url in enumerate(attachment_urls):
            if not picture_loaded and is_image_url(url):
                embed.set_image(url=url)
                picture_loaded = True
            else:
                report_message += f' Message Attachments: {url}\n'

    embed.add_field(
        name='Message Content',
        value=report_message
    )

    response_embed = discord.Embed(
        description='✅ Message sent to moderation.',
        color=constants.EMBED_COLOUR_OK
    )

    await evidence_channel.send(embed=embed, content=f'{mod_role.mention}')
    await message.delete()
    await interaction.response.send_message(embed=response_embed, ephemeral=True)
