"""
Constants used throughout ModBot.

Depends on: nothing
"""

# libraries
import ast
import os
import discord
from discord.ext import commands
from dotenv import load_dotenv


# Define whether the bot is in testing or live mode. Default is testing mode.
_production = ast.literal_eval(os.environ.get('PTN_MODBOT_SERVICE', 'False'))

# define paths
TESTING_DATA_PATH = os.path.join(os.getcwd(), 'ptn', 'modbot', 'data') # defines the path for use in a local testing environment
DATA_DIR = os.getenv('PTN_MODBOT_DATA_DIR', TESTING_DATA_PATH)

# database paths
DB_PATH = os.path.join(DATA_DIR, 'database') # path to database directory
INFRACTIONS_DB_PATH = os.path.join(DATA_DIR, 'database', 'infractions.db') # path to infractions database
BACKUP_DB_PATH = os.path.join(DATA_DIR, 'database', 'backups') # path to use for direct DB backups
SQL_PATH = os.path.join(DATA_DIR, 'database', 'db_sql') # path to use for SQL dumps


# Get the discord token from the local .env file. Deliberately not hosted in the repo or Discord takes the bot down
# because the keys are exposed. DO NOT HOST IN THE PUBLIC REPO.
# load_dotenv(os.path.join(DATA_DIR, '.env'))
load_dotenv(os.path.join(DATA_DIR, '.env'))


# define bot token
TOKEN = os.getenv('MODBOT_DISCORD_TOKEN_PROD') if _production else os.getenv('MODBOT_DISCORD_TOKEN_TESTING')


# define bot object
bot = commands.Bot(command_prefix='mod!', intents=discord.Intents.all())


# Production variables
PROD_DISCORD_GUILD = 800080948716503040 # PTN server ID
PROD_CHANNEL_EVIDENCE = 845362369739096174 # PTN mod-evidence channel
PROD_CHANNEL_BOTSPAM = 801258393205604372 # PTN bot-spam channel
PROD_CHANNEL_RULES = 800098038727180352 # PTN rules channel
PROD_ROLE_COUNCIL = 800091021852803072 # PTN Council role
PROD_ROLE_MOD = 813814494563401780 # PTN Mod role
PROD_ROLE_SOMMELIER = 838520893181263872 # PTN Sommelier role
PROD_RULES_MESSAGE = 1067751625529229373 # PTN Rules Message - there's probably a better way of doing this
PROD_BC_CATEGORIES = [1077429676470976512, 1077428970439577710, 838515215950807100] # Admin Area, Wine Carriers, Booze Cruise


# Testing variables
TEST_DISCORD_GUILD = 682302487658496057
TEST_CHANNEL_EVIDENCE = 1160424339468980347
TEST_CHANNEL_BOTSPAM = 1160424363321983066
TEST_CHANNEL_RULES = 770079848827584522
TEST_ROLE_COUNCIL = 1166198689388314714
TEST_ROLE_MOD = 1166198849975627866
TEST_ROLE_SOMMELIER = 1166198981148291102
TEST_RULES_MESSAGE = 1153873171288690738
TEST_BC_CATEGORIES = [1166126363669954560]

# Embed colours
EMBED_COLOUR_ERROR = 0x800000           # dark red
EMBED_COLOUR_QU = 0x00d9ff              # que?
EMBED_COLOUR_OK = 0x80ff80              # we're good here thanks, how are you?


# random gifs and images
error_gifs = [
    'https://media.tenor.com/-DSYvCR3HnYAAAAC/beaker-fire.gif', # muppets
    'https://media.tenor.com/M1rOzWS3NsQAAAAC/nothingtosee-disperse.gif', # naked gun
    'https://media.tenor.com/oSASxe-6GesAAAAC/spongebob-patrick.gif', # spongebob
    'https://media.tenor.com/u-1jz7ttHhEAAAAC/angry-panda-rage.gif' # panda smash
]


# images and icons used in embeds



# define constants based on prod or test environment
def bot_guild():
  return PROD_DISCORD_GUILD if _production else TEST_DISCORD_GUILD

guild_obj = discord.Object(bot_guild())

def channel_evidence():
    return PROD_CHANNEL_EVIDENCE if _production else TEST_CHANNEL_EVIDENCE

def channel_botspam():
    return PROD_CHANNEL_BOTSPAM if _production else TEST_CHANNEL_BOTSPAM

def role_council():
    return PROD_ROLE_COUNCIL if _production else TEST_ROLE_COUNCIL

def role_mod():
    return PROD_ROLE_MOD if _production else TEST_ROLE_MOD

def role_sommelier():
    return PROD_ROLE_SOMMELIER if _production else TEST_ROLE_SOMMELIER

def channel_rules():
    return PROD_CHANNEL_RULES if _production else TEST_CHANNEL_RULES

def rules_message():
    return PROD_RULES_MESSAGE if _production else TEST_RULES_MESSAGE

def bc_categories():
    return PROD_BC_CATEGORIES if _production else TEST_BC_CATEGORIES


any_elevated_role = [role_council(), role_mod()]


def get_guild():
    """
    Return bot guild instance for use in get_member()
    """
    return bot.get_guild(bot_guild())