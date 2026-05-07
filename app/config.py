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

load_dotenv()


def _require(name: str) -> str:
    """Read an env var, fail fast with a clear message if it's missing."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(
            f"{name} is not set. Copy .env.example to .env and fill it in."
        )
    return value


# AI
ANTHROPIC_API_KEY = _require("ANTHROPIC_API_KEY")
MODEL = "claude-haiku-4-5"
MAX_TOKENS = 2048

# Auth (Clerk)
CLERK_SECRET_KEY = _require("CLERK_SECRET_KEY")
CLERK_JWKS_URL = _require("CLERK_JWKS_URL")

# Database (Supabase)
SUPABASE_URL = _require("SUPABASE_URL")
SUPABASE_SECRET_KEY = _require("SUPABASE_SECRET_KEY")