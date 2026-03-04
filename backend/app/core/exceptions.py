class ReconciliationError(Exception):
    pass


class FileParsingError(ReconciliationError):
    pass


class SessionNotFoundError(ReconciliationError):
    pass
