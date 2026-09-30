"""AI summary endpoints — all ON REQUEST only. Results cached in SQLite.

No data gathering — Gemini handles all research from its training data.
This eliminates yfinance rate-limit bottlenecks entirely.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import provenance as pv
from ..database import SessionLocal
from ..db_models import AiSummary
from ..services import ai_service

router = APIRouter(prefix="/api/ai", tags=["ai"])


def _utcnow() -> datetime:
    """Naive UTC now — matches AiSummary.created_at, which is stored naive."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class CompanyRequest(BaseModel):
    ticker: str
    model: str = "gemini-2.5-flash"
    force_regenerate: bool = False


class MacroRequest(BaseModel):
    countries: list[str]
    model: str = "gemini-2.5-flash"
    force_regenerate: bool = False


class DashboardRequest(BaseModel):
    model: str = "gemini-2.5-flash"
    force_regenerate: bool = False


class AiHistoryItem(BaseModel):
    id: int
    summary_text: str
    model_used: str
    created_at: str


# ─── Helpers ─────────────────────────────────────────────────────────────────


def _lookup(session, summary_type: str, context_key: str) -> AiSummary | None:
    return (
        session.query(AiSummary)
        .filter(AiSummary.summary_type == summary_type, AiSummary.context_key == context_key)
        .order_by(AiSummary.created_at.desc())
        .first()
    )


def _cached_lookup(summary_type: str, context_key: str) -> AiSummary | None:
    """Session-owning lookup, safe to run in a worker thread."""
    with SessionLocal() as session:
        return _lookup(session, summary_type, context_key)


def _save(summary_type: str, context_key: str, model: str, prompt: str, text: str) -> None:
    """Persist a summary row. Best-effort — failures are logged, not raised."""
    import os, time, sqlite3

    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/axiomfinance.db")
    db_path = db_url.replace("sqlite:///", "")
    now = _utcnow().isoformat()

    for attempt in range(5):
        try:
            conn = sqlite3.connect(db_path, timeout=15)
            conn.execute(
                "INSERT INTO ai_summary (summary_type, context_key, model_used, summary_text, prompt_sent, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (summary_type, context_key, model, text, prompt, now),
            )
            conn.commit()
            conn.close()
            return
        except Exception:
            if attempt < 4:
                time.sleep(1.5 * (attempt + 1))
            else:
                import logging
                logging.getLogger("uvicorn").warning(f"ai_summary save failed: {summary_type}/{context_key}")
        finally:
            try:
                conn.close()
            except Exception:
                pass


_AI_NOTE = ("Written by the language model from its own training knowledge: EconoSift sends it no "
            "market or macro data, so any figures, dates and the sources it lists are unverified.")


def _response(summary_type: str, context_key: str, model: str, text: str, cached: bool,
              generated_at: datetime | None = None) -> dict:
    out = {
        "summary_type": summary_type,
        "context_key": context_key,
        "summary_text": text,
        "model_used": model,
        "created_at": _utcnow().isoformat(),
        "cached": cached,
    }
    if text.startswith("Error:"):
        return out
    # ``generated_at`` is when a cached summary was actually written.
    observed = generated_at.date().isoformat() if generated_at else None
    stale = summary_type == "dashboard" and generated_at is not None and generated_at.date() < _utcnow().date()
    return pv.attach(out, {"*": pv.ref(
        "gemini", model, f"AI-generated {summary_type} summary", observed=observed,
        flags=["stale"] if stale else [],
        note=_AI_NOTE + (" This daily briefing was generated on an earlier day." if stale else ""))})


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/company")
async def ai_company(body: CompanyRequest):
    ticker = body.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required.")

    if not body.force_regenerate:
        cached = await asyncio.to_thread(_cached_lookup, "company", ticker)
        if cached and cached.summary_text and not cached.summary_text.startswith("Error:"):
            return _response("company", ticker, cached.model_used, cached.summary_text, True, cached.created_at)

    prompt = ai_service.build_company_prompt(ticker)
    result = await ai_service.generate_summary(prompt, body.model)
    await asyncio.to_thread(_save, "company", ticker, body.model, prompt, result)
    return _response("company", ticker, body.model, result, False)


@router.post("/macro")
async def ai_macro(body: MacroRequest):
    if not body.countries:
        raise HTTPException(status_code=400, detail="At least one country required.")

    iso_list = [c.strip().upper() for c in body.countries]
    context_key = ",".join(sorted(iso_list))

    if not body.force_regenerate:
        cached = await asyncio.to_thread(_cached_lookup, "macro", context_key)
        if cached and cached.summary_text and not cached.summary_text.startswith("Error:"):
            return _response("macro", context_key, cached.model_used, cached.summary_text, True, cached.created_at)

    prompt = ai_service.build_macro_prompt(iso_list)
    result = await ai_service.generate_summary(prompt, body.model)
    await asyncio.to_thread(_save, "macro", context_key, body.model, prompt, result)
    return _response("macro", context_key, body.model, result, False)


@router.post("/dashboard")
async def ai_dashboard(body: DashboardRequest):
    if not body.force_regenerate:
        cached = await asyncio.to_thread(_cached_lookup, "dashboard", "daily")
        if cached and cached.summary_text and not cached.summary_text.startswith("Error:"):
            return _response("dashboard", "daily", cached.model_used, cached.summary_text, True, cached.created_at)

    prompt = ai_service.build_dashboard_prompt()
    result = await ai_service.generate_summary(prompt, body.model)
    await asyncio.to_thread(_save, "dashboard", "daily", body.model, prompt, result)
    return _response("dashboard", "daily", body.model, result, False)


@router.get("/history/{summary_type}/{context_key}")
async def ai_history(summary_type: str, context_key: str):
    def _fetch() -> list[AiHistoryItem]:
        with SessionLocal() as session:
            rows = (
                session.query(AiSummary)
                .filter(AiSummary.summary_type == summary_type, AiSummary.context_key == context_key)
                .order_by(AiSummary.created_at.desc())
                .limit(20)
                .all()
            )
            return [
                AiHistoryItem(id=r.id or 0, summary_text=r.summary_text, model_used=r.model_used, created_at=r.created_at.isoformat() if r.created_at else "")
                for r in rows
            ]

    items = await asyncio.to_thread(_fetch)
    return pv.attach({"items": [i.model_dump() for i in items]}, {"*": pv.ref(
        "gemini", None, "Previously generated AI summaries",
        note=_AI_NOTE + " Each item names its model in model_used and its generation time in created_at.")})
