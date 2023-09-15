"""
Functions relating to databases used by ModBot.

Depends on: constants, ErrorHandler

"""

# libraries
import os

# local classes
from ptn.modbot.classes.InfractionData import InfractionData

# local constants
import ptn.modbot.constants as constants
from ptn.modbot.constants import bot

# local modules
from ptn.modbot.modules.DateString import get_formatted_date_string
from ptn.modbot.modules.ErrorHandler import CustomError, on_generic_error


# ensure all paths function for a clean install
def build_directory_structure_on_startup():
    print("Building directory structure...")
    os.makedirs(constants.DB_PATH, exist_ok=True) # /database - the main database files
    os.makedirs(constants.SQL_PATH, exist_ok=True) # /database/db_sql - DB SQL dumps
    os.makedirs(constants.BACKUP_DB_PATH, exist_ok=True) # /database/backups - db backups
