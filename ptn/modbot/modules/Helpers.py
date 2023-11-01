import os
from datetime import datetime
import requests
import discord
from discord import app_commands
from discord.app_commands import commands

from ptn.modbot import constants
from ptn.modbot.constants import channel_evidence, bot_guild, channel_rules, channel_botspam, forum_channel
from ptn.modbot.bot import bot
from ptn.modbot.database.database import find_infraction, insert_infraction
from ptn.modbot.modules.ErrorHandler import CustomError, on_generic_error, CommandRoleError

"""
THREAD HELPERS

Used for thread creation/interactions
"""


# create thread
def create_thread(member: discord.Member, guild: discord.Guild):
    try:
        # get member info
        member_name = member.name
        member_id = member.id

        # get channel info
        print(f'create_thread called for {member_name}')
        infractions_channel = guild.get_channel_or_thread(forum_channel())

        # create thread
        thread_name = f'{member_name} | {member_id}'
        return infractions_channel.create_thread(name=thread_name, content='🔨')
    except Exception as e:
        raise CustomError(f"Error in thread creation: {e}")


# gets thread by id match in name
async def find_thread(interaction: discord.Interaction, member: discord.Member, guild: discord.Guild):
    # get member info
    member_name = member.name
    member_id = member.id

    # get channel info
    print(f'find_thread called for {member_name}')

    evidence_channel = guild.get_channel(forum_channel())

    threads = evidence_channel.threads
    # print(type(threads))
    thread = next((thread for thread in threads if str(member_id) in thread.name), None)
    # print(thread)

    if thread:
        return thread

    else:
        # embed = discord.Embed(
        #    description=f"❓ That thread doesn't exist for user <@{member_id}>.",
        #    color=discord.Color.yellow()
        # )
        # await interaction.response.send_message(embed=embed, ephemeral=True)
        return False


"""
INFRACTION HELPERS

Used for infraction displaying and creation
"""


# display user infractions
async def display_infractions(interaction: discord.Interaction, member: discord.Member, guild: discord.Guild):
    try:
        # search for user id in column 2
        infractions = await find_infraction(member.id, 'warned_user')
        # print(infractions)

        # initialize embed
        embed = discord.Embed(
            title='User Infractions',
            color=constants.EMBED_COLOUR_QU
        )

        # set initial values
        embed.set_author(name=member.name)
        embed.set_footer(text=f'ID: {member.id}')

        # find if thread exists
        thread = await find_thread(guild=guild, member=member, interaction=interaction)
        if thread:
            embed.description = f'Thread: <#{thread.id}>'

        # display infractions as a list
        if not infractions:
            embed.description = embed.description + "\nUser has no infractions on record."
        else:
            for i, infraction in enumerate(infractions, start=1):
                infraction_value = f'<t:{infraction.warning_time}:f> | Rule Broken: {infraction.rule_broken} | Warning ' \
                                   f'Reason: {infraction.warning_reason}'
                embed.add_field(name=f'Infraction {i}', value=infraction_value)

        await interaction.response.send_message(embed=embed, ephemeral=True)

    except Exception as e:
        try:
            raise CustomError(f"Could not retrieve infraction: {e}")
        except Exception as e:
            return await on_generic_error(interaction, e)


"""
RULE HELPERS

Used for getting and displaying rules
"""


async def rule_check(rule_number: int, interaction: discord.Interaction):
    if rule_number <= 0:
        try:
            raise CustomError('Rule must be a positive value!')
        except Exception as e:
            return await on_generic_error(interaction, e)

    guild = interaction.channel.guild

    # get rule channel from guild
    rules_channel_object = guild.get_channel(channel_rules())

    # fetch rules message from rules channel
    rules_message = await rules_channel_object.fetch_message(constants.rules_message())

    # get the rule embeds from the message
    rules_list = rules_message.embeds

    # get the rule
    try:
        return bool(rules_list[rule_number - 1])
    except IndexError:
        try:
            raise CustomError(f'That is not a valid rule!')
        except Exception as e:
            return await on_generic_error(interaction=interaction, error=e)


