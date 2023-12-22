"""
Functions relating to databases used by ModBot.

Depends on: constants

Error handling: errors originating from Discord commands should be handled in their respective Cogs and outputted to user
                errors occuring on startup functions should be handled within those functions and outputted to terminal
"""

# libraries
import asyncio
import enum
import sqlite3
import os

# local classes
from ptn.modbot.classes.InfractionData import InfractionData

# local constants
import ptn.modbot.constants as constants
from ptn.modbot.bot import bot
from ptn.modbot.classes.TowTruckData import TowTruckData

"""
STARTUP FUNCTIONS
"""


# ensure all paths function for a clean install
def build_directory_tree_on_startup():
    print("Building directory tree...")
    try:
        os.makedirs(constants.DB_PATH, exist_ok=True)  # /database - the main database files
        os.makedirs(constants.SQL_PATH, exist_ok=True)  # /database/db_sql - DB SQL dumps
        os.makedirs(constants.BACKUP_DB_PATH, exist_ok=True)  # /database/backups - db backups
    except Exception as e:
        print(f"Error building directory tree: {e}")


build_directory_tree_on_startup()  # build directory structure


# build or modify database as needed on startup
def build_database_on_startup():
    print("Building database...")
    try:
        # Add a mapping when a new table needs to be created
        # Doing it this way enables us to easily add in new tables in the future
        # Requires:
        #   table_name (str):
        #       obj (sqlite db obj): sqlite connection to db
        #       create (str): sql create statement for table
        database_table_map = {
            'infractions': {'obj': infraction_db, 'create': infractions_table_create},
            'tow_truck': {'obj': infraction_db, 'create': tow_truck_table_create}
        }

        # check database exists, create from scratch if needed
        for table_name in database_table_map:
            t = database_table_map[table_name]
            if not check_database_table_exists(table_name, t['obj']):
                create_missing_table(table_name, t['obj'], t['create'])
            else:
                print(f'{table_name} table exists, do nothing')
    except Exception as e:
        print(f"Error building database: {e}")


# defining infraction table for database creation
infractions_table_create = '''
    CREATE TABLE infractions(
        entry_id INTEGER NOT NULL PRIMARY KEY,
        warned_user INTEGER NOT NULL,
        warning_moderator INTEGER NOT NULL,
        warning_time INTEGER NOT NULL,
        rule_broken INTEGER,
        warning_reason TEXT,
        thread_id INTEGER
    )
    '''

tow_truck_table_create = '''
    CREATE TABLE tow_truck(
        entry_id INTEGER NOT NULL PRIMARY KEY,
        carrier_name TEXT NOT NULL,
        carrier_id TEXT NOT NULL UNIQUE,
        carrier_position TEXT NOT NULL,
        in_game_carrier_owner TEXT NOT NULL,
        discord_user INTEGER,
        user_roles TEXT
    )   
'''


# enumerate infraction database columns
class InfractionDbFields(enum.Enum):
    entry_id = "entry_id"
    warned_user = "warned_user"
    warning_moderator = "warning_moderator"
    warning_time = "warning_time"
    rule_broken = "rule_broken"
    warning_reason = "warning_reason"
    thread_id = "thread_id"


class CarrierDbFields(enum.Enum):
    entry_id = "entry_id"
    carrier_name = "carrier_name"
    carrier_id = "carrier_id"
    carrier_position = "carrier_position"
    in_game_carrier_owner = "in_game_carrier_owner"
    discord_user = "discord_user"
    user_roles = "user_roles"


# list of infractions table columns
infractions_table_columns = [member.value for member in InfractionDbFields]


# function to check if a given table exists in a given database
def check_database_table_exists(table_name, database):
    """
    Checks whether a table exists in the database already.

    :param str table_name:  The database string name to create.
    :param sqlite.Connection.cursor database: The database to connect againt.
    :returns: A boolean state, True if it exists, else False
    :rtype: bool
    """
    print(f'Starting up - checking if {table_name} table exists or not')

    database.execute(f"SELECT count(name) FROM sqlite_master WHERE TYPE = 'table' AND name = '{table_name}'")
    return bool(database.fetchone()[0])


