import io
import os
from pathlib import Path
from importlib import util

from setuptools import setup

NAMESPACE = 'ptn'
COMPONENT = 'modbot'

here = Path().absolute()

# Bunch of things to allow us to dynamically load the metadata file in order to read the version number.
# This is really overkill but it is better code than opening, streaming and parsing the file ourselves.

metadata_name = f'{NAMESPACE}.{COMPONENT}._metadata'
spec = util.spec_from_file_location(metadata_name, os.path.join(here, NAMESPACE, COMPONENT, '_metadata.py'))
metadata = util.module_from_spec(spec)
spec.loader.exec_module(metadata)

# load up the description field
with io.open(os.path.join(here, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name=f'{NAMESPACE}.{COMPONENT}',
    version=metadata.__version__,
    packages=[
        'ptn.modbot', # core
        'ptn.modbot.botcommands', # user interactions
        'ptn.modbot.database', # database
        'ptn.modbot.modules',
        'ptn.modbot.classes'
        ],
    description='Pilots Trade Network Moderator Assistance Bot',
    long_description=long_description,
    author='Charles Tosh',
    url='',
    install_requires=[
        'aiohttp==3.9.2',
        'aiosignal==1.3.1',
        'async-timeout==4.0.3',
        'attrs==23.1.0',
        'certifi==2023.7.22',
        'charset-normalizer==3.3.0',
        'DateTime==4.3',
        'discord.py>=2.3.2',
        'frozenlist==1.4.0',
        'idna==3.4',
        'multidict==6.0.4',
        'python-dateutil==2.8.2',
        'python-dotenv==0.15.0',
        'pytz==2023.3.post1',
        'requests==2.31.0',
        'six==1.16.0',
        'urllib3==2.0.7',
        'yarl==1.9.2',
        'zope.interface==6.1'
    ],
    entry_points={
        'console_scripts': [
            'modbot=ptn.modbot.application:run',
        ],
    },
    license='None',
    keyword='PTN',
    project_urls={
        "Source": "https://github.com/PilotsTradeNetwork/modbot",
    },
    python_required='>=3.10',
)
