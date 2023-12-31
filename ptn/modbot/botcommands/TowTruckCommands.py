import re
import time
from sqlite3 import IntegrityError
from typing import List

import discord
from discord import app_commands
from discord.app_commands import describe
from discord.ext import commands

from ptn.modbot import constants
from ptn.modbot.bot import bot
from ptn.modbot.constants import role_tow_truck, channel_botspam, channel_tow_truck
from ptn.modbot.database.database import insert_carrier, find_carrier, delete_carrier, get_all_carriers, edit_carrier
from ptn.modbot.modules.ErrorHandler import on_app_command_error, CustomError, on_generic_error
from ptn.modbot.modules.Helpers import check_roles, warn_user, build_tow_truck_embed, \
    build_or_update_tow_truck_pin_embed, find_largest_user_roles


class TowTruckCommands(commands.Cog):
    def __init__(self, bot: commands.Cog):
        self.bot = bot

    def cog_load(self):
        tree = self.bot.tree
        self._old_tree_error = tree.on_error
        tree.on_error = on_app_command_error

    def cog_unload(self):
        tree = self.bot.tree
        tree.on_error = self._old_tree_error

    @app_commands.command(name='impound', description='Tow a carrier to the impound lot | Generates an infraction')
    @check_roles(constants.any_elevated_role)
    @describe(carrier_owner='In-game name or @user')
    async def tow_carrier(self, interaction: discord.Interaction, carrier_name: str,
                          carrier_id: str, carrier_position: str, carrier_owner: str):

        # initial constants
        guild = interaction.guild
        tow_truck_role = guild.get_role(role_tow_truck())
        spam_channel = guild.get_channel(channel_botspam())
        spam_embed = discord.Embed(description=f'{interaction.user.mention} impounded a carrier with the id '
                                               f'{carrier_id}', color=constants.EMBED_COLOUR_QU)
        tow_truck_channel = guild.get_channel(channel_tow_truck())
        bot_guild_member = guild.get_member(bot.user.id)

        # check for member object
        regex_mention_pattern = r"<@!?(\d+)>"
        member_match = re.findall(regex_mention_pattern, carrier_owner)
        member = None
        if member_match:
            if len(member_match) > 1:
                try:
                    raise CustomError('You can only input one member!')
                except Exception as e:
                    return await on_generic_error(interaction, e)
            member_id = int(member_match[0])
            member = guild.get_member(member_id)

        # if member, check if bot can edit roles
            if member == guild.owner:
                try:
                    raise CustomError('You cannot tow the discord owner!')
                except Exception as e:
                    return await on_generic_error(interaction, e)

            if not bot_guild_member.guild_permissions.manage_roles:
                try:
                    raise CustomError('Bot does not have role edit permissions!')
                except Exception as e:
                    return await on_generic_error(interaction, e)

            if bot_guild_member.top_role.position < member.top_role.position:
                try:
                    raise CustomError('Bot cannot tow members with higher roles!')
                except Exception as e:
                    return await on_generic_error(interaction, e)

        position_choices = [
            'Wally Bei | Planet 4 (Malerba)',
            'Wally Bei | Planet 5 (Swanson)',
            'Wally Bei | Middle',
            'Mbutas | Planet A1/A1a (Burkin)',
            'Mbutas | Planet A2/A2a (Darlton)'
        ]

        # enforce choice from menu
        if carrier_position not in position_choices:
            try:
                raise CustomError('You must use one of the choices!')
            except Exception as e:
                return await on_generic_error(interaction, e)

        # initial message
        await interaction.response.defer(ephemeral=True, thinking=True)

        # get user roles if given member
        roles = None
        member_id = None
        if member:
            role_ids = [role.id for role in member.roles]

            # prevent mod or council from being hit
            if any(role_id in role_ids for role_id in constants.any_elevated_role) or member.bot:
                try:
                    raise CustomError('What are you trying to do, eh?')
                except Exception as e:
                    return await on_generic_error(interaction, e)

            # the bird
            if member == bot.user:
                embed = discord.Embed(color=constants.EMBED_COLOUR_ERROR)
                embed.set_image(url=constants.the_bird)
                await interaction.followup.send(embed=embed, ephemeral=True)
                return

            # Transform roles into string for storage
            role_ids = [str(role.id) for role in member.roles]
            roles_string = ",".join(role_ids)
            member_id = member.id
            roles = roles_string
            spam_embed = discord.Embed(
                description=f'{interaction.user.mention} impounded a carrier with the id {carrier_id} '
                            f'for member {member.mention}', color=constants.EMBED_COLOUR_QU)

        try:
            # insert into database
            await insert_carrier(carrier_name=carrier_name, carrier_id=carrier_id, in_game_carrier_owner=carrier_owner,
                                 discord_user=member_id, user_roles=roles, carrier_position=carrier_position)
        except IntegrityError:
            print('Carrier is already in database, returning...')
            already_towed_embed = discord.Embed(description='Carrier is already in the lot!',
                                                color=constants.EMBED_COLOUR_CAUTION)
            await interaction.followup.send(embed=already_towed_embed, ephemeral=True)
            return

        # member operations
        if member:
            # check if user already has tow truck
            if str(tow_truck_role.id) not in role_ids:
                # Remove roles, [1:] is to skip @everyone
                await member.remove_roles(*member.roles[1:], reason=f"Tow Truck from {interaction.user.display_name}")

                # Give tow truck role
                await member.add_roles(tow_truck_role, reason=f"Tow Truck from {interaction.user.display_name}")

                # Ping in tow channel
                async for message in tow_truck_channel.history(limit=None):
                    if message.author == bot.user:
                        if message.content == tow_truck_role.mention:
                            await message.delete()
                await tow_truck_channel.send(tow_truck_role.mention)

                # Generate infraction
                await warn_user(warned_user=member, interaction=interaction, warning_moderator=interaction.user,
                                warning_reason=f'Tow Truck for carrier {carrier_id} | {carrier_position}',
                                warning_time=int(time.time()), rule_number=6, original_interaction=interaction,
                                warning_message='')

            final_embed = discord.Embed(description=f'Successfully towed {member.mention}\'s carrier',
                                        color=constants.EMBED_COLOUR_QU)

        else:
            final_embed = discord.Embed(description=f'Successfully towed the carrier',
                                        color=constants.EMBED_COLOUR_QU)

        # end
        await build_or_update_tow_truck_pin_embed(interaction)
        await interaction.followup.send(embed=final_embed, ephemeral=True)
        await spam_channel.send(embed=spam_embed)

    @tow_carrier.autocomplete('carrier_position')
    async def position_autocomplete(self, interaction: discord.Interaction, current: str) -> List[
        app_commands.Choice[str]]:
        choices = [
            'Wally Bei | Planet 4 (Malerba)',
            'Wally Bei | Planet 5 (Swanson)',
            'Wally Bei | Middle',
            'Mbutas | Planet A1/A1a (Burkin)',
            'Mbutas | Planet A2/A2a (Darlton)'
        ]
        return [
            app_commands.Choice(name=choice, value=choice)
            for choice in choices if current.lower() in choice.lower()
        ]

    @app_commands.command(name='release', description='Removes a carrier from the impound lot')
    @check_roles(constants.any_elevated_role)
    async def release_carrier(self, interaction: discord.Interaction, carrier_id_or_member: str):
        print(f'Call for an impound lot release for a carrier from {interaction.user.display_name}')

        # initial constants
        guild = interaction.guild
        spam_channel = guild.get_channel(channel_botspam())
        not_found_embed = discord.Embed(description='Carrier was not found in the database',
                                        color=constants.EMBED_COLOUR_QU)
        tow_truck_role = guild.get_role(role_tow_truck())
        multiple_carriers = False
        everyone_role = guild.default_role

        # initial response
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Catch non-input
        # check for member object
        regex_mention_pattern = r"<@!?(\d+)>"
        regex_id_pattern = r"[A-Za-z]{3}-\d{3}"
        member_match = re.findall(regex_mention_pattern, carrier_id_or_member)
        id_match = re.findall(regex_id_pattern, carrier_id_or_member)
        member = None
        if member_match and id_match:
            try:
                raise CustomError('You can only input member or id, not both!')
            except Exception as e:
                return await on_generic_error(interaction, e)

        if member_match:
            if len(member_match) > 1:
                try:
                    raise CustomError('You can only input one member!')
                except Exception as e:
                    return await on_generic_error(interaction, e)

            member_id = int(member_match[0])
            member = guild.get_member(member_id)

        elif id_match:
            if len(id_match) > 1:
                try:
                    raise CustomError('You can only input one id!')
                except Exception as e:
                    return await on_generic_error(interaction, e)

            carrier_id = carrier_id_or_member
            carrier_to_remove = await find_carrier(carrier_id, 'carrier_id')

        else:
            try:
                raise CustomError('You must put in a carrier id or a discord member!')
            except Exception as e:
                return await on_generic_error(interaction, e)

        # Find carrier and delete carrier
        if member:
            carrier_to_remove = await find_carrier(member.id, 'discord_user')
            if len(carrier_to_remove) > 1:
                carrier_ids = [carrier.carrier_id for carrier in carrier_to_remove]
                carrier_ids_string = "\n".join(carrier_ids)
                multi_carrier_embed = discord.Embed(description='This member has multiple carriers, '
                                                                'please go by carrier id.\n' + carrier_ids_string)
                await interaction.followup.send(embed=multi_carrier_embed, ephemeral=True)
                return

        # Message and end if not found
        if not carrier_to_remove:
            await interaction.followup.send(embed=not_found_embed, ephemeral=True)
            return

        possible_member = carrier_to_remove[0].discord_user
        if possible_member:
            member = interaction.guild.get_member(possible_member)
            if member:
                carriers = await find_carrier(member.id, 'discord_user')
                multiple_carriers = len(carriers) > 1
                print(multiple_carriers)

        # Get the carrier with the roles
        if multiple_carriers:

            # filter carrier to remove from other carriers
            other_carriers = [carrier for carrier in carriers if carrier.entry_id != carrier_to_remove[0].entry_id]

            # get role count in carrier_to_remove
            to_remove_role_count = len(carrier_to_remove[0].user_roles.split(','))

            # get the max number of roles from other carrier objects
            max_roles = 0
            for carrier in other_carriers:
                if carrier.entry_id == carrier_to_remove[0].entry_id:
                    continue
                num_roles = len(carrier.user_roles.split(','))
                if num_roles > max_roles:
                    max_roles = num_roles

            # transfer roles to the next carrier if the carrier to remove has the highest number
            if to_remove_role_count > max_roles:
                roles_to_carrier = other_carriers[0]
                await edit_carrier(roles_to_carrier.entry_id, user_roles=carrier_to_remove[0].user_roles)

        # Entry id from object
        entry_id = carrier_to_remove[0].entry_id
        carrier_id = carrier_to_remove[0].carrier_id

        # Delete carrier from database
        await delete_carrier(entry_id)

        # if member, give back roles and remove tow truck
        if member and not multiple_carriers:
            # remove tow truck role
            await member.remove_roles(tow_truck_role)

            # get roles from object
            roles = [int(role_id) for role_id in carrier_to_remove[0].user_roles.split(",")]
            bad_roles = []
            roles_list = []
            for role_id in roles:

                # skip everyone
                if role_id == everyone_role.id:
                    continue

                # try to give roles, add to list if can't
                try:
                    role = interaction.guild.get_role(role_id)

                    # add not added role to the list
                    if not role:
                        bad_roles.append(role_id)

                    roles_list.append(role)

                except Exception as e:
                    print(e)
                    bad_roles.append(role_id)

            await member.add_roles(*roles_list)

            if bad_roles:
                print("COULD NOT GIVE ROLES")
                print(bad_roles)

        # end
        if multiple_carriers:
            success_embed = discord.Embed(description='✅ Successfully removed carrier from the database, '
                                                      'user still has carriers in the database.',
                                          color=constants.EMBED_COLOUR_OK)
        else:
            success_embed = discord.Embed(description='✅ Successfully removed carrier from the database',
                                          color=constants.EMBED_COLOUR_OK)
        await interaction.followup.send(embed=success_embed, ephemeral=True)

        if member:
            spam_embed = discord.Embed(
                description=f'ℹ️ {interaction.user.mention} removed {member.mention}\'s carrier from '
                            f'the tow lot ({carrier_id})', color=constants.EMBED_COLOUR_QU)
        else:
            spam_embed = discord.Embed(description=f'ℹ️ {interaction.user.mention} removed carrier {carrier_id} from '
                                                   f'the tow lot')
        await build_or_update_tow_truck_pin_embed(interaction)
        await spam_channel.send(embed=spam_embed)

    @app_commands.command(name='tow_lot', description='View carriers in the lot')
    @check_roles(constants.any_elevated_role)
    async def view_carriers(self, interaction: discord.Interaction):

        # get all carriers in database
        carrier_objects = await get_all_carriers()

        if not carrier_objects:
            no_carriers_embed = discord.Embed(description='ℹ️ There are no carriers in the impound lot',
                                              color=constants.EMBED_COLOUR_QU)
            await interaction.response.send_message(embed=no_carriers_embed, ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        # build embed
        tow_lot_embed = await build_tow_truck_embed(interaction)

        await interaction.followup.send(embed=tow_lot_embed, ephemeral=True)

    @app_commands.command(name='refresh_tow_embed', description='Refreshes the tow lot embed')
    @check_roles(constants.any_elevated_role)
    async def refresh_tow_embed(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True, thinking=True)
        await build_or_update_tow_truck_pin_embed(interaction)

        success_embed = discord.Embed(description='✅ Refreshed embed', color=constants.EMBED_COLOUR_OK)

        await interaction.followup.send(embed=success_embed, ephemeral=True)