# function to create a missing table / database
def create_missing_table(table, db_obj, create_stmt):
    print(f'{table} table missing - creating it now')

    if os.path.exists(os.path.join(os.getcwd(), 'db_sql', f'{table}_dump.sql')):

        # recreate from backup file
        print('Recreating database from backup ...')
        with open(os.path.join(os.getcwd(), 'db_sql', f'{table}_dump.sql')) as f:

            sql_script = f.read()
            db_obj.executescript(sql_script)

    else:
        # Create a new version
        print('No backup found - Creating empty database')

        db_obj.execute(create_stmt)


"""
DATABASE OBJECT

Database connection, cursor, and lock
"""

# connect to infraction database
infraction_conn = sqlite3.connect(constants.INFRACTIONS_DB_PATH)
infraction_conn.row_factory = sqlite3.Row
infraction_db = infraction_conn.cursor()

# lock infraction db
infraction_db_lock = asyncio.Lock()

"""
DATABASE EDIT FUNCTIONS

-- Infraction Table --
- Add infraction: insert_infraction
- Search database by warned user ID: find_infraction
- Search database by entry ID: find_infraction
- Remove warning from database: delete_single_warning
- Remove all warnings for a user from database: delete_all_warnings_for_user
- Edit single infraction object: insert_infraction

-- Carrier Table --
- Search database by carrier ID: find_carrier
- Search database by discord ID: find_carrier
- Remove tracked carrier from database: delete_carrier
- Add carrier to the database: insert_carrier
"""

''' -- Infractions Table --'''


# find an infraction in the db
async def find_infraction(searchterm1, searchcolumn1, searchterm2=None, searchcolumn2=None):
    print(f"Called find_infraction with {searchterm1}, {searchcolumn1}, {searchterm2}, {searchcolumn2}")
    """
    Finds all infractions that match given search terms in the specified columns.

    :param searchterm1: First search term to match
    :param searchcolumn1: First DB column to match against
    :param searchterm2: Second search term to match (optional)
    :param searchcolumn2: Second DB column to match against (optional)
    :returns: A list of InfractionData objects
    :rtype: InfractionData
    """

    # Building the SQL query and the tuple of parameters
    sql = "SELECT * FROM infractions WHERE "
    params = []

    # Handling the first column and term
    if searchcolumn1 in [InfractionDbFields.entry_id.value, InfractionDbFields.warned_user.value,
                         InfractionDbFields.warning_moderator.value]:
        sql += f"{searchcolumn1} = ?"
        params.append(searchterm1)
    else:
        sql += f"{searchcolumn1} LIKE ?"
        params.append(f"%{searchterm1}%")

    # Handling the second column and term (if provided)
    if searchterm2 is not None and searchcolumn2 is not None:
        if searchcolumn2 in [InfractionDbFields.entry_id.value, InfractionDbFields.warned_user.value,
                             InfractionDbFields.warning_moderator.value]:
            sql += f" AND {searchcolumn2} = ?"
            params.append(searchterm2)
        else:
            sql += f" AND {searchcolumn2} LIKE ?"
            params.append(f"%{searchterm2}%")

    # Executing the SQL statement
    infraction_db.execute(sql, tuple(params))

    infraction_data = [InfractionData(infraction) for infraction in infraction_db.fetchall()]
    # for infraction in infraction_data:
    #     print(infraction)  # calls the __str__ method to print the contents of the instantiated class object

    return infraction_data


# Remove warning from database
async def delete_single_warning(entry_id):
    """
    Function to lookup a warning by its Primary Key and delete it.
    """
    print(f"Attempting to delete entry {entry_id}.")
    try:
        await infraction_db_lock.acquire()
        infraction_db.execute(f"DELETE FROM infractions WHERE entry_id = {entry_id}")
        infraction_conn.commit()
    finally:
        infraction_db_lock.release()

    return


# Remove all warnings for a user
async def delete_all_warnings_for_user(warned_user):
    """
    Function to delete all entries matching a given warned user ID.
    """
    print(f"Attempting to delete all entries for {warned_user}.")
    try:
        await infraction_db_lock.acquire()
        infraction_db.execute(f"DELETE FROM infractions WHERE warned_user = {warned_user}")
        infraction_conn.commit()
    finally:
        infraction_db_lock.release()
    return


