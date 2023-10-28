import os
from datetime import datetime
import requests
import discord

from ptn.modbot import constants
from ptn.modbot.constants import channel_evidence, bot_guild, channel_rules
from ptn.modbot.bot import bot
from ptn.modbot.database.database import find_infraction, insert_infraction
from ptn.modbot.modules.ErrorHandler import CustomError, on_generic_error

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
        infractions_channel = guild.get_channel_or_thread(channel_evidence())

        # create thread
        thread_name = f'{member_name} | {member_id}'
        return infractions_channel.create_thread(name=thread_name)
    except Exception as e:
        raise CustomError(f"Error in thread creation: {e}")


# gets thread by id match in name
async def find_thread(interaction: discord.Interaction, member: discord.Member, guild: discord.Guild):
    # get member info
    member_name = member.name
    member_id = member.id

    # get channel info
    print(f'find_thread called for {member_name}')

    evidence_channel = guild.get_channel(channel_evidence())

    threads = evidence_channel.threads
    print(type(threads))
    thread = next((thread for thread in threads if str(member_id) in thread.name), None)
    print(thread)

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
        print(infractions)

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
                    warning_reason: str, warning_time: int, rule_number: int, image: str = None, send_dm: bool = False):




    # find and count previous infractions
    infractions = await find_infraction(warned_user.id, 'warned_user')
    print(len(infractions))
    current_infraction_number = len(infractions) + 1

    # handle thread (find if exists, create if not)
    try:
        thread = await find_thread(interaction=interaction, member=warned_user, guild=interaction.guild)
        print(thread)

        if not thread:
            thread = await create_thread(member=warned_user, guild=interaction.guild)
            print(f"Created thread with id {thread.id}")

        # post infraction to thread
        embed = discord.Embed(
            title=f"Infraction #{current_infraction_number}",
            timestamp=datetime.utcnow()
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
        embed.set_image(url=image)

        await thread.send(embed=embed)
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
        print(infraction)
    except Exception as e:
        try:
            raise CustomError(f"Error in database interaction: {e}")
        except Exception as e:
            return await on_generic_error(interaction, e)

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
        title="✅ Successfully issued and logged infraction.",
        color=constants.EMBED_COLOUR_OK
    )
    try:
        await interaction.response.edit_message(embed=embed, view=None)
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
