class InfractionData:

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
        self.warned_user = info_dict.get('warned_user', None)
        self.warning_moderator = info_dict.get('warning_moderator', None)
        self.warning_time = info_dict.get('warning_time', None)
        self.rule_broken_no = info_dict.get('rule_broken_no', None)
        self.rule_broken_text = info_dict.get('rule_broken_text', None)
        self.warning_reason = info_dict.get('warning_reason', None)
        self.thread_id = info_dict.get('thread_id', None)

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
        return 'InfractionData: entry_id:{0.entry_id} warned_user:{0.warned_user} warning_moderator:{0.warning_moderator} ' \
               'warning_time:{0.warning_time} rule_broken_no:{0.rule_broken_no} rule_broken_text:{0.rule_broken_text} ' \
               'warning_reason:{0.warning_reason} thread_id:{0.thread_id}'.format(self)

    def __bool__(self):
        """
        Override boolean to check if any values are set, if yes then return True, else False, where false is an empty
        class.

        :rtype: bool
        """
        return any([value for key, value in vars(self).items() if value])
