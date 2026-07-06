from functools import lru_cache
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_ENV_TEXT = """APP_ENV=local
CHAT_PROVIDER=mock
CHAT_MODEL=deepseek-chat
CHAT_REASONING_MODEL=deepseek-reasoner
CHAT_BASE_URL=https://api.deepseek.com
CHAT_API_KEY=
GLM_BASE_URL=https://open.bigmodel.cn/api/paas/v4
GLM_API_KEY=
SPEECH_PROVIDER=whisper-local
SPEECH_MODEL=base
SPEECH_BASE_URL=
SPEECH_API_KEY=
RECORD_SAMPLE_RATE=16000
RECORD_CHANNELS=1
CACHE_FLUSH_SECONDS=5
SUMMARY_CHUNK_CHARS=7000
RAG_CHUNK_CHARS=900
RAG_CHUNK_OVERLAP=120
RAG_TOP_K=5
"""


def _runtime_root() -> Path:
    explicit_root = os.environ.get("MEETING_SKILL_ROOT")
    if explicit_root:
        return Path(explicit_root).resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


ROOT_DIR = _runtime_root()
CONFIG_DIR = ROOT_DIR / "config"
ENV_FILE = CONFIG_DIR / ".env"
ENV_EXAMPLE_FILE = CONFIG_DIR / ".env.example"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
if not ENV_EXAMPLE_FILE.exists():
    ENV_EXAMPLE_FILE.write_text(DEFAULT_ENV_TEXT, encoding="utf-8")
if not ENV_FILE.exists():
    ENV_FILE.write_text(DEFAULT_ENV_TEXT, encoding="utf-8")
load_dotenv(ENV_FILE)


class Settings(BaseSettings):
    app_env: str = "local"
    chat_provider: str = "mock"
    chat_model: str = "deepseek-chat"
    chat_reasoning_model: str = "deepseek-reasoner"
    chat_base_url: str = "https://api.deepseek.com"
    chat_api_key: str = ""
    glm_base_url: str = "https://open.bigmodel.cn/api/paas/v4"
    glm_api_key: str = ""
    speech_provider: str = "whisper-local"
    speech_model: str = "base"
    speech_base_url: str = ""
    speech_api_key: str = ""
    record_sample_rate: int = 16000
    record_channels: int = 1
    cache_flush_seconds: int = 5
    summary_chunk_chars: int = 7000
    rag_chunk_chars: int = 900
    rag_chunk_overlap: int = 120
    rag_top_k: int = 5

    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


def project_path(*parts: str) -> Path:
    return ROOT_DIR.joinpath(*parts)
