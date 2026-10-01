"""Cross-border finance router — bilateral international banking claims."""
from fastapi import APIRouter

from .. import provenance as pv

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
    period = str(data["period"])
    return pv.attach({
        "claims": data["claims"],
        "totalUsd": data.get("totalUsd"),
        "pairCount": data.get("pairCount"),
        "source": _SOURCE,
        "asOf": data["period"],
    }, {
        "*": pv.ref(
            "bis", "WS_LBS_D_PUB",
            "Locational banking statistics: cross-border claims, all instruments, currencies and sectors",
            units="USD", frequency="quarterly", observed=period,
            note="Claims of banks located in the creditor country on residents of the debtor country. "
                 "Only the newest quarter is kept and only the 60 largest country pairs are listed."),
        "totalUsd": pv.ref(
            "bis", "WS_LBS_D_PUB", "Total cross-border claims, all reporting countries on all counterparties",
            units="USD", frequency="quarterly", observed=period,
            note="BIS's own aggregate series (reporter 5A, counterparty 5J), not the sum of the listed pairs."),
        "pairCount": pv.derived(
            "number of country-to-country pairs with a claim reported in the latest quarter "
            "(BIS aggregates excluded)", ["*"], title="Pairs reporting", observed=period),
    })
