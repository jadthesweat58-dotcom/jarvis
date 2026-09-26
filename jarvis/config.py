"""Settings, read from environment variables (and a .env file if present)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass
class Settings:
    anthropic_api_key: str = field(default_factory=lambda: _env("ANTHROPIC_API_KEY"))
    my_name: str = field(default_factory=lambda: _env("MY_NAME", "Sir"))
    timezone: str = field(default_factory=lambda: _env("TIMEZONE", "UTC"))
    home_city: str = field(default_factory=lambda: _env("HOME_CITY"))

    mode: str = field(default_factory=lambda: _env("JARVIS_MODE", "cloud").lower())
    model: str = field(default_factory=lambda: _env("JARVIS_MODEL", "claude-opus-5"))
    effort: str = field(default_factory=lambda: _env("JARVIS_EFFORT", "medium"))
    access_token: str = field(default_factory=lambda: _env("JARVIS_ACCESS_TOKEN"))
    data_dir: Path = field(default_factory=lambda: Path(_env("JARVIS_DATA_DIR", "data")))
    files_root: Path = field(
        default_factory=lambda: Path(_env("JARVIS_FILES_ROOT") or Path.home()).expanduser()
    )

    twilio_account_sid: str = field(default_factory=lambda: _env("TWILIO_ACCOUNT_SID"))
    twilio_auth_token: str = field(default_factory=lambda: _env("TWILIO_AUTH_TOKEN"))
    twilio_phone_number: str = field(default_factory=lambda: _env("TWILIO_PHONE_NUMBER"))
    my_phone_number: str = field(default_factory=lambda: _env("MY_PHONE_NUMBER"))
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL").rstrip("/"))

    @property
    def is_local(self) -> bool:
        return self.mode == "local"

    @property
    def tz(self) -> ZoneInfo:
        return ZoneInfo(self.timezone or "UTC")

    @property
    def twilio_enabled(self) -> bool:
        return bool(self.twilio_account_sid and self.twilio_auth_token and self.twilio_phone_number)

    @property
    def db_path(self) -> Path:
        return self.data_dir / "jarvis.db"


settings = Settings()
