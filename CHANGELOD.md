# Changelog
## 1.3.8
### TowTruckCommands.py
- towing a member now pings/re-pings the tow truck role in the tow truck channel
- towing a member who already has tow truck will skip role functions, role ping, and infraction
- added guild constant to `release_carrier`
- combined `release_carrier` inputs to one with regex and input screening
- added logic to handle and transfer roles between carriers on release
- added @everyone skip to release
- added carrier_id to member carrier release spam embed

## database.py
- added function to edit carrier object in database
## 1.3.7
### TowTruckCommands.py
- checks to stop tow command if bot cannot edit a member's roles

## 1.3.6
### TowTruckCommands.py
- Removed `discord_user` param for `tow_carrier` in favor of regex match form `carrier_owner`

### Helpers.py
- Carrier owner in tow lot carrier string is now either member mention or string, not both
## 1.3.5
### TowTruckCommands.py
- added prevention of council, mods, and bots being towed
- the bird

## 1.3.2
### Helpers.py
- changed tow truck embed fields to not be inline

## 1.3.1
### TowTruckCommands.py
- fixed improper ending calls upon impoun

## 1.3.0: Tow Truck Update
### constants.py
- added CCO WMM channel and tow truck role

### database.py
- added tow truck table and interaction functions

### Helpers.py
- added functions for tow truck embed building
### ModCommands.py
- removed error handler from file in favor of import
- added link to dyno hit in 'warning from report'
### Created TowTruckCommands.py
### Created TowTruckData.py
## 1.2.6
- Removed deletion of Dyno hits
## 1.2.5
- Removed search ability for dyno search for members over a year old, now gives embed with search text for search bar
## 1.2.4
- Allowed Atlas to use Report to Mods
- Removed mod ping and added removal of message for mods to Report to Mods
## 1.2.3
- Added time range to dyno search
## 1.2.2
- Fixed all dyno search bugs
## 1.2.0
- Added search function for dyno hits
## 1.1.0
- Added Edit function to infractions
- Fixed spam embed not posting upon warning

## 1.0.4
- Corrected testing data path to ptn/modbot/data
- Mod summons now works when channel is empty (lol)
- Tweak mod summon feedback message
- [#41](https://github.com/PilotsTradeNetwork/ModBot/issues/41) Include reason in message content on mod pings
- Fixed rule command not reporting channel properly


## 1.0.3
- [#37](https://github.com/PilotsTradeNetwork/ModBot/issues/37) Changed bot connection message channel


## 1.0.2
- Added filter for non-message warnings
- Updated formatting of infractions
- Removed more print statements


## 1.0.1
- Added message displaying with notification on warning in evidence Updated deletion logic to not delete threads when there are member messages in them Removed unnecessary prin messages
- Added timestamping and linking to summon command
- Closes [#29](https://github.com/PilotsTradeNetwork/ModBot/issues/29) [#30](https://github.com/PilotsTradeNetwork/ModBot/issues/30) [#28](https://github.com/PilotsTradeNetwork/ModBot/issues/28) [#27](https://github.com/PilotsTradeNetwork/ModBot/issues/27)


## 1.0.0
- Initial release
