class DomainError(Exception):
    """A rule failed. The service turns this into an HTTP error."""

    def __init__(self, message: str, fields: dict[str, str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.fields = fields or {}
