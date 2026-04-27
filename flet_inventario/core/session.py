class Session:
    token = None
    user = None  # dict: {id, username, rol}

    @classmethod
    def set(cls, token, user):
        cls.token = token
        cls.user = user

    @classmethod
    def clear(cls):
        cls.token = None
        cls.user = None
