class TowTruckData:

    def __init__(self, info_dict=None):
        """
        Class represents a carrier object as returned from the database.

        carrier_name, carrier_id, in_game_carrier_owner, discord_user

        :param sqlite.Row info_dict: A single row from the sqlite query.
        """
        if info_dict:
            # Convert the sqlite3.Row object to a dictionary
            info_dict = dict(info_dict)
        else:
            info_dict = dict()

        self.entry_id = info_dict.get('entry_id', None)
        self.carrier_name = info_dict.get('carrier_name', None)
        self.carrier_id = info_dict.get('carrier_id', None)
        self.carrier_position = info_dict.get('carrier_position', None)
        self.in_game_carrier_owner = info_dict.get('in_game_carrier_owner', None)
        self.discord_user = info_dict.get('discord_user', None)
        self.user_roles = info_dict.get('user_roles', None)

    def to_dictionary(self):
        """
        Formats the carrier data into a dictionary for easy access.

        :returns: A dictionary representation for the carrier data.
        :rtype: dict
        """
        response = {}
        for key, value in vars(self).items():
            if value is not None:
                response[key] = value
        return response

    def __str__(self):
        """
        Overloads str to return a readable object

        :rtype: str
        """
        return 'InfractionData: entry_id:{0.entry_id} carrier_name:{0.carrier_name} carrier_id:{0.carrier_id} ' \
               'carrier_position: {0.carrier_position} in_game_carrier_owner:{0.in_game_carrier_owner} ' \
               'discord_user:{0.discord_user} user_roles:{0.user_roles}'.format(self)

    def __bool__(self):
        """
        Override boolean to check if any values are set, if yes then return True, else False, where false is an empty
        class.

        :rtype: bool
        """
        return any([value for key, value in vars(self).items() if value])
