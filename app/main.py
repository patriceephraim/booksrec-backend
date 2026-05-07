"""
FastAPI app — the HTTP surface of BooksRec.

This module wires routes to the AI service. It does NOT import the
anthropic SDK directly. All AI logic is delegated to ai_service.recommend_books.

Endpoints:
    GET  /api/health      → liveness check (used by deployment platforms)
    POST /api/recommend   → take quiz answers, return book recommendations
"""

import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.ai_service import AIServiceError, recommend_books
from app.models import QuizAnswers, RecommendationResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="BooksRec API",
    description="AI-powered book recommendations.",
    version="0.1.0",
)

# CORS — Cross-Origin Resource Sharing.
# By default browsers block JS on one domain from calling APIs on another.
# Our Next.js dev server runs on http://localhost:3000 and needs to call
# this backend on http://localhost:8000, so we explicitly allow it.
# In production we'll add the real frontend URL here.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Liveness check. Cheap, no AI call. Hosting platforms ping this."""
    return {"status": "ok"}


@app.post("/api/recommend", response_model=RecommendationResponse)
async def recommend(quiz: QuizAnswers) -> RecommendationResponse:
    """
    Take quiz answers, return 3-5 personalized book recommendations.

    FastAPI auto-validates `quiz` against the QuizAnswers Pydantic model.
    If the body is missing fields or has bad types, the user gets a 422
    with details — we never even reach this function body.
    """
    try:
        books = await recommend_books(quiz)
    except AIServiceError as e:
        logger.error("AI service failed: %s", e)
        # 503 Service Unavailable — the request was fine, but our
        # downstream (Claude) couldn't deliver. Tells the client to retry.
        raise HTTPException(status_code=503, detail=str(e))

    return RecommendationResponse(recommendations=books)