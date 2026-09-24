"""Verified-memory endpoints (Phase 2: auth).

Semantic memory indexing and retrieval land in later phases; this route
already requires authentication (401 without credentials).
"""
from fastapi import APIRouter

from app.api.deps import CurrentUser

router = APIRouter()


@router.get("/search", summary="Search verified memory (placeholder)")
async def search_memory(query: str, user: CurrentUser) -> dict:
    return {"results": [], "query": query}