# Insert an infraction into the database
async def insert_infraction(warned_user, warning_moderator, warning_time, rule_broken=None, warning_reason=None,
                            thread_id=None):
    """
    Inserts a new infraction into the infractions table.

    :param int warned_user: ID of the user being warned
    :param int warning_moderator: ID of the moderator issuing the warning
    :param int warning_time: Unix timestamp of when the warning was issued
    :param int rule_broken: (Optional) ID of the rule broken, if any
    :param str warning_reason: (Optional) Reason for the warning
    :param int thread_id: (Optional) Thread ID, if any
    :returns: The row ID of the newly inserted infraction
    :rtype: int
    """

    print(f"Inserting infraction for user {warned_user} by moderator {warning_moderator}.")

    try:
        await infraction_db_lock.acquire()

        infraction_db.execute(
            f"INSERT INTO infractions (warned_user, warning_moderator, warning_time, rule_broken, warning_reason, "
            f"thread_id) VALUES (?, ?, ?, ?, ?, ?)",
            (warned_user, warning_moderator, warning_time, rule_broken, warning_reason, thread_id)
        )
        infraction_conn.commit()

        # Fetch the ID of the last row inserted (this is our infraction's entry ID)
        entry_id = infraction_db.lastrowid
    finally:
        infraction_db_lock.release()

    print(f"Infraction inserted with entry ID {entry_id}.")
    return entry_id


async def edit_infraction(entry_id, warned_user=None, warning_moderator=None, warning_time=None, rule_broken=None,
                          warning_reason=None, thread_id=None):
    """
    Edits an existing infraction in the infractions table.

    :param int entry_id: ID of the infraction entry to be edited
    :param int warned_user: (Optional) New ID of the user being warned
    :param int warning_moderator: (Optional) New ID of the moderator issuing the warning
    :param int warning_time: (Optional) New Unix timestamp of when the warning was issued
    :param int rule_broken: (Optional) New ID of the rule broken, if any
    :param str warning_reason: (Optional) New reason for the warning
    :param int thread_id: (Optional) New thread ID, if any
    :returns: True if the infraction was successfully updated, False otherwise
    :rtype: bool
    """

    print(f"Editing infraction with entry ID {entry_id}.")

    try:
        await infraction_db_lock.acquire()

        # Prepare the SET part of the SQL command
        updates = []
        parameters = []
        if warned_user is not None:
            updates.append("warned_user = ?")
            parameters.append(warned_user)
        if warning_moderator is not None:
            updates.append("warning_moderator = ?")
            parameters.append(warning_moderator)
        if warning_time is not None:
            updates.append("warning_time = ?")
            parameters.append(warning_time)
        if rule_broken is not None:
            updates.append("rule_broken = ?")
            parameters.append(rule_broken)
        if warning_reason is not None:
            updates.append("warning_reason = ?")
            parameters.append(warning_reason)
        if thread_id is not None:
            updates.append("thread_id = ?")
            parameters.append(thread_id)

        set_command = ", ".join(updates)
        parameters.append(entry_id)

        # Check if there is anything to update
        if not updates:
            print("No updates provided.")
            return False

        # Execute the update command
        infraction_db.execute(
            f"UPDATE infractions SET {set_command} WHERE entry_id = ?",
            tuple(parameters)
        )
        infraction_conn.commit()

    finally:
        infraction_db_lock.release()

    print("Infraction updated.")
    return True


''' -- Tow Truck Table -- '''


async def insert_carrier(carrier_name: str, carrier_id: str, carrier_position: str, in_game_carrier_owner: str,
                         discord_user: int = None, user_roles: str = None):
    """
    Inserts a new carrier into the tow truck table
    """
    print(f'Inserting infraction for carrier {carrier_name} ({carrier_id})')

    try:
        await infraction_db_lock.acquire()

        infraction_db.execute(
            f"INSERT INTO tow_truck (carrier_name, carrier_id, carrier_position, in_game_carrier_owner, discord_user, "
            f"user_roles) VALUES (?, ?, ?, ?, ?, ?)",
            (carrier_name, carrier_id, carrier_position, in_game_carrier_owner, discord_user, user_roles)
        )

        infraction_conn.commit()

    finally:
        infraction_db_lock.release()

    print(f"Carrier {carrier_id} inserted into database")


