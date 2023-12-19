"""
The Python script that starts the bot.

"""

# import libraries
import asyncio
import os

from ptn.modbot.botcommands.TowTruckCommands import TowTruckCommands
# import build functions
from ptn.modbot.database.database import build_database_on_startup

from ptn.modbot.bot import bot

# import bot Cogs
from ptn.modbot.botcommands.ModCommands import ModCommands
from ptn.modbot.botcommands.DatabaseInteraction import DatabaseInteraction

# import bot object, token, production status
from ptn.modbot.constants import TOKEN, _production, DATA_DIR

print(f"Data dir is {DATA_DIR} from {os.path.join(os.getcwd(), 'ptn', 'modbot', DATA_DIR, '.env')}")

print(f'PTN ModBot is connecting against production: {_production}.')


def run():
    asyncio.run(modbot())


async def modbot():
    async with bot:
        build_database_on_startup()
        await bot.add_cog(ModCommands(bot))
        await bot.add_cog(DatabaseInteraction(bot))
        await bot.add_cog(TowTruckCommands(bot))
        await bot.start(TOKEN)


if __name__ == '__main__':
    """
    If running via `python ptn/modbot/application.py
    """
    run()