async def get_rule(rule_number: int, interaction: discord.Interaction, member: discord.Member = None):
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

    # get the rule
    try:
        rule = rules_list[rule_number - 1]
    except IndexError:
        try:
            raise CustomError(f'That is not a valid rule!')
        except Exception as e:
            return await on_generic_error(interaction=interaction, error=e)

    if member:
        try:
            await interaction.channel.send(embed=rule, content=member.mention)

        except Exception as e:
            try:
                raise CustomError(f"Could not mention member: {e}")
            except Exception as e:
                return await on_generic_error(interaction, e)
    else:
        await interaction.channel.send(embed=rule)

    confirmation_embed = discord.Embed(
        description=f"✅ Sent rule in <#{interaction.channel}>",
        color=constants.EMBED_COLOUR_OK
    )
    await interaction.response.send_message(embed=confirmation_embed, ephemeral=True)


"""
WARNING HELPER
"""


async def warn_user(warned_user: discord.Member, interaction: discord.Interaction, warning_moderator: discord.Member,
                    warning_reason: str, warning_time: int, rule_number: int, original_interaction: discord.Interaction
                    , image: str = None, send_dm: bool = False):
    spamchannel = interaction.guild.get_channel(channel_botspam())

    # find and count previous infractions
    infractions = await find_infraction(warned_user.id, 'warned_user')
    # (len(infractions))
    current_infraction_number = len(infractions) + 1

    # handle thread (find if exists, create if not)
    try:
        thread = await find_thread(interaction=interaction, member=warned_user, guild=interaction.guild)
        print(thread)

        if not thread:
            await create_thread(member=warned_user, guild=interaction.guild)
            thread = await find_thread(interaction, warned_user, guild=interaction.guild)
            ping_message = await thread.send(constants.the_bird)
            await ping_message.edit(content=f'{interaction.guild.get_role(constants.role_mod()).mention}')
            print(f"Created thread with id {thread.id}")

    except Exception as e:
        try:
            raise CustomError(f"Error in thread handling: {e}")
        except Exception as e:
            return await on_generic_error(interaction=interaction, error=e)

    # Insert infraction into database
    try:
        infraction = await insert_infraction(
            warned_user=warned_user.id,
            warning_time=warning_time,
            warning_moderator=warning_moderator.id,
            rule_broken=rule_number,
            warning_reason=warning_reason,
            thread_id=thread.id
        )
    except Exception as e:
        try:
            raise CustomError(f"Error in database interaction: {e}")
        except Exception as e:
            return await on_generic_error(interaction, e)

    # post infraction to thread
    embed = discord.Embed(
        title=f"Infraction #{current_infraction_number}",
        timestamp=datetime.fromtimestamp(warning_time)
    )
    embed.add_field(
        name="User",
        value=f"<@{warned_user.id}>",
        inline=True
    )
    embed.add_field(
        name="Moderator",
        value=f"<@{warning_moderator.id}>",
        inline=True
    )
    embed.add_field(
        name="Reason",
        value=warning_reason,
        inline=True
    )
    embed.add_field(
        name='Rule Broken',
        value=rule_number,
        inline=True
    )

    embed.add_field(
        name='Database Entry',
        value=infraction,
        inline=True
    )
    embed.set_image(url=image)
    await thread.send(embed=embed)

    # DM user
    if send_dm:
        warning_dm_message = 'Hello, this message is to inform you that you have received an infraction from the P.T.N ' \
                             f'Mod team for being deemed in violation of Rule {rule_number}. For any questions about ' \
                             'the nature of this infraction, please DM a Mod and we will answer them as best as we can.'

        warning_dm_embed = discord.Embed(
            title='Infraction Received',
            description=warning_dm_message,
            color=constants.EMBED_COLOUR_ERROR
        )

        try:
            await warned_user.send(embed=warning_dm_embed)
        except Exception as e:
            try:
                raise CustomError(f'Could not DM user: {e}')
            except Exception as e:
                return await on_generic_error(interaction, e)

    # Success Message
    embed = discord.Embed(
        description="✅ **Successfully issued and logged infraction.**",
        color=constants.EMBED_COLOUR_OK
    )

    spam_embed = discord.Embed(
        description=f'A new infraction was created for {warned_user.mention} by {warning_moderator.mention}',
        color=constants.EMBED_COLOUR_QU
    )
    await spamchannel.send(embed=spam_embed)

    original_interaction_message = await original_interaction.original_response()

    try:
        await original_interaction_message.edit(embed=embed, view=None, content=None)
    except:
        await interaction.followup.send(embed=embed, ephemeral=True)