async def find_carrier(searchterm1, searchcolumn1, searchterm2=None, searchcolumn2=None):
    print(f"Called find_carrier with {searchterm1}, {searchcolumn1}, {searchterm2}, {searchcolumn2}")

    # Building the SQL query and the tuple of parameters
    sql = "SELECT * FROM tow_truck WHERE "
    params = []

    # Handling the first column and term
    if searchcolumn1 in [CarrierDbFields.entry_id.value, CarrierDbFields.carrier_id.value,
                         CarrierDbFields.discord_user.value]:
        sql += f"{searchcolumn1} = ?"
        params.append(searchterm1)
    else:
        sql += f"{searchcolumn1} LIKE ?"
        params.append(f"%{searchterm1}%")

    # Handling the second column and term (if provided)
    if searchterm2 is not None and searchcolumn2 is not None:
        if searchcolumn2 in [CarrierDbFields.entry_id.value, CarrierDbFields.carrier_id.value,
                             CarrierDbFields.discord_user.value]:
            sql += f" AND {searchcolumn2} = ?"
            params.append(searchterm2)
        else:
            sql += f" AND {searchcolumn2} LIKE ?"
            params.append(f"%{searchterm2}%")

    # Executing the SQL statement
    infraction_db.execute(sql, tuple(params))

    carrier_data = [TowTruckData(carrier) for carrier in infraction_db.fetchall()]
    # for infraction in infraction_data:
    #     print(infraction)  # calls the __str__ method to print the contents of the instantiated class object

    return carrier_data


async def delete_carrier(entry_id):
    """
    Function to lookup a carrier by its Primary Key and delete it.
    """
    print(f"Attempting to delete entry {entry_id}.")
    try:
        await infraction_db_lock.acquire()
        infraction_db.execute(f"DELETE FROM tow_truck WHERE entry_id = {entry_id}")
        infraction_conn.commit()
    finally:
        infraction_db_lock.release()

    return


async def get_all_carriers():
    print('Getting all carriers')
    try:
        await infraction_db_lock.acquire()
        infraction_db.execute("SELECT * FROM tow_truck")
        carrier_data = [TowTruckData(carrier) for carrier in infraction_db.fetchall()]
    finally:
        infraction_db_lock.release()

    return carrier_data


async def edit_carrier(entry_id, carrier_name=None, carrier_id=None, carrier_position=None, in_game_carrier_owner=None,
                       discord_user=None, user_roles=None):
    print(f"Editing infraction with entry ID {entry_id}.")

    try:
        await infraction_db_lock.acquire()

        # Prepare the SET part of the SQL command
        updates = []
        parameters = []
        if carrier_name is not None:
            updates.append("carrier_name = ?")
            parameters.append(carrier_name)
        if carrier_id is not None:
            updates.append("carrier_id = ?")
            parameters.append(carrier_id)
        if carrier_position is not None:
            updates.append("carrier_position = ?")
            parameters.append(carrier_position)
        if in_game_carrier_owner is not None:
            updates.append("in_game_carrier_owner = ?")
            parameters.append(in_game_carrier_owner)
        if discord_user is not None:
            updates.append("discord_user = ?")
            parameters.append(discord_user)
        if user_roles is not None:
            updates.append("user_roles = ?")
            parameters.append(user_roles)

        set_command = ", ".join(updates)
        parameters.append(entry_id)

        # Check if there is anything to update
        if not updates:
            print("No updates provided.")
            return False

        # Execute the update command
        infraction_db.execute(
            f"UPDATE tow_truck SET {set_command} WHERE entry_id = ?",
            tuple(parameters)
        )
        infraction_conn.commit()

    finally:
        infraction_db_lock.release()

    print("Carrier updated.")
    return True
