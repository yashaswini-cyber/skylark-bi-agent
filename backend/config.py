from pathlib import Path

from dotenv import load_dotenv


ENV_PATH = Path(__file__).resolve().parent / ".env"
load_dotenv(ENV_PATH)


class ConfigError(RuntimeError):
    """Raised when required configuration is missing."""


def _required_env(name: str) -> str:
    from os import getenv

    value = getenv(name)
    if not value:
        raise ConfigError(f"Missing required environment variable: {name}")
    return value


MONDAY_API_TOKEN = _required_env("MONDAY_API_TOKEN")
DEALS_BOARD_ID = _required_env("DEALS_BOARD_ID")
WORK_ORDERS_BOARD_ID = _required_env("WORK_ORDERS_BOARD_ID")
GEMINI_API_KEY = _required_env("GEMINI_API_KEY")
