import os
import re
from datetime import datetime
import discord
import inflect
from discord import app_commands
from discord.app_commands import commands

import ptn.modbot.bot
from ptn.modbot import constants
from ptn.modbot.bot import bot
from ptn.modbot.constants import channel_evidence, bot_guild, channel_rules, channel_botspam, forum_channel, \
    EMBED_COLOUR_CAUTION, EMBED_COLOUR_ORANG, EMBED_COLOUR_EVIL, channel_cco_wmm
from ptn.modbot.database.database import find_infraction, insert_infraction, get_all_carriers
from ptn.modbot.modules.ErrorHandler import CustomError, on_generic_error, CommandRoleError

# inflect engine
p = inflect.engine()

"""
THREAD HELPERS

Used for thread creation/interactions
"""


# create thread
def create_thread(user_id, guild):
    try:
        # get channel info
        print(f'create_thread called for {user_id}')
        infractions_channel = guild.get_channel_or_thread(forum_channel())

        # member info
        member = guild.get_member(user_id)
        member_name = member.display_name

        # create thread
        thread_name = f'{member_name} | {user_id}'
        return infractions_channel.create_thread(name=thread_name, content='🔨')
    except Exception as e:
        raise CustomError(f"Error in thread creation: {e}")


# gets thread by id match in name
async def find_thread(user_id, guild):
    # get member info
    member = guild.get_member(user_id)
    member_name = member.name

    # get channel info
    print(f'find_thread called for {member_name}')

    evidence_channel = guild.get_channel(forum_channel())

    threads = evidence_channel.threads
    # print(type(threads))
    thread = next((thread for thread in threads if str(user_id) in thread.name), None)
    # print(thread)

    if thread:
        return thread

    else:
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
        thread = await find_thread(member.id, guild)
        if thread:
            embed.description = f'Thread: <#{thread.id}>'

        # display infractions as a list
        if not infractions:
            embed.description += "\nUser has no infractions on record."
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
        description=f"✅ Sent rule in <#{interaction.channel.id}>",
        color=constants.EMBED_COLOUR_OK
    )
    await interaction.response.send_message(embed=confirmation_embed, ephemeral=True)


"""
WARNING HELPER
"""


