"""Tests for the policy intelligence service (Phase 18A Task 3)."""
import pytest
from unittest.mock import patch, AsyncMock


def _pts(values: list[float]) -> list[dict]:
    from datetime import date, timedelta

    base = date(2023, 1, 1)
    return [{"date": str(base + timedelta(days=30 * i)), "value": v} for i, v in enumerate(values)]


MOCK_CB = {
    "FEDFUNDS": _pts([4.75, 5.00, 5.25, 5.25, 5.00, 4.75, 4.50, 4.50, 4.25, 4.25, 4.00, 4.00, 3.75]),
    "ECBMRRFR": _pts([3.00, 3.50, 4.00, 4.00, 3.75, 3.50, 3.25, 3.25, 3.00, 3.00, 2.75, 2.75, 2.50]),
}


@pytest.mark.asyncio
async def test_policy_tracker_structure():
    with patch(
        "backend.services.policy_service._fetch_cb_series",
        new_callable=AsyncMock,
        return_value=MOCK_CB,
    ):
        from backend.services.policy_service import get_policy_tracker
        result = await get_policy_tracker()

    assert "divergence" in result
    assert "carry_differentials" in result
    assert len(result["divergence"]) >= 2

    fed = next(d for d in result["divergence"] if d["cb"] == "Fed")
    assert "stance" in fed
    assert "change_12m" in fed
    assert fed["stance"] == "easing"  # rate dropped from 4.75 → 3.75 over 12M
