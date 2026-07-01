"""
Central configuration for AgentForge.

All runtime settings are pulled from environment variables so the same
image can be deployed anywhere (local Docker, cloud VM, k8s Job) without
code changes -- a small thing recruiters notice.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

class Settings:
    # --- LLM provider -------------------------------------------------
    # Groq's API is OpenAI-compatible and has a genuinely free tier with
    # tool-calling support, so AgentForge talks to it via the `openai`
    # SDK pointed at Groq's base_url. Swapping to real OpenAI or another
    # OpenAI-compatible provider later is just an env var change.
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    BASE_URL: str = os.getenv("AGENTFORGE_BASE_URL", "https://api.groq.com/openai/v1")
    MODEL_NAME: str = os.getenv("AGENTFORGE_MODEL", "llama-3.3-70b-versatile")
    MAX_TOKENS: int = int(os.getenv("AGENTFORGE_MAX_TOKENS", "2048"))

    # --- App ------------------------------------------------------------
    APP_NAME: str = "AgentForge"
    DB_PATH: str = os.getenv("AGENTFORGE_DB", str(BASE_DIR / "data" / "agentforge.db"))

    # --- Orchestration ----------------------------------------------------
    MAX_PLAN_STEPS: int = int(os.getenv("AGENTFORGE_MAX_STEPS", "6"))
    MAX_CRITIC_ROUNDS: int = int(os.getenv("AGENTFORGE_MAX_CRITIC_ROUNDS", "2"))
    CODE_EXEC_TIMEOUT: int = int(os.getenv("AGENTFORGE_CODE_TIMEOUT", "8"))

    # --- Memory -----------------------------------------------------------
    MEMORY_TOP_K: int = int(os.getenv("AGENTFORGE_MEMORY_TOPK", "4"))


settings = Settings()

Path(settings.DB_PATH).parent.mkdir(parents=True, exist_ok=True)
