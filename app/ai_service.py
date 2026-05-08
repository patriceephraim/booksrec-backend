"""
AI service — the ONLY module that talks to Claude.

Public API:
    recommend_books(quiz: QuizAnswers) -> list[BookRecommendation]

Why this lives in its own module:
- The rest of the app doesn't depend on Anthropic. If we swap providers
  (OpenAI, local model), only this file changes.
- All prompt-engineering decisions live in one place — easy to audit,
  easy to test.
- Validation and retry logic happen here, so callers always get clean,
  validated Python objects or a clear exception.
"""

import json
import logging
from urllib.parse import quote_plus

from anthropic import AsyncAnthropic, APIError
from pydantic import ValidationError

from app.config import ANTHROPIC_API_KEY, MAX_TOKENS, MODEL
from app.models import BookRecommendation, QuizAnswers

logger = logging.getLogger(__name__)

# AsyncAnthropic so we don't block the FastAPI event loop on network I/O.
client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


class AIServiceError(Exception):
    """Raised when the AI service can't produce a valid response."""


#  Tool schema 
# We use Claude's tool-use feature to FORCE structured JSON output.
# Instead of asking Claude "please respond in JSON" and praying, we tell
# Claude: "your only available action is calling this tool, with these
# exact arguments." This eliminates parsing free-text responses.

RECOMMEND_TOOL = {
    "name": "submit_recommendations",
    "description": "Submit a list of 3-5 book recommendations for the user.",
    "input_schema": {
        "type": "object",
        "properties": {
            "books": {
                "type": "array",
                "minItems": 3,
                "maxItems": 5,
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "author": {"type": "string"},
                        "year": {"type": "integer"},
                        "genre": {"type": "string"},
                        "why_recommended": {
                            "type": "string",
                            "description": "2-3 sentences. Reference the user's specific quiz answers.",
                        },
                    },
                    "required": ["title", "author", "year", "genre", "why_recommended"],
                },
            }
        },
        "required": ["books"],
    },
}


SYSTEM_PROMPT = """You are an expert, opinionated bookseller who has read \
widely across every genre. You give personalized recommendations grounded \
in real, published books. You never invent titles or authors.

IMPORTANT — recency: strongly prefer books published from 2010 onwards. \
If the user listed recent bestsellers (e.g. Atomic Habits, Discipline Is \
Destiny, Fourth Wing), they clearly enjoy contemporary books — match that \
energy. Only recommend older books when they are a genuinely exceptional \
fit that nothing modern can match, and even then limit it to one out of \
your 3-5 picks. Do NOT fill recommendations with classics from the 1960s-1990s \
when the user's taste is clearly modern.

When you recommend a book, explain WHY it fits this specific user — \
referencing the books they already love, their stated mood, and what they \
want to avoid. Generic praise like "this is a classic" is forbidden; \
every recommendation must connect to something the user actually said."""


def _build_user_message(quiz: QuizAnswers) -> str:
    """Turn structured quiz answers into a natural prompt for Claude."""
    books_line = (
        f"Books they've loved: {', '.join(quiz.favorite_books)}"
        if quiz.favorite_books
        else "They haven't listed specific books they've loved — work from their genres, themes, and mood."
    )
    themes_line = (
        f"\nThemes they enjoy: {', '.join(quiz.themes)}" if quiz.themes else ""
    )
    style_line = (
        f"\nStory style preference: {quiz.reading_style.replace('_', ' ')}"
        if quiz.reading_style != "no_preference"
        else ""
    )
    avoid_line = (
        f"\nThings to avoid: {', '.join(quiz.avoid)}" if quiz.avoid else ""
    )
    return f"""Recommend 3-5 books for this reader.

{books_line}
Preferred genres: {', '.join(g.value for g in quiz.preferred_genres)}
Mood right now: {quiz.mood.value}
Length preference: {quiz.length_preference.value}{themes_line}{style_line}{avoid_line}

Use the submit_recommendations tool to return your picks."""


async def _call_claude(quiz: QuizAnswers) -> list[dict]:
    """One Claude call. Returns the raw `books` list from the tool call."""
    response = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=[RECOMMEND_TOOL],
        tool_choice={"type": "tool", "name": "submit_recommendations"},
        messages=[{"role": "user", "content": _build_user_message(quiz)}],
    )

    logger.info(
        "Claude usage — input: %d, output: %d tokens",
        response.usage.input_tokens,
        response.usage.output_tokens,
    )

    # Find the tool_use block in the response. With tool_choice forced,
    # there should always be exactly one.
    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_recommendations":
            return block.input["books"]

    raise AIServiceError("Claude did not call the expected tool.")


# Public API 

async def recommend_books(quiz: QuizAnswers) -> list[BookRecommendation]:
    """
    Get book recommendations for a quiz. Validates the LLM output with
    Pydantic and retries once if validation fails.
    """
    last_error: Exception | None = None

    for attempt in (1, 2):
        try:
            raw_books = await _call_claude(quiz)

            # Add the goodreads URL ourselves — don't trust Claude with URL
            # construction, it'll hallucinate slugs.
            for book in raw_books:
                query = quote_plus(f"{book['title']} {book['author']}")
                book["goodreads_search_url"] = (
                    f"https://www.goodreads.com/search?q={query}"
                )

            # Pydantic validates each book. If any field is wrong type,
            # missing, or fails a constraint, this raises ValidationError.
            return [BookRecommendation(**book) for book in raw_books]

        except ValidationError as e:
            logger.warning("Validation failed on attempt %d: %s", attempt, e)
            last_error = e
        except APIError as e:
            logger.error("Anthropic API error on attempt %d: %s", attempt, e)
            last_error = e

    raise AIServiceError(
        f"Failed to produce valid recommendations after 2 attempts: {last_error}"
    )