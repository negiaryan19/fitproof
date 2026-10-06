class ServiceError(Exception):
    """Public, sanitized error. Never contains credentials or provider response bodies."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message
