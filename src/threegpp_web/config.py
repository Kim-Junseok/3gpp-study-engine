"""Local web settings. Model execution deliberately has no activation switch yet."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from threegpp.storage import data_root


@dataclass(frozen=True)
class Settings:
    data_root: Path
    state_root: Path
    password: str
    fixture_mode: bool = False
    secure_cookies: bool = False
    max_meetings: int = 3
    max_sources: int = 20
    max_input_tokens: int = 32768
    max_output_tokens: int = 8192
    timeout_seconds: int = 180

    def __post_init__(self):
        if not self.password:
            raise ValueError("Set THREEGPP_WEB_PASSWORD_FILE or THREEGPP_WEB_PASSWORD before serving")
        if len(self.password) < 12:
            raise ValueError("The web password must contain at least 12 characters")
        for key, value in self.limits.items():
            if value <= 0:
                raise ValueError(f"{key} must be positive")
        source, state = Path(self.data_root).resolve(), Path(self.state_root).resolve()
        if source == state or source.is_relative_to(state) or state.is_relative_to(source):
            raise ValueError("Research corpus and web state must use separate directories")

    @property
    def limits(self):
        return {key: getattr(self, key) for key in (
            "max_meetings", "max_sources", "max_input_tokens",
            "max_output_tokens", "timeout_seconds")}

    @classmethod
    def from_env(cls, *, source=None, state=None, fixture_mode=False):
        secret_file = os.environ.get("THREEGPP_WEB_PASSWORD_FILE")
        password = (Path(secret_file).read_text().rstrip("\r\n") if secret_file
                    else os.environ.get("THREEGPP_WEB_PASSWORD", ""))
        names = ("max_meetings", "max_sources", "max_input_tokens", "max_output_tokens", "timeout_seconds")
        values = {key: int(os.environ.get("THREEGPP_WEB_" + key.upper(),
                          str(cls.__dataclass_fields__[key].default))) for key in names}
        return cls(data_root=Path(source) if source else data_root(),
                   state_root=Path(state or os.environ.get("THREEGPP_WEB_STATE_ROOT", "var/web")),
                   password=password, fixture_mode=fixture_mode,
                   secure_cookies=os.environ.get("THREEGPP_WEB_SECURE_COOKIES") == "1",
                   **values)
