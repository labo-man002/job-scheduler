from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Resolved by this file's own location, not the caller's cwd -- works whether
# commands run from the repo root or from backend/, and regardless of whether
# .env lives at the repo root or was moved into backend/.
_BACKEND_DIR = Path(__file__).resolve().parent.parent
_REPO_ROOT = _BACKEND_DIR.parent


class Settings(BaseSettings):
    database_hostname: str
    database_port: str
    database_password: str
    database_name: str
    database_username: str
    model_config = SettingsConfigDict(env_file=(_REPO_ROOT / ".env", _BACKEND_DIR / ".env"))



settings = Settings()