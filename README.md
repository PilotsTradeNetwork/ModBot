# ModBot
A Discord bot to handle various in-house moderation issues.

## Overview
Bot to handle warning users on mods' behalf, manage individual threads for users in mod-evidence, count total warnings issued.

## Target functions
- ContextCommand (User): view moderator infractions (ephemeral or ping user in thread in mod-evidence)
- ContextCommand (Message): delete and send to user thread in mod-evidence, with option to send warning DM containing message text, time sent, time removed, rule broken (with link to server rules), and reason given by moderator for deletion
- SlashCommand: `/warn`: view moderator infractions, with option to send warning DM as above
- For all warnings, create or append a thread in mod-evidence for warned user with message containing message text, time sent, time removed, rule broken (with link to server rules), moderator who took action, and reason given by moderator for deletion
- append DM replies to user's thread in mod-evidence, tagging moderator who took action
- browsable infactions db: user, thread ID, datetime warned, warning moderator, rule broken, notes
- SlashCommand: `/rule` # - print a rule to a channel
- maintain/link-in to server rules

## Architecture
- Discord.py 2.x
- SQLite db for infractions
