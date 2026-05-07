"""
Supabase client — the ONLY module that talks to the database.

Same pattern as ai_service.py: isolate the dependency in one file. If we
swap Supabase for raw Postgres + SQLAlchemy later, only this file changes.

We use the SECRET (service-role) key, which bypasses Row Level Security.
That's fine — our backend is the security boundary. Every query in this
file is scoped by the user_id we pulled from the verified Clerk JWT.
"""

from supabase import Client, create_client

from app.config import SUPABASE_SECRET_KEY, SUPABASE_URL
from app.models import BookRecommendation

# Create the client once at module load. Reusing the same client across
# requests is a real performance win — connection pooling, no per-request
# handshake.
_client: Client = create_client(SUPABASE_URL, SUPABASE_SECRET_KEY)


def save_book(user_id: str, book: BookRecommendation) -> dict:
    """Save a recommendation for a user. Returns the inserted row."""
    payload = {
        "user_id": user_id,
        "title": book.title,
        "author": book.author,
        "year": book.year,
        "genre": book.genre,
        "why_recommended": book.why_recommended,
        "goodreads_url": book.goodreads_search_url,
    }
    response = _client.table("saved_books").insert(payload).execute()

    # The supabase-py client returns the inserted rows in response.data.
    # We always insert one row, so we return the first (and only) one.
    return response.data[0]


def list_saved_books(user_id: str) -> list[dict]:
    """Return all books saved by this user, newest first."""
    response = (
        _client.table("saved_books")
        .select("*")
        .eq("user_id", user_id)
        .order("saved_at", desc=True)
        .execute()
    )
    return response.data