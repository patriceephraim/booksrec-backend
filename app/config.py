"""
Configuration — loads environment variables once, exposes them as constants.

Why centralize this? Two reasons:
1. If a required env var is missing, we fail fast at startup with a clear
   error, instead of crashing on the first user request.
2. If we ever need to change how secrets are loaded (e.g., AWS Secrets
   Manager later), we change it in one place.
"""

import os

from dotenv import load_dotenv

load_dotenv()  # reads .env into os.environ

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
if not ANTHROPIC_API_KEY:
    raise RuntimeError(
        "ANTHROPIC_API_KEY is not set. Copy .env.example to .env and add your key."
    )

# Model + cost knobs in one place so we can tune them without hunting.
MODEL = "claude-haiku-4-5"
MAX_TOKENS = 2048