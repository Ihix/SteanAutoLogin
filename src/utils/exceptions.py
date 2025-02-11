class SteamSwitcherException(Exception):
    def __init__(self, error_code, detail=None):
        self.error_code = error_code
        self.detail = detail
        super().__init__(f"{error_code.message} - {detail if detail else ''}")

class SteamError(SteamSwitcherException):
    pass

class AccountError(SteamSwitcherException):
    pass

class FileError(SteamSwitcherException):
    pass 