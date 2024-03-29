# discord.py
import re
import time
from datetime import datetime, timedelta

# import discord
import discord
from discord import app_commands, ui
from discord.app_commands import describe
from discord.ext import commands

# import metadata
from ptn.modbot._metadata import __version__

# import bot
from ptn.modbot.bot import bot

# import constants
import ptn.modbot.constants as constants
from ptn.modbot.constants import role_council, role_mod, channel_evidence, \
    channel_botspam, forum_channel, dyno_user, atlas_channel, any_elevated_role

# import database functions
from ptn.modbot.database.database import find_infraction, delete_single_warning, edit_infraction

# local modules
from ptn.modbot.modules.ErrorHandler import on_app_command_error, on_generic_error, CustomError
from ptn.modbot.modules.Helpers import (find_thread, display_infractions, get_rule, create_thread, warn_user,
                                        check_roles, rule_check, delete_thread_if_only_bot_message, can_see_channel, \
    warning_color, is_in_channel, edit_warning_reason, member_or_member_id)

'''
MODALS FOR WARNS
'''


# From /warn
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
        placeholder='Number (i.e. \'1\') of the rule broken... | Tow truck is rule 6',
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
        warning_reason = str(self.warning_reason)
        if not await rule_check(rule_number=int(str(self.rule_number)), interaction=interaction):
            return
        try:
            warning_data = {
                'warned_user': self.warned_user,
                'interaction': interaction,
                'warning_moderator': self.warning_moderator,
                'warning_reason': warning_reason,
                'warning_time': int(time.time()),
                'rule_number': int(str(self.rule_number))
            }
            embed = discord.Embed(description='DMing the member is disabled by default, this is for if the infraction '
                                              'requires manual intervention.', color=constants.EMBED_COLOUR_QU)
            await interaction.response.send_message(view=WarningAndDMConfirmation(warning_data=warning_data),
                                                    ephemeral=True, embed=embed)
            # await warn_user(**warning_data)

        except Exception as e:
            try:
                raise CustomError(f'Could not warn member! `{e}`')
            except Exception as e:
                return await on_generic_error(interaction, e)


# Class for confirming warning deletion
class DeletionConfirmation(discord.ui.View):
    def __init__(self, infraction_entry: int, message: discord.Message, original_interaction: discord.Interaction):
        super().__init__(timeout=None)
        self.infraction_entry = infraction_entry
        self.message = message
        self.original_interaction = original_interaction

    @discord.ui.button(label='Delete', style=discord.ButtonStyle.green, emoji='⚠️', custom_id='delete', row=0)
    async def delete_infraction_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        botspam = interaction.guild.get_channel(channel_botspam())

        # Get the infraction number
        infraction_number = int(self.message.embeds[0].title.split('#')[1])
        # Delete infraction in thread
        await self.message.delete()

        # Delete infraction in database
        await delete_single_warning(self.infraction_entry)

        original_response = await self.original_interaction.original_response()

        spam_embed = discord.Embed(
            description=f'<@{interaction.user.id}> deleted an infraction',
            color=constants.EMBED_COLOUR_QU
        )
        await botspam.send(embed=spam_embed)

        # Call our helper function to check and delete the thread if necessary
        user_messages = [message async for message in interaction.channel.history() if not message.author.bot]
        if not user_messages:
            await delete_thread_if_only_bot_message(self.message)

        embed_confirmation = discord.Embed(
            description='✅ Infraction Deleted',
            color=constants.EMBED_COLOUR_OK
        )
        await original_response.delete()
        await interaction.response.send_message(ephemeral=True, embed=embed_confirmation)

        print('Infraction Removal Successful')

        messages = [message async for message in interaction.channel.history(limit=100)]
        # Update infraction numbers
        for message in messages:
            if message.embeds:
                embed = message.embeds[0]
                title = embed.title
                if title.startswith("Infraction #"):
                    current_number = int(title.split('#')[1])
                    if current_number >= infraction_number:
                        new_title = f"Infraction #{current_number - 1}"
                        new_embed = embed.to_dict()
                        new_embed['title'] = new_title
                        new_embed['color'] = warning_color(current_number - 1)
                        await message.edit(embed=discord.Embed.from_dict(new_embed))
                        print('Updated message')

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.red, emoji='✖️', custom_id='cancel', row=0)
    async def cancel_deletion(self, interaction: discord.Interaction, button: discord.Button):
        original_response = await self.original_interaction.original_response()

        embed_confirmation = discord.Embed(
            description='❌ Canceled.',
            color=constants.EMBED_COLOUR_QU
        )
        await original_response.delete()
        await interaction.response.send_message(ephemeral=True, embed=embed_confirmation)


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
        # print('received infraction confirmation')
        button.disabled = True
        print(f'{interaction.user.display_name} is reporting an infraction')

        try:
            embed = discord.Embed(description='Proceeding with warning...', color=constants.EMBED_COLOUR_QU)
            await interaction.response.edit_message(view=None, embed=embed)
            await warn_user(warned_user=self.warning_data.get('warned_user'),
                            interaction=interaction,
                            warning_moderator=self.warning_data.get('warning_moderator'),
                            warning_time=self.warning_data.get('warning_time'),
                            warning_reason=self.warning_data.get('warning_reason'),
                            rule_number=self.warning_data.get('rule_number'),
                            send_dm=self.send_dm,
                            image=self.warning_data.get('image'),
                            original_interaction=interaction,
                            warning_message=self.warning_data.get('warning_message'))
        except Exception as e:
            return await on_generic_error(interaction, e)


