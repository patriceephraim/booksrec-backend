"""
Pydantic models for BooksRec.

These define the SHAPES of data flowing through the app.
- QuizAnswers: what comes IN from the user's quiz
- BookRecommendation: what goes OUT to the user
- RecommendationResponse: the wrapper around a list of books

Pydantic enforces these shapes at runtime — invalid data is rejected
automatically with a clear error, before it ever reaches our logic.
"""

from enum import Enum

from pydantic import BaseModel, Field


# Enums 
# Enums lock down valid values. The user cannot send "magical realism" as
# a genre — it has to be one of these exact strings, or Pydantic rejects it.

class Genre(str, Enum):
    fiction = "fiction"
    nonfiction = "nonfiction"
    scifi = "scifi"
    fantasy = "fantasy"
    mystery = "mystery"
    biography = "biography"
    history = "history"
    self_help = "self_help"
    romance = "romance"
    literary = "literary"


class Mood(str, Enum):
    light = "light"
    deep = "deep"
    escapist = "escapist"
    challenging = "challenging"
    comforting = "comforting"


class LengthPreference(str, Enum):
    short = "short"
    medium = "medium"
    long = "long"
    no_preference = "no_preference"


# Input model 

class QuizAnswers(BaseModel):
    """What the user submits from the quiz."""

    favorite_books: list[str] = Field(
        ...,
        min_length=1,
        max_length=5,
        description="1 to 5 books the user has loved.",
    )
    preferred_genres: list[Genre] = Field(
        ...,
        min_length=1,
        description="At least one preferred genre.",
    )
    mood: Mood
    length_preference: LengthPreference
    avoid: list[str] = Field(
        default_factory=list,
        description="Optional things the user wants to avoid (e.g., 'sad endings').",
    )


# Output models 

class BookRecommendation(BaseModel):
    """One recommended book."""

    title: str
    author: str
    year: int = Field(..., ge=1000, le=2100)
    genre: str
    why_recommended: str = Field(
        ...,
        min_length=20,
        description="2-3 sentences explaining why this book fits the user.",
    )
    goodreads_search_url: str


class RecommendationResponse(BaseModel):
    """The full response from POST /api/recommend."""

    recommendations: list[BookRecommendation] = Field(..., min_length=3, max_length=5)