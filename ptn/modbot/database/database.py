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
            'infractions': {'obj': infraction_db, 'create': infractions_table_create}
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


# enumerate infraction database columns
class InfractionDbFields(enum.Enum):
    entry_id = "entry_id"
    warned_user = "warned_user"
    warning_moderator = "warning_moderator"
    warning_time = "warning_time"
    rule_broken = "rule_broken"
    warning_reason = "warning_reason"
    thread_id = "thread_id"


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

- Search database by warned user ID: find_infraction
- Search database by entry ID: find_infraction
- Remove warning from database: delete_single_warning
- Remove all warnings for a user from database: delete_all_warnings_for_user
"""


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
