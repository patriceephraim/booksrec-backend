"""
FastAPI app — the HTTP surface of BooksRec.

Endpoints:
    GET  /api/health      → liveness check (no auth)
    POST /api/recommend   → quiz → book recommendations (no auth)
    GET  /api/me          → who am I? (auth required) — used to test JWTs
    POST /api/save        → save a book to my list (auth required)
    GET  /api/saved       → list my saved books (auth required)
"""

import logging

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.ai_service import AIServiceError, recommend_books
from app.auth import get_current_user
from app.database import list_saved_books, save_book
from app.models import BookRecommendation, QuizAnswers, RecommendationResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BooksRec API",
    description="AI-powered book recommendations.",
    version="0.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Public endpoints ------------------------------------------------------

@app.get("/api/health")
async def health() -> dict[str, str]:
    """Liveness check. No auth, no AI call. Used by deploy platforms."""
    return {"status": "ok"}


@app.post("/api/recommend", response_model=RecommendationResponse)
async def recommend(quiz: QuizAnswers) -> RecommendationResponse:
    """Quiz → 3-5 personalized book recommendations. No auth required."""
    try:
        books = await recommend_books(quiz)
    except AIServiceError as e:
        logger.error("AI service failed: %s", e)
        raise HTTPException(status_code=503, detail=str(e))

    return RecommendationResponse(recommendations=books)


# --- Protected endpoints ---------------------------------------------------
# Any route below uses Depends(get_current_user). FastAPI runs the auth
# check first; the route body never executes unless the JWT is valid.

@app.get("/api/me")
async def me(user_id: str = Depends(get_current_user)) -> dict[str, str]:
    """Return the authenticated user's Clerk ID. Useful for verifying auth."""
    return {"user_id": user_id}


@app.post("/api/save")
async def save(
    book: BookRecommendation,
    user_id: str = Depends(get_current_user),
) -> dict:
    """Save a book to the current user's list."""
    saved = save_book(user_id=user_id, book=book)
    return {"saved": saved}


@app.get("/api/saved")
async def saved(user_id: str = Depends(get_current_user)) -> dict:
    """List all books saved by the current user."""
    books = list_saved_books(user_id=user_id)
    return {"books": books}