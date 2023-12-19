import time
from sqlite3 import IntegrityError
from typing import List

import discord
from discord import app_commands
from discord.app_commands import describe
from discord.ext import commands

from ptn.modbot import constants
from ptn.modbot.constants import role_tow_truck, channel_botspam
from ptn.modbot.database.database import insert_carrier, find_carrier, delete_carrier, get_all_carriers
from ptn.modbot.modules.ErrorHandler import on_app_command_error, CustomError, on_generic_error
from ptn.modbot.modules.Helpers import check_roles, warn_user, build_tow_truck_embed, \
    build_or_update_tow_truck_pin_embed


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
    @describe(carrier_owner='In-game name')
    async def tow_carrier(self, interaction: discord.Interaction, carrier_name: str,
                          carrier_id: str, carrier_position: str, carrier_owner: str, member: discord.Member = None):

        # initial constants
        guild = interaction.guild
        tow_truck_role = guild.get_role(role_tow_truck())
        spam_channel = guild.get_channel(channel_botspam())
        spam_embed = discord.Embed(description=f'{interaction.user.mention} impounded a carrier with the id '
                                               f'{carrier_id}', color=constants.EMBED_COLOUR_QU)
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
            already_towed_embed = discord.Embed(description='Carrier is already in the lot!', color=constants.EMBED_COLOUR_CAUTION)
            await interaction.followup.send(embed=already_towed_embed, ephemeral=True)
            return

        # member operations
        if member:
            # Remove roles, [1:] is to skip @everyone
            await member.remove_roles(*member.roles[1:], reason=f"Tow Truck from {interaction.user.display_name}")

            # Give tow truck role
            await member.add_roles(tow_truck_role, reason=f"Tow Truck from {interaction.user.display_name}")

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
    async def release_carrier(self, interaction: discord.Interaction, carrier_id: str = None,
                              member: discord.Member = None):
        print(f'Call for an impound lot release for a carrier from {interaction.user.display_name}')

        # initial constants
        spam_channel = interaction.guild.get_channel(channel_botspam())
        not_found_embed = discord.Embed(description='Carrier was not found in the database',
                                        color=constants.EMBED_COLOUR_QU)
        tow_truck_role = interaction.guild.get_role(role_tow_truck())
        multiple_carriers = False


        # initial response
        await interaction.response.defer(ephemeral=True, thinking=True)

        # Catch non-input
        if not member and not carrier_id:
            try:
                raise CustomError('You must put in a carrier id or a discord member!')
            except Exception as e:
                return await on_generic_error(interaction, e)

        # Find carrier and delete carrier
        if member:
            carrier_object = await find_carrier(member.id, 'discord_user')
            if len(carrier_object) > 1:
                carrier_ids = [carrier.carrier_id for carrier in carrier_object]
                carrier_ids_string = "\n".join(carrier_ids)
                multi_carrier_embed = discord.Embed(description='This member has multiple carriers, '
                                                                'please go by carrier id.\n'+carrier_ids_string)
                await interaction.followup.send(embed=multi_carrier_embed, ephemeral=True)
                return


        if carrier_id:
            carrier_object = await find_carrier(carrier_id, 'carrier_id')

        # Message and end if not found
        if not carrier_object:
            await interaction.followup.send(embed=not_found_embed, ephemeral=True)
            return

        possible_member = carrier_object[0].discord_user
        if possible_member:
            member = interaction.guild.get_member(possible_member)
            if member:
                multiple_carriers = len(await find_carrier(member.id, 'discord_user')) > 1
                print(multiple_carriers)

        # Entry id from object
        entry_id = carrier_object[0].entry_id

        # Delete carrier from database
        await delete_carrier(entry_id)

        # if member, give back roles and remove tow truck
        if member and not multiple_carriers:
            # remove tow truck role
            await member.remove_roles(tow_truck_role)

            # get roles from object
            roles = [int(role_id) for role_id in carrier_object[0].user_roles.split(",")]
            bad_roles = []
            for role_id in roles:
                try:
                    role = interaction.guild.get_role(role_id)

                    # add not added role to the list
                    if not role:
                        bad_roles.append(role_id)

                    await member.add_roles(role)

                except:
                    bad_roles.append(role_id)

            if bad_roles:
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
            spam_embed = discord.Embed(description=f'ℹ️ {interaction.user.mention} removed carrier {carrier_id} from '
                                                   f'the tow lot ({member.mention})')
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