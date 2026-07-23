from __future__ import annotations


class VideoError(Exception):
    """Expected, user-actionable pipeline failure."""

    def __init__(self, code: str, message: str, *, path: str | None = None, hint: str | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.path = path
        self.hint = hint

    def as_dict(self) -> dict[str, str]:
        payload = {"code": self.code, "message": self.message}
        if self.path:
            payload["path"] = self.path
        if self.hint:
            payload["hint"] = self.hint
        return payload