async def warn_user(warned_user: discord.Member, interaction: discord.Interaction, warning_moderator: discord.Member,
                    warning_reason: str, warning_time: int, rule_number: int, original_interaction: discord.Interaction
                    , warning_message: str, image: str = None, send_dm: bool = False):
    # initial constants
    guild = interaction.guild
    spamchannel = interaction.guild.get_channel(channel_botspam())
    evidence_channel = interaction.guild.get_channel(channel_evidence())

    # find and count previous infractions
    infractions = await find_infraction(warned_user.id, 'warned_user')
    current_infraction_number = len(infractions) + 1
    is_dyno_infraction = "**From Dyno**" in warning_reason
    current_dyno_number = len(
        [infraction for infraction in infractions if "**From Dyno**" in infraction.warning_reason])
    if is_dyno_infraction:
        current_dyno_number += 1

    # infraction number ordinals
    if current_dyno_number > 0:
        dyno_ordinal = p.ordinal(current_dyno_number)

    infraction_ordinal = p.ordinal(current_infraction_number)

    # Combine warning reason and message
    if warning_message:
        warning_reason = f'{warning_reason}\n{warning_message}'

    # check if thread exits
    thread = await find_thread(warned_user.id, guild)
    if thread:
        thread_id = thread.id
    else:
        thread_id = None

    # Insert infraction into database
    try:
        infraction = await insert_infraction(
            warned_user=warned_user.id,
            warning_time=warning_time,
            warning_moderator=warning_moderator.id,
            rule_broken=rule_number,
            warning_reason=warning_reason,
            thread_id=thread_id
        )
    except Exception as e:
        try:
            raise CustomError(f"Error in database interaction: {e}")
        except Exception as e:
            return await on_generic_error(interaction, e)
    color = warning_color(current_infraction_number)

    # DM user
    if send_dm:
        warning_dm_message = 'Hello, this message is to inform you that you have received an infraction from the P.T.N ' \
                             f'Mod team for being deemed in violation of Rule {rule_number}. For any questions about ' \
                             'the nature of this infraction, please DM a Mod and we will answer them as best as we can.'

        reason_dm_embed = discord.Embed(
            title='Warning Reason',
            description=warning_message,
            color=constants.EMBED_COLOUR_QU
        )

        warning_dm_embed = discord.Embed(
            title='Infraction Received',
            description=warning_dm_message,
            color=constants.EMBED_COLOUR_ERROR
        )

        try:
            await warned_user.send(embeds=[warning_dm_embed, reason_dm_embed])

        except Exception as e:
            await interaction.followup.send(content="Could not DM user", ephemeral=True)

    # Success Message
    embed = discord.Embed(
        description="✅ **Successfully issued and logged infraction.**",
        color=constants.EMBED_COLOUR_OK
    )

    # Build announcement description
    description = (f'ℹ️ **A new infraction was created for <@{warned_user.id}> by <@{warning_moderator.id}>.**\n'
                   f'This is their {infraction_ordinal} infraction')

    if is_dyno_infraction:
        description += f' ({dyno_ordinal} dyno infraction)'
    elif current_dyno_number > 0:
        description += f' ({current_dyno_number} dyno infraction(s)'
    description += '.'

    # Sync infractions
    await sync_infractions(warned_user.id, guild)
    thread = await find_thread(warned_user.id, guild)
    if thread:
        description += f'\nThread link: {thread.jump_url}'

    # Create thread if thread doesn't exist and if this is the member's 3rd dyno infraction or a non-dyno infraction
    if not thread and (not is_dyno_infraction or current_dyno_number >= 3):
        await create_thread(warned_user.id, guild)
        thread = await find_thread(warned_user.id, guild)
        await sync_infractions(warned_user.id, guild)
        description += f'Thread link: \n{thread.jump_url}'

    announcement_embed = discord.Embed(
        description=description,
        color=constants.EMBED_COLOUR_QU
    )
    if warning_message:
        announcement_reason_embed = discord.Embed(
            title='Message',
            description=f'{warning_message}',
            color=constants.EMBED_COLOUR_QU
        )

        await evidence_channel.send(embeds=[announcement_embed, announcement_reason_embed])

    else:
        await evidence_channel.send(embed=announcement_embed)

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


def get_role(ctx, id):
    """
    takes a Discord role ID and returns the role object
    """
    role = discord.utils.get(ctx.guild.roles, id=id)
    return role


async def checkroles_actual(interaction: discord.Interaction, permitted_role_ids):
    """
    Check if the user has at least one of the permitted roles to run a command
    """
    try:
        print(f"checkroles called.")
        author_roles = interaction.user.roles
        permitted_roles = [get_role(interaction, role) for role in permitted_role_ids]
        # print(author_roles)
        # print(permitted_roles)
        permission = True if any(x in permitted_roles for x in author_roles) else False
        # print(f'Permission: {permission}')
        return permission, permitted_roles
    except Exception as e:
        print(e)
    return permission


def check_roles(permitted_role_ids):
    """
    Returns bool based off of if user has given roles
    """

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


def warning_color(warning_number: int):
    # color handling
    if warning_number == 1:
        return EMBED_COLOUR_CAUTION
    elif warning_number == 2:
        return EMBED_COLOUR_ORANG
    else:  # this covers all cases where current_infraction_number is 3 or above
        return EMBED_COLOUR_EVIL