# From Delete & Warn
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
        try:
            warned_user = self.message.author
            warning_moderator = interaction.user
            rule_broken = int(str(self.rule_number))
            image = None

            if not await rule_check(rule_number=int(str(self.rule_number)), interaction=interaction):
                return

            warning_reason = ''
            warning_message = ''
            if self.warning_description:
                warning_reason += f"**Warning reason from Mod:** {self.warning_description}\n"

            if self.stickers:
                warning_message += f'**Message Stickers:** \n'
                for itx, sticker in enumerate(self.stickers, start=1):
                    warning_message += f'[Sticker {itx}]({sticker.url})\n'
                print('Stickers in Message')

            if self.attachments:
                warning_reason += "**Message had attachments**\n"

            if self.message.content:
                warning_message += f"\n**Message Text:** {self.message.content}"

            # await warn_user(warned_user=warned_user, interaction=interaction, warning_moderator=warning_moderator,
            # warning_reason=warning_reason, warning_time=warning_time, rule_number=rule_broken, image=image)

            warning_data = {
                'warned_user': warned_user,
                'interaction': interaction,
                'warning_moderator': warning_moderator,
                'warning_reason': warning_reason,
                'warning_message': warning_message,
                'warning_time': int(time.time()),
                'rule_number': rule_broken,
                'image': image
            }
            print('Sending Warning Confirmation')
            embed = discord.Embed(description='DMing the member is disabled by default, this is for if the infraction '
                                              'requires manual intervention.', color=constants.EMBED_COLOUR_QU)
            await interaction.response.send_message(view=WarningAndDMConfirmation(warning_data=warning_data),
                                                    ephemeral=True, embed=embed)
            await self.message.delete()
        except Exception as e:
            try:
                raise CustomError(f'Could not delete and warn member! `{e}`')
            except Exception as e:
                return await on_generic_error(interaction, e)


"""
COG FOR COMMANDS/SLASH COMMANDS
"""