"""
GENERAL HELPERS
"""


def get_message_attachments(message: discord.Message):
    attachments = message.attachments
    attachment_urls = []
    if attachments:
        for attachment in attachments:
            attachment_urls.append(attachment.url)

    return attachment_urls


def is_image_url(url):
    # List of allowed image extensions
    allowed_extensions = ['.jpg', '.jpeg', '.png', '.webp', '.gif']

    # Extract the file extension from the URL
    file_extension = os.path.splitext(url)[1].split('?')[0]  # Splits by '?' to handle query parameters

    return file_extension in allowed_extensions


def get_role(ctx, id):  # takes a Discord role ID and returns the role object
    role = discord.utils.get(ctx.guild.roles, id=id)
    return role


async def checkroles_actual(interaction: discord.Interaction, permitted_role_ids):
    try:
        """
        Check if the user has at least one of the permitted roles to run a command
        """
        print(f"checkroles called.")
        author_roles = interaction.user.roles
        permitted_roles = [get_role(interaction, role) for role in permitted_role_ids]
        print(author_roles)
        print(permitted_roles)
        permission = True if any(x in permitted_roles for x in author_roles) else False
        print(f'Permission: {permission}')
        return permission, permitted_roles
    except Exception as e:
        print(e)
    return permission


def check_roles(permitted_role_ids):
    async def checkroles(interaction: discord.Interaction):
        permission, permitted_roles = await checkroles_actual(interaction, permitted_role_ids)
        print("Inherited permission from checkroles")
        if not permission:  # raise our custom error to notify the user gracefully
            role_list = []
            for role in permitted_role_ids:
                role_list.append(f'<@&{role}> ')
                formatted_role_list = " • ".join(role_list)
            try:
                raise CommandRoleError(permitted_roles, formatted_role_list)
            except CommandRoleError as e:
                print(e)
                raise
        return permission

    return app_commands.check(checkroles)


async def delete_thread_if_only_bot_message(message: discord.Message):
    """
    If there are no embed messages from the bot in the thread, delete the thread.
    """
    # Fetching all messages in the thread (you might want to adjust the limit based on your needs)
    messages = [msg async for msg in message.channel.history(limit=None)]

    bot_embed_messages = [msg for msg in messages if msg.author.bot and msg.embeds]

    # Check if there are no embed messages from the bot
    if not bot_embed_messages:
        if isinstance(message.channel, discord.Thread):  # Ensure it's a thread before deleting
            await message.channel.delete()


def can_see_channel(channel_id):
    """Check if the member can see the specific channel."""

    async def predicate(interaction: discord.Interaction):
        # Get the channel object using the channel_id
        channel = interaction.guild.get_channel(channel_id)
        if not channel:
            raise commands.CheckFailure("Channel not found in this guild.")

        # Check if the member can read the channel's messages
        if not channel.permissions_for(interaction.user).read_messages:
            raise commands.CheckFailure("You do not have permissions to run this command.")

        return True

    return commands.check(predicate)

