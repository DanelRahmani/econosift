"""Cross-border finance router — bilateral international banking claims."""
from fastapi import APIRouter

router = APIRouter(prefix="/api/crossborder", tags=["crossborder"])

_SOURCE = "BIS Locational Banking Statistics (LBS)"


@router.get("/claims")
async def crossborder_claims():
    """Largest bilateral cross-border bank claims, latest quarter (BIS LBS).

    When BIS is unreachable the response says so. It used to substitute World
    Bank merchandise trade (% of GDP) and present those percentages as USD
    bank claims (audit D-28).
    """
    from ..sources.source_bis import get_crossborder_claims
    data = await get_crossborder_claims()
    if not data.get("claims"):
        return {"claims": [], "source": _SOURCE, "asOf": None, "status": "unavailable"}
    return {
        "claims": data["claims"],
        "totalUsd": data.get("totalUsd"),
        "pairCount": data.get("pairCount"),
        "source": _SOURCE,
        "asOf": data["period"],
    }