class ModCommands(commands.Cog):
    def __init__(self, bot: commands.Cog):
        self.bot = bot
        self.summon_message_ids = {}

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
    @check_roles(constants.any_elevated_role)
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
    @check_roles(constants.any_elevated_role)
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
    @check_roles(constants.any_elevated_role)
    @describe(rule_number='Number of the rule you wish to print')
    @describe(member='[Optional] Mention a user')
    async def rule(self, interaction: discord.Interaction, rule_number: int, member: discord.Member = None):
        if member:
            if member.bot:
                try:
                    raise CustomError('Bots are too cool for rules 💀')
                except Exception as e:
                    return await on_generic_error(interaction, e)

        await get_rule(interaction=interaction, rule_number=rule_number, member=member)

    # relies on getting member infractions
    @app_commands.command(name='warn', description='Warn a user')
    @check_roles(constants.any_elevated_role)
    @describe(member='The member to be warned')
    async def warn(self, interaction: discord.Interaction, member: str):
        print(f"warn called by {interaction.user.display_name}")
        guild = interaction.guild
        regex_match = member_or_member_id(member)

        if regex_match:
            member_id = int(regex_match[0])
            member = guild.get_member(member_id)

            if not member:
                member = await bot.fetch_user(member_id)

                if not member:
                    try:
                        raise CustomError("Could not find discord user from id.")
                    except Exception as e:
                        return await on_generic_error(interaction, e)

        else:
            try:
                raise CustomError('Could not find user.')
            except Exception as e:
                return await on_generic_error(interaction, e)

        if member.bot:
            if member == bot.user:
                embed = discord.Embed(color=constants.EMBED_COLOUR_ERROR)
                embed.set_image(url=constants.the_bird)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            try:
                raise CustomError('You cannot warn bots.')
            except Exception as e:
                return await on_generic_error(interaction, e)

        warned_user = member
        warning_moderator = interaction.user
        warning_time = int(time.time())

        await interaction.response.send_modal(
            InfractionReport(warned_user=warned_user, warning_time=warning_time, warning_moderator=warning_moderator,
                             interaction=interaction))

    # command to find a user's infraction thread, if exists
    @app_commands.command(name='find_thread', description='finds a thread given a user\'s id')
    @check_roles(constants.any_elevated_role)
    async def find_thread(self, interaction: discord.Interaction, member: discord.Member):
        # check if user is in guild
        guild = interaction.guild

        # Check if member is bot
        if member.bot:
            if member == bot.user:
                embed = discord.Embed(color=constants.EMBED_COLOUR_ERROR)
                embed.set_image(url=constants.the_bird)
                await interaction.response.send_message(embed=embed, ephemeral=True)
                return
            embed = discord.Embed(description='❌ Bots cannot have threads', color=constants.EMBED_COLOUR_ERROR)
            await interaction.response.send_message(embed=embed, ephemeral=True)

        # find and send thread id
        thread = await find_thread(member=member, guild=guild, interaction=interaction)
        if thread:
            await interaction.response.send_message(f"<#{thread.id}>", ephemeral=True)
        else:
            embed = discord.Embed(description=f'<@{member.id}> does not have a thread.',
                                  color=constants.EMBED_COLOUR_QU)
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name='sync_infractions', description='Sync infractions from the database to the thread')
    @check_roles(constants.any_elevated_role)
    async def sync_infractions(self, interaction: discord.Interaction, member: discord.Member):
        print(f'{interaction.user.display_name} called sync_infractions')
        guild = interaction.guild
        botspam = guild.get_channel(channel_botspam())

        db_infractions = await find_infraction(member.id, 'warned_user')
        # print(db_infractions)
        await find_thread(interaction, member, guild)
        thread = await find_thread(interaction, member, guild)

        # If there are no infractions in the database and a thread exists, delete the thread and inform the user.
        if not db_infractions and thread:
            non_bot_messages = [message async for message in thread.history() if not message.author.bot]
            if non_bot_messages:
                async for message in thread.history():
                    if message.author == bot.user:
                        await message.delete()

                response_embed = discord.Embed(
                    description=f'Cleaned thread for <@{member.id}>, did not delete due to user messages in channel.',
                    color=constants.EMBED_COLOUR_OK)

                await interaction.response.send_message(embed=response_embed, ephemeral=True)
                return

            await thread.delete()
            response_embed = discord.Embed(
                description=f'Thread for <@{member.id}> deleted as no infractions were found in the database.',
                color=constants.EMBED_COLOUR_OK)

            spam_embed = discord.Embed(
                description=f'Thread for <@{member.id}> deleted in sync action from <@{interaction.user.id}>.',
                color=constants.EMBED_COLOUR_QU
            )
            await interaction.response.send_message(embed=response_embed, ephemeral=True)
            await botspam.send(embed=spam_embed)
            return

        # If no infractions exist in the database for the member and no thread exists, exit early.
        if not db_infractions:
            response_embed = discord.Embed(description=f'No infractions found for <@{member.id}> in the database.',
                                           color=constants.EMBED_COLOUR_OK)
            await interaction.response.send_message(embed=response_embed, ephemeral=True)
            return

        if not thread:
            thread = await create_thread(member, guild)

        response_embed = discord.Embed(description=f'Syncing Infractions for <@{member.id}>...')
        await interaction.response.send_message(embed=response_embed, ephemeral=True)

        def extract_id(value: str) -> int:
            match = re.search(r'(\d+)', value)
            if match:
                return int(match.group(1))
            return 0  # return a default value if no match

        def extract_infraction_from_embed(embed: discord.Embed) -> dict:
            return {
                'warned_user': extract_id(embed.fields[0].value),
                'warning_moderator': extract_id(embed.fields[1].value),
                'warning_time': embed.timestamp.timestamp(),
                'warning_reason': embed.fields[2].value,
                'rule_broken': embed.fields[3].value,
                'entry_id': embed.fields[4].value,
                'thread_id': thread.id
            }

        thread_infractions = []
        async for message in thread.history():
            for embed in message.embeds:
                infraction = extract_infraction_from_embed(embed)
                thread_infractions.append(infraction)

        db_infractions_raw = await find_infraction(member.id, 'warned_user')
        db_infractions = [infraction.to_dictionary() for infraction in db_infractions_raw]
        db_ids = {infraction['entry_id'] for infraction in db_infractions}
        # print(db_ids)
        thread_ids = {int(infraction['entry_id']) for infraction in thread_infractions}
        # print(thread_ids)

        # Infractions missing in the thread
        missing_in_thread = db_ids - thread_ids
        # print(missing_in_thread)
        for itx, infraction in enumerate(db_infractions):
            if infraction['entry_id'] in missing_in_thread:
                print('MISSING IN THREAD, SENDING...')
                embed = discord.Embed(
                    title=f"Infraction #{itx + 1}",
                    timestamp=datetime.fromtimestamp(infraction['warning_time'])
                )
                embed.add_field(name="User", value=f"<@{infraction['warned_user']}>", inline=True)
                embed.add_field(name="Moderator", value=f"<@{infraction['warning_moderator']}>", inline=True)
                embed.add_field(name="Reason", value=infraction['warning_reason'], inline=True)
                embed.add_field(name='Rule Broken', value=infraction['rule_broken'], inline=True)
                embed.add_field(name='Database Entry', value=infraction['entry_id'], inline=True)
                embed.set_footer(text='Synced from database')
                await thread.send(embed=embed)

        # Infractions present in thread but not in database
        extra_in_thread = thread_ids - db_ids
        # print(extra_in_thread)
        if extra_in_thread:
            messages_to_delete = []
            async for message in thread.history():
                for embed in message.embeds:
                    if int(embed.fields[4].value) in extra_in_thread:
                        messages_to_delete.append(message)
            for msg in messages_to_delete:
                await msg.delete()

        await interaction.delete_original_response()
        await interaction.followup.send(embed=discord.Embed(description=f'✅ Infractions Synced',
                                                            color=constants.EMBED_COLOUR_OK), ephemeral=True)

    @app_commands.command(name='summon_mod', description='Summons a mod for help in a channel')
    @can_see_channel(atlas_channel())
    async def summon_mod(self, interaction: discord.Interaction):
        print(f"Summoned to {interaction.channel} by {interaction.user}")
        guild = interaction.guild
        evidence_channel = guild.get_channel(channel_evidence())
        mod_role = guild.get_role(role_mod())
        summon_time = f'<t:{int(time.time())}:t> (<t:{int(time.time())}:R>)'

        print("⏳ Notifying user")
        waiting_embed = discord.Embed(description=f'🕰️ Summoning a {mod_role.mention}...',
                                      color=constants.EMBED_COLOUR_QU)

        await interaction.response.send_message(embed=waiting_embed, ephemeral=True)

        print("⏳ Fetching channel message...")
        # Fetch the last message in the channel before the summon
        last_message_url = None
        try:
            messages = [message async for message in interaction.channel.history(limit=1) if not message.author.bot]
            if messages:
                last_message = messages[0]
                last_message_url = last_message.jump_url
                last_message_link = f"[Jump to message]({last_message_url})"
            else:
                last_message_link = "No previous messages found."
        except:
            last_message_link = "No previous messages found."

        print("▶ Sending to mod-evidence")
        # Send summon message to evidence channel
        alert_embed = discord.Embed(title='📟 A user is requesting a mod',
                                    description=f'{summon_time} {interaction.user.mention} is requesting a mod in '
                                                f'{interaction.channel.mention}.'
                                                f'\n\n**Last message before summon:** {last_message_link}',
                                    color=constants.EMBED_COLOUR_CAUTION)
        summon_message_content = f'<@&{mod_role.id}>: summoned to {interaction.channel.mention} by {interaction.user.mention}'
        summon_message = await evidence_channel.send(content=summon_message_content, embed=alert_embed)
        await summon_message.add_reaction('✅')

        success_embed = discord.Embed(description=f'✅ A {mod_role.mention} has been summoned.',
                                      color=constants.EMBED_COLOUR_OK)

        print("▶ Updating status for user")
        await interaction.edit_original_response(embed=success_embed)

        # Store the ID of the summon message for future reference
        self.summon_message_ids[summon_message.id] = {
            'summon_time': summon_time,
            'last_message_url': last_message_url,
            'last_message_link': last_message_link,
            'channel_mention': interaction.channel.mention
        }

    # Listener for summon message
    @commands.Cog.listener()
    async def on_reaction_add(self, reaction: discord.Reaction, user: discord.User):
        if reaction.message.id in self.summon_message_ids:
            # Additional checks: Is the user a mod? Is the reaction on a summon message?
            if check_roles(any_elevated_role):
                summon_info = self.summon_message_ids[reaction.message.id]
                new_embed = discord.Embed(
                    title='🛡️ A mod is answering the summons',
                    description=f"{summon_info['summon_time']} {user.mention} is answering the mod summon in "
                                f"{summon_info['channel_mention']}."
                                f"\n\n**Last message before summon:** {summon_info['last_message_link']}",
                    color=constants.EMBED_COLOUR_OK
                )
                self.summon_message_ids.pop(reaction.message.id, None)
                await reaction.message.edit(embed=new_embed)

    @app_commands.command(name='search_dyno', description='Searches for previous hits from dyno')
    @check_roles(constants.any_elevated_role)
    @is_in_channel(channel_evidence())
    async def search_dyno(self, interaction: discord.Interaction, member: discord.Member):
        print(f'search_dyno called by {interaction.user.display_name}')
        wait_embed = discord.Embed(
            description='Searching for Dyno Bonks, this may take a few moments...',
            color=constants.EMBED_COLOUR_QU
        )
        evidence_channel = interaction.guild.get_channel(channel_evidence())

        joined_at = member.joined_at.replace(tzinfo=None)
        over_a_year = joined_at < (datetime.now().replace(tzinfo=None) - timedelta(days=365))
        search = f'in:{evidence_channel.name} ID: {member.id}'
        if over_a_year:
            print('User is over a year old, sending discord search text')
            embed = discord.Embed(
                description=f'⚠️ User has been in the server for over a year, use this search instead:\n'
                            + f'`{search}`',
                color=constants.EMBED_COLOUR_CAUTION)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        print(f'Searching for messages after {joined_at}')

        await interaction.response.send_message(embed=wait_embed,
                                                ephemeral=True)
        original_id = str(member.id)

        # Search for messages from Dyno with a matching ID in the footer
        matching_messages = []
        messages = [message async for message in interaction.channel.history(limit=None, oldest_first=False,
                                                                             after=joined_at)
                    if message.author.id == dyno_user()]
        for history_message in messages:
            if history_message.author.id == dyno_user() and history_message.embeds:
                for embed in history_message.embeds:
                    if embed.footer and 'ID: ' + original_id in embed.footer.text:
                        for line in embed.description.split('\n'):
                            pattern = r"\*\*Message sent by <@\d+> deleted in <#\d+>\*\*"
                            if bool(re.match(pattern, line)):
                                matching_messages.append(history_message)

        if matching_messages:
            report_embed = discord.Embed(
                title='Previous Hits Found',
                color=constants.EMBED_COLOUR_CAUTION
            )
            matching_messages.reverse()

            for itx, message in enumerate(matching_messages, start=1):
                embed = message.embeds[0]
                description = embed.description
                reason = embed.fields[0].value
                try:
                    detailed_reason = embed.fields[1].value
                except:
                    detailed_reason = 'None Given'

                report_embed.add_field(
                    name=f'Hit #{itx}',
                    value=f'{description}\nReason: {reason} | Detailed Reason: {detailed_reason}\n',
                    inline=False
                )
                report_embed.set_footer(text=search)

            await interaction.edit_original_response(embed=report_embed)

        else:
            report_embed = discord.Embed(
                description='ℹ️ No previous hits found',
                color=constants.EMBED_COLOUR_QU
            )
            report_embed.set_footer(text=search)
            await interaction.edit_original_response(embed=report_embed)


