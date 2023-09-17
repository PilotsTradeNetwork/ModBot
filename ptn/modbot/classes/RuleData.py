class RuleData:

    def __init__(self, info_dict=None):
        """
        Class represents an infraction object as returned from the database.

        user, thread ID, datetime warned, warning moderator, rule broken, reason given

        :param sqlite.Row info_dict: A single row from the sqlite query.
        """
        if info_dict:
            # Convert the sqlite3.Row object to a dictionary
            info_dict = dict(info_dict)
        else:
            info_dict = dict()

        self.entry_id = info_dict.get('entry_id', None)
        self.rule_number = info_dict.get('rule_number', None)
        self.rule_title = info_dict.get('rule_title', None)
        self.short_text = info_dict.get('short_text', None)
        self.long_text = info_dict.get('long_text', None)
        self.message_id = info_dict.get('message_id', None)

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
        return 'RuleData: entry_id:{0.entry_id} rule_number:{0.rule_number} rule_title:{0.rule_title} ' \
               'short_text:{0.short_text} long_text:{0.long_text} message_id:{0.message_id}'.format(self)

    def __bool__(self):
        """
        Override boolean to check if any values are set, if yes then return True, else False, where false is an empty
        class.

        :rtype: bool
        """
        return any([value for key, value in vars(self).items() if value])
