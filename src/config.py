import toml

class ConfigFile:
    def __init__(self, path):
        self.path = path
        self.config_data = None

    def load(self):
        with open(self.path, 'r', encoding='utf-8') as f:
            self.config_data = toml.load(f)

    def get(self, table, key, default_value=None):
        if self.config_data is None:
            raise Exception('config file is not loaded')
        return self.config_data.get(table, {}).get(key, default_value)

    @staticmethod
    def config(table, key, default_value=None):
        # TODO: 'required' arg 
        def decorator(func):
            @property
            def wrapper(self):
                return self.get(table, key, default_value)
            # Optionally allow setting too:
            # @wrapper.setter
            # def wrapper(self, value):
            #     if not hasattr(self, "_config"):
            #         self._config = {}
            #     self._config.setdefault(table, {})[key] = value
            return wrapper
        return decorator

    # Properties

    @config('fetcher', 'token_filename', default_value='')
    def fetcher_token_filename(self): ...

    @config('fetcher', 'device_idfv', default_value='')
    def fetcher_device_idfv(self): ...

    @config('fetcher', 'device_id', default_value='')
    def fetcher_device_id(self): ...

    @config('database', 'host', default_value='')
    def database_host(self): ...

    @config('database', 'port', default_value='')
    def database_port(self): ...

    @config('database', 'username', default_value='')
    def database_username(self): ...

    @config('database', 'password', default_value='')
    def database_password(self): ...

    @config('database', 'auth_source', default_value='')
    def database_auth_source(self): ...

    @config('database', 'database_name', default_value='')
    def database_database_name(self): ...