"""
CONTEXT MENU COMMANDS
"""


# An interaction to view a user's infractions
@bot.tree.context_menu(name='View Infractions')
@check_roles(constants.any_elevated_role)
async def view_infractions(interaction: discord.Interaction, member: discord.Member):
    print(f"view_infractions called by {interaction.user.display_name} for {member.display_name}")
    guild = interaction.guild
    if member.bot:
        if member == bot.user:
            embed = discord.Embed(color=constants.EMBED_COLOUR_ERROR)
            embed.set_image(url=constants.the_bird)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        embed = discord.Embed(description='❌ Bots cannot have infractions', color=constants.EMBED_COLOUR_ERROR)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    await display_infractions(interaction=interaction, member=member, guild=guild)


# An interaction to delete a violating message and send it to the infractions thread, with option to DM the user
@bot.tree.context_menu(name='Delete & Warn')
@check_roles(constants.any_elevated_role)
async def infraction_message(interaction: discord.Interaction, message: discord.Message):
    print(
        f"infraction_message by {interaction.user.display_name} for user {message.author.display_name}'s message in "
        f"{message.channel.id}.")

    if message.author.bot:
        if message.author == bot.user:
            embed = discord.Embed(color=constants.EMBED_COLOUR_ERROR)
            embed.set_image(url=constants.the_bird)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        try:
            raise CustomError('You cannot report bot messages.')
        except Exception as e:
            return await on_generic_error(interaction, e)

    # Get the message attachments if they exist
    attachments = message.attachments
    stickers = message.stickers

    await interaction.response.send_modal(MessageInfractionReport(interaction=interaction, message=message,
                                                                  attachments=attachments, stickers=stickers))


