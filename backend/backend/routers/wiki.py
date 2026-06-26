"""Wiki/dictionary router."""
from fastapi import APIRouter, Query
from backend.services.wiki_service import TERMS, CATEGORIES

router = APIRouter(prefix="/api/wiki", tags=["wiki"])


@router.get("/categories")
async def wiki_categories():
    """Return all categories with term counts."""
    counts = {c["key"]: sum(1 for t in TERMS if t["category"] == c["key"]) for c in CATEGORIES}
    return {
        "categories": [{**c, "count": counts[c["key"]]} for c in CATEGORIES],
        "total": len(TERMS),
    }


@router.get("/terms")
async def wiki_terms(
    search: str = Query(default="", description="Search query (matches term name, definition, category)"),
    category: str = Query(default="", description="Filter by category key"),
    limit: int = Query(default=200, ge=1, le=500),
):
    """Search and list wiki terms."""
    q = search.lower().strip()
    results = TERMS

    if category:
        results = [t for t in results if t["category"] == category]

    if q:
        results = [
            t for t in results
            if q in t["term"].lower()
            or q in t["definition"].lower()
            or q in t["category"].lower()
            or any(q in r for r in t.get("related", []))
        ]

    # Return limited results with full definitions
    return {
        "terms": results[:limit],
        "total": len(results),
        "query": search,
        "category": category,
    }


@router.get("/term/{slug}")
async def wiki_term(slug: str):
    """Get a single term by its URL slug."""
    for t in TERMS:
        if t["slug"] == slug:
            return {"term": t, "found": True}
    return {"term": None, "found": False}