def is_in_channel(channel_id):
    async def predicate(interaction: discord.Interaction):
        # Get the channel object using the channel_id
        channel_to_check = interaction.guild.get_channel(channel_id)
        current_channel = interaction.channel

        # Check if the channel id is the same as the channel the interaction is run in
        if not channel_to_check == current_channel:
            raise commands.CheckFailure(f'This command can only be run in <#{channel_to_check.id}>!')

        return True

    return commands.check(predicate)


def edit_warning_reason(reason, new_reason):
    """
    Edits the warning reason in a structured message infraction.

    :param str message_infraction: The original message containing the infraction details.
    :param str new_reason: The new reason to replace the old one.
    :returns: The updated message infraction string.
    """

    # Split the message by lines
    lines = reason.split('\n')
    for i, line in enumerate(lines):
        # Check if the line contains the warning reason
        if line.startswith('**Warning Reason from Mod:**'):
            # Replace the line with the new reason
            lines[i] = f'**Warning Reason from Mod:** {new_reason}'
            break  # Stop the loop after finding and replacing the line

    # Join the lines back into a single string
    updated_message_infraction = '\n'.join(lines)
    return updated_message_infraction


async def build_tow_truck_embed(interaction: discord.Interaction):
    guild = interaction.guild
    carrier_objects = await get_all_carriers()
    tow_lot_embed = discord.Embed(title='Tow Lot', color=constants.EMBED_COLOUR_CAUTION)
    tow_lot_dict = {}
    if carrier_objects:
        for carrier in carrier_objects:
            carrier_name = carrier.carrier_name
            carrier_id = carrier.carrier_id
            carrier_owner = carrier.in_game_carrier_owner
            carrier_position = carrier.carrier_position
            carrier_discord_user = carrier.discord_user

            if carrier_position not in tow_lot_dict:
                tow_lot_dict[carrier_position] = []

            carrier_string = f'{carrier_name} ({carrier_id}) | '
            if carrier_discord_user:
                user = guild.get_member(carrier_discord_user)
                carrier_string += f' {user.mention}'
            else:
                carrier_string += f'{carrier_owner}'

            tow_lot_dict[carrier_position].append(carrier_string)

        for key, values in tow_lot_dict.items():
            field_title = key + ":\n"
            field_value = ''
            for value in values:
                field_value += f'{value}\n'

            tow_lot_embed.add_field(name=field_title, value=field_value, inline=False)
    else:
        tow_lot_embed = discord.Embed(title='Tow Lot', color=constants.EMBED_COLOUR_CAUTION,
                                      description='No carriers in tow lot')

    return tow_lot_embed


async def build_or_update_tow_truck_pin_embed(interaction: discord.Interaction):
    # get embed message if exists
    wmm_channel = interaction.guild.get_channel(channel_cco_wmm())
    pins = await wmm_channel.pins()
    new_embed = await build_tow_truck_embed(interaction)

    embed_exists = False
    for message in pins:
        if message.author.id == bot.user.id:
            if message.embeds[0].title == 'Tow Lot':
                embed_exists = True
                embed_message = message

    if embed_exists:
        await embed_message.edit(embed=new_embed)

    else:
        message = await wmm_channel.send(embed=new_embed)
        await message.pin(reason='Tow Truck Embed')


# get return the carrier object with the largest number of roles
def find_largest_user_roles(carriers):
    def numerical_value_of_roles(roles):
        # Split the string into individual numbers and convert them to integers
        return [int(role) for role in roles.split(',')]

    def compare_roles(roles1, roles2):
        # Compare two sequences of numbers
        for a, b in zip(roles1, roles2):
            if a != b:
                return a - b
        return 0

    largest_carrier = None
    largest_roles = []

    for carrier in carriers:
        current_roles = numerical_value_of_roles(carrier.user_roles)

        if largest_carrier is None or compare_roles(current_roles, largest_roles) > 0:
            largest_carrier = carrier
            largest_roles = current_roles

    return largest_carrier