@bot.tree.context_menu(name='Report to Mods')
@can_see_channel(constants.atlas_channel())
async def report_to_moderation(interaction: discord.Interaction, message: discord.Message):
    reporting_user = interaction.user
    reporting_user_roles = [role.id for role in reporting_user.roles]
    mod_role = interaction.guild.get_role(role_mod())
    evidence_channel = interaction.guild.get_channel(channel_evidence())

    if message.author.bot:
        if message.author == bot.user:
            embed = discord.Embed(color=constants.EMBED_COLOUR_ERROR)
            embed.set_image(url=constants.the_bird)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        try:
            raise CustomError('You cannot report bot messages.')
        except Exception as e:
            return await on_generic_error(interaction, e)

    mod = role_mod() in reporting_user_roles or role_council() in reporting_user_roles

    reported_user = message.author
    report_time = datetime.now()
    report_title = f'### Report from <@{interaction.user.id}> on a message from <@{reported_user.id}> in ' \
                   f'<#{interaction.channel.id}>.\n'

    report_message = '\n'
    if not mod:
        report_message += f'Message Link: {message.jump_url}\n'
        evidence_message_content = f'{mod_role.mention}: report in {interaction.channel.mention} from {interaction.user.mention}'

    else:
        evidence_message_content = f'Report in {interaction.channel.mention} from {interaction.user.mention}'

    # Max message length for users is 2000 characters, if we somehow go past 4096 then wtf
    if message.content:
        report_message += f"Message Text: {message.clean_content}\n"

    if message.stickers:
        report_message += f'\nMessage Stickers: \n'
        for idx, sticker in enumerate(message.stickers):
            report_message += f'{idx}. [Sticker URL]({sticker.url})\n'

    if message.attachments:
        report_message += '**Message has attachments**'

    description = report_title + report_message

    embed = discord.Embed(
        description=description,
        timestamp=report_time,
        color=constants.EMBED_COLOUR_QU
    )

    response_embed = discord.Embed(
        description='✅ Message sent to moderation.',
        color=constants.EMBED_COLOUR_OK
    )

    await evidence_channel.send(embed=embed, content=evidence_message_content)

    if mod:
        await message.delete()

    await interaction.response.send_message(embed=response_embed, ephemeral=True)


