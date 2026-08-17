# ── skyra-vision-service: Configuration Loader ───────────────────────────────
# Loads environment variables using pydantic-settings. All fields are parsed
# once at startup. Downstream modules import the singleton `settings` object.

import os
from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import Field

# Resolve project root relative to this file (src/config.py -> project root)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ENV_FILE = _PROJECT_ROOT / ".env"


class Settings(BaseSettings):
    # ── Server ───────────────────────────────────────────────────────────────
    PORT: int = Field(default=8006, description="FastAPI server port")

    # ── Gemini Vision API ─────────────────────────────────────────────────────
    GEMINI_API_KEY_1: str = Field(default="", description="Primary Gemini Vision API key")
    GEMINI_API_KEY_2: str = Field(default="", description="Fallback Gemini Vision API key")

    # ── Telegram Out-of-Band Alerts ───────────────────────────────────────────
    TELEGRAM_BOT_TOKEN: str = Field(default="", description="Telegram Bot API token from @BotFather")
    TELEGRAM_ADMIN_CHAT_ID: str = Field(default="", description="Telegram Chat ID to deliver analysis results")

    # ── Hotkey Trigger ────────────────────────────────────────────────────────
    HOTKEY_COMBINATION: str = Field(default="ctrl+shift+f9", description="Global hotkey trigger combination")

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }

    @property
    def active_gemini_key(self) -> str:
        """Returns the first available Gemini API key."""
        if self.GEMINI_API_KEY_1:
            return self.GEMINI_API_KEY_1
        if self.GEMINI_API_KEY_2:
            return self.GEMINI_API_KEY_2
        return ""

    @property
    def gemini_configured(self) -> bool:
        return bool(self.active_gemini_key)

    @property
    def telegram_configured(self) -> bool:
        return bool(self.TELEGRAM_BOT_TOKEN and self.TELEGRAM_ADMIN_CHAT_ID)


# Singleton settings instance shared across all modules
settings = Settings()