def member_or_member_id(input: str):
    regex_mention_pattern = r"<@!?(\d+)>"
    regex_id_pattern = r'\d{18}'
    member_match = re.findall(regex_mention_pattern, input)
    id_match = re.findall(regex_id_pattern, input)
    if member_match:
        return member_match

    elif id_match:
        return id_match

    else:
        return None


async def sync_infractions(user_id, guild):
    # get user infractions
    infractions = await find_infraction(user_id, 'warned_user')
    current_dyno_number = len(
        [infraction for infraction in infractions if "**From Dyno**" in infraction.warning_reason])

    # only open the thread if we need to (i.e. dyno infractions are less than 3 and there are no manual infractions)
    open_thread = ((len(infractions) - current_dyno_number) > 0) or current_dyno_number >= 3

    # get thread if exists
    thread = await find_thread(user_id, guild)

    # exit early if neither exist
    if not thread and not infractions:
        print('Syncing not needed - No infractions, no threads')
        return True

    # Check if there are infractions in discord but not in the database
    if not infractions and thread:
        non_bot_messages = [message async for message in thread.history() if not message.author.bot]

        # delete all infractions, but not user messages nor the thread
        if non_bot_messages:
            async for message in thread.history():
                if message.author == bot.user:
                    await message.delete()
                    print('Synced thread - No infractions, non-bot messages present')
            return True

        # delete thread if no user messages
        await thread.delete()
        print('Synced thread - No infractions, thread deleted')

    # Delete/do not open thread if it is not necessary
    if not open_thread:
        if thread:
            await thread.delete()
            print('Synced thread - Thread threshold not met, thread deleted')
        return True

    else:
        await create_thread(user_id, guild)
        thread = await find_thread(user_id, guild)

    # info extraction from existing embeds
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
            'warning_reason': embed.description,
            'rule_broken': embed.fields[2].value,
            'entry_id': embed.fields[3].value,
            'thread_id': thread.id
        }

    thread_infractions = []
    async for message in thread.history():
        for embed in message.embeds:
            infraction = extract_infraction_from_embed(embed)
            thread_infractions.append(infraction)

    # get missing infractions from thread
    db_infractions = [infraction.to_dictionary() for infraction in infractions]
    db_ids = {infraction['entry_id'] for infraction in db_infractions}
    print(db_ids)
    thread_ids = {int(infraction['entry_id']) for infraction in thread_infractions}
    missing_in_thread = db_ids - thread_ids

    for itx, infraction in enumerate(infractions, start=1):
        infraction_ordinal = p.ordinal(itx)
        color = warning_color(itx)
        if infraction.entry_id not in missing_in_thread:
            continue

        embed = discord.Embed(
            title=f"{infraction_ordinal} Infraction",
            description="Warning Reason: " + infraction.warning_reason,
            timestamp=datetime.fromtimestamp(infraction.warning_time),
            color=color
        )
        embed.add_field(
            name="User",
            value=f"<@{infraction.warned_user}>",
            inline=True
        )
        embed.add_field(
            name="Moderator",
            value=f"<@{infraction.warning_moderator}>",
            inline=True
        )
        embed.add_field(
            name='Rule Broken',
            value=infraction.rule_broken,
            inline=True
        )

        embed.add_field(
            name='Database Entry',
            value=infraction.entry_id,
            inline=True
        )

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

    messages = [message async for message in thread.history(limit=100)]
    messages = [message for message in messages if message.embeds]
    messages.reverse()
    # Update infraction numbers
    for itx, message in enumerate(messages, start=1):
        if message.embeds:
            embed = message.embeds[0]
            title = embed.title
            if 'Infraction' in title:
                current_number = int(title[0])
                if current_number != itx:
                    new_title = f"{p.ordinal(itx)} Infraction"
                    new_embed = embed.to_dict()
                    new_embed['title'] = new_title
                    new_embed['color'] = warning_color(itx)
                    await message.edit(embed=discord.Embed.from_dict(new_embed))
                    print('Updated message')
    print('Synced thread - Fully Synced')
    return True