@bot.tree.context_menu(name='Remove Infraction')
@check_roles(constants.any_elevated_role)
async def remove_infraction(interaction: discord.Interaction, message: discord.Message):
    channel = interaction.channel
    try:
        if interaction.channel.parent_id == forum_channel() and isinstance(channel, discord.Thread):
            infraction_embed = message.embeds[0]
            infraction_user = re.sub(r'[^a-zA-Z0-9 ]', '', infraction_embed.fields[0].value)
            infraction_entry = int(infraction_embed.fields[3].value)
            # await interaction.response.send_message(f'TEST:\nREASON: {infraction_reason}\nUSER: {infraction_user}')

            embed = discord.Embed(
                description='Confirm Delete this Infraction?',
                color=constants.EMBED_COLOUR_QU
            )

            infraction = await find_infraction(int(infraction_user), 'warned_user', infraction_entry, 'entry_id')
            if infraction:
                await interaction.response.send_message(
                    view=DeletionConfirmation(infraction_entry, message, interaction),
                    embeds=[embed, infraction_embed], ephemeral=True)
    except AttributeError:
        try:
            raise CustomError(f'Must be in a thread in <#{forum_channel()}>.')
        except Exception as e:
            return await on_generic_error(interaction, e)

    except IndexError:
        try:
            raise CustomError(f'Must be on an infraction message.')
        except Exception as e:
            return await on_generic_error(interaction, e)


@bot.tree.context_menu(name='Warning from Report')
@is_in_channel(channel_evidence())
@check_roles(constants.any_elevated_role)
async def report_to_warn(interaction: discord.Interaction, message: discord.Message):
    # Check if message is from Dyno
    dyno = False
    if message.author.id == dyno_user():
        dyno = True
        print('WARNING FROM DYNO BONK')

    # Check if message is from the bot
    elif not (message.author == bot.user):
        try:
            raise CustomError(f'Message must be from <@{bot.user.id}>')
        except Exception as e:
            return await on_generic_error(interaction, e)

    # check and get dyno embed
    try:
        report_embed = message.embeds[0]
    except IndexError:
        try:
            raise CustomError('Must be run on reports only!')
        except Exception as e:
            return await on_generic_error(interaction, e)

    # If message is from ModBot
    if not dyno:
        try:
            user_pattern = r"<@(\d+)>"
            channel_pattern = r"<#(\d+)>"
            content = report_embed.description
            content_title = content.split('\n')[0]
            user_ids = re.findall(user_pattern, content_title)
            channel_ids = re.findall(channel_pattern, content_title)
            if not (len(user_ids) == 2 and len(channel_ids) == 1):
                raise Exception
        except:
            try:
                raise CustomError('Must be run on reports only!')
            except Exception as e:
                return await on_generic_error(interaction, e)

        report_info = report_embed.description

        # Get the ids for the reporter, the reported, and the channel which the id is from
        numbers = re.findall(r'<[@#](\d+)>', report_info)
        reporter_id, reported_user_id, channel_id = numbers

        # get reported user
        reported_user = interaction.guild.get_member(int(reported_user_id))
        if not reported_user:
            try:
                reported_user = await bot.fetch_user(reported_user_id)

            except discord.NotFound:
                try:
                    raise CustomError('Could not find the user in the report')
                except Exception as e:
                    return await on_generic_error(interaction, e)

            except discord.HTTPException as e:
                try:
                    raise CustomError(f'HTTP Error: {e}')
                except Exception as e:
                    return await on_generic_error(interaction, e)

        # Reporter should probably be in the server, if not then wtf
        reporter_user = interaction.guild.get_member(int(reporter_id))
        message_link = message.jump_url
        content_field = (f'\nOriginal Reporter: <@{reporter_user.id}>\nReported Channel: <#{channel_id}>\n'
                         f'Report Message Link: {message_link}')

    else:
        fields = report_embed.fields
        main_content = report_embed.description

        header_pattern = re.compile(r"<@\d+>.*<#\d+>\*\*")
        if not bool(header_pattern.search(main_content)):
            try:
                raise CustomError('Not a dyno report!')
            except Exception as e:
                return await on_generic_error(interaction, e)

        hit_reason = fields[0].value
        hit_word = fields[1].value

        # Compile the regular expression patterns
        user_pattern = re.compile(r"<@(\d+)>")
        channel_pattern = re.compile(r"<#(\d+)>")
        # Assume that the context starts after the '**' that follows the channel id
        context_pattern = re.compile(r"\*\*(?:(?!\*\*).)*\*\*(.*)", re.DOTALL)

        # Search the patterns in the message
        reported_user_match = user_pattern.search(main_content)
        reported_channel_match = channel_pattern.search(main_content)
        reported_context_match = context_pattern.search(main_content)

        # Extract the groups if matches were found
        reported_user_id = reported_user_match.group(1) if reported_user_match else None
        reported_user = interaction.guild.get_member(int(reported_user_id))
        if not reported_user:
            try:
                raise CustomError(f'Member not found in guild! <@{int(reported_user_id)}?')
            except Exception as e:
                return await on_generic_error(interaction, e)

        reported_channel = reported_channel_match.group(1) if reported_channel_match else None

        # The context is everything after the second '**', so strip() is used to remove whitespace
        reported_context = reported_context_match.group(1).strip() if reported_context_match else None
        # print(reported_context)
        content_field = f'**From Dyno**\nWord Hit: {hit_word}\nHit Reason: {hit_reason}\nChannel: <#{reported_channel}>' \
                        f'\nLink to hit: {message.jump_url}'

    # Modal for rule number reporting
    class RuleModal(discord.ui.Modal):
        def __init__(self):
            super().__init__(timeout=None, title='Report rule number broken')

        rule_number = ui.TextInput(
            label='Rule Broken',
            placeholder='Number (i.e. \'1\') of the rule broken...',
            required=True
        )

        async def on_submit(self, interaction: discord.Interaction):
            warning_reason = content_field + ''
            try:
                warning_data = {
                    'warned_user': reported_user,
                    'interaction': interaction,
                    'warning_moderator': interaction.user,
                    'warning_reason': warning_reason,
                    'warning_time': int(time.time()),
                    'rule_number': int(str(self.rule_number)),
                    'image': None
                }

                embed = discord.Embed(
                    description='DMing the member is disabled by default, this is for if the infraction '
                                'requires manual intervention.', color=constants.EMBED_COLOUR_QU)
                await interaction.response.send_message(view=WarningAndDMConfirmation(warning_data=warning_data),

                                                        ephemeral=True, embed=embed)
            except Exception as e:
                try:
                    raise CustomError(f'Could not warn from report! `{e}`')
                except Exception as e:
                    return await on_generic_error(interaction, e)

    await interaction.response.send_modal(RuleModal())


@bot.tree.context_menu(name='Edit Infraction')
@check_roles(constants.any_elevated_role)
async def edit_infraction_command(interaction: discord.Interaction, message: discord.Message):
    channel = interaction.channel
    is_thread = (interaction.channel.parent_id == forum_channel() and isinstance(channel, discord.Thread))

    if not is_thread:
        try:
            raise CustomError('Must be run in a thread!')
        except Exception as e:
            return await on_generic_error(interaction, e)

    try:
        infraction_embed = message.embeds[0]
        infraction_entry = int(infraction_embed.fields[4].value)
    except IndexError:
        try:
            raise CustomError(f'Must be on an infraction message.')
        except Exception as e:
            return await on_generic_error(interaction, e)

    reason_field = infraction_embed.fields[2].value

    message_infraction = False
    for line in reason_field.split('\n'):
        if line.startswith('**Warning Reason from Mod:**'):
            mod_line = line.split(':**')[1].strip(' ')
            message_infraction = True
            break

    class EditInfractionModal(ui.Modal, title='Edit Infraction'):
        def __init__(self):
            super().__init__()

        if message_infraction:
            reason_message = ui.TextInput(
                label='Change Reason',
                default=mod_line
            )
            rule_broken = ui.TextInput(
                label='Rule Broken',
                default=infraction_embed.fields[3].value
            )

        else:
            reason_full = ui.TextInput(
                label='Change Reason',
                default=infraction_embed.fields[2].value
            )
            rule_broken = ui.TextInput(
                label='Rule Broken',
                default=infraction_embed.fields[3].value
            )

        async def on_submit(self, interaction: discord.Interaction):
            if message_infraction:
                updated_reason = edit_warning_reason(reason_field, str(self.reason_message))
                updated_rule = int(str(self.rule_broken))

            else:
                updated_reason = str(self.reason_full)
                updated_rule = int(str(self.rule_broken))

            # Update database
            await edit_infraction(entry_id=infraction_entry, rule_broken=updated_rule, warning_reason=updated_reason)

            # Update embed
            infraction_embed_dict = infraction_embed.to_dict()
            for field in infraction_embed_dict['fields']:
                if field['name'] == 'Reason':
                    field['value'] = updated_reason

                if field['name'] == 'Rule Broken':
                    field['value'] = str(updated_rule)

            new_embed = discord.Embed.from_dict(infraction_embed_dict)

            await message.edit(embed=new_embed)

            confirmation_embed = discord.Embed(
                description='✅ Updated infraction successfully!',
                color=constants.EMBED_COLOUR_OK
            )

            await interaction.response.send_message(embed=confirmation_embed, ephemeral=True)

    await interaction.response.send_modal(EditInfractionModal())
