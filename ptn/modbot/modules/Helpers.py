import discord

from ptn.modbot import constants
from ptn.modbot.constants import channel_evidence, bot_guild, channel_rules
from ptn.modbot.bot import bot
from ptn.modbot.database.database import find_infraction
from ptn.modbot.modules.ErrorHandler import CustomError, on_generic_error

"""
THREAD HELPERS

Used for thread creation/interactions
"""


# create thread
def create_thread(member: discord.Member, guild: discord.Guild):
    # get member info
    member_name = member.name
    member_id = member.id

    # get channel info
    print(f'create_thread called for {member_name}')
    infractions_channel = guild.get_channel_or_thread(channel_evidence())

    # create thread
    thread_name = f'{member_name} | {member_id}'
    initial_message = f'<@{member_id}>'
    infractions_channel.create_thread(name=thread_name, message=initial_message)


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
        #embed = discord.Embed(
        #    description=f"❓ That thread doesn't exist for user <@{member_id}>.",
        #    color=discord.Color.yellow()
        #)
        #await interaction.response.send_message(embed=embed, ephemeral=True)
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

    if member:
        try:
            await interaction.channel.send(member.mention)
        except Exception as e:
            try:
                raise CustomError(f"Could not mention member: {e}")
            except Exception as e:
                return await on_generic_error(interaction, e)
    await interaction.channel.send(embed=rules_list[rule_number - 1])
    await interaction.response.send_message(f"Sent rule in {interaction.channel.name}", ephemeral=True)

