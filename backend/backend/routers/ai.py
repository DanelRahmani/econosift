"""AI summary endpoints — all ON REQUEST only. Results cached in SQLite.

No data gathering — Gemini handles all research from its training data.
This eliminates yfinance rate-limit bottlenecks entirely.
"""

from __future__ import annotations

from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..database import SessionLocal
from ..db_models import AiSummary
from ..services import ai_service

router = APIRouter(prefix="/api/ai", tags=["ai"])


class CompanyRequest(BaseModel):
    ticker: str
    model: str = "gemini-2.0-flash"
    force_regenerate: bool = False


class MacroRequest(BaseModel):
    countries: list[str]
    model: str = "gemini-2.0-flash"
    force_regenerate: bool = False


class DashboardRequest(BaseModel):
    model: str = "gemini-2.0-flash"
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


def _save(summary_type: str, context_key: str, model: str, prompt: str, text: str) -> None:
    """Persist a summary row. Best-effort — failures are logged, not raised."""
    import os, time, sqlite3

    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/axiomfinance.db")
    db_path = db_url.replace("sqlite:///", "")
    now = datetime.utcnow().isoformat()

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


def _response(summary_type: str, context_key: str, model: str, text: str, cached: bool) -> dict:
    return {
        "summary_type": summary_type,
        "context_key": context_key,
        "summary_text": text,
        "model_used": model,
        "created_at": datetime.utcnow().isoformat(),
        "cached": cached,
    }


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/company")
async def ai_company(body: CompanyRequest):
    ticker = body.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required.")

    with SessionLocal() as session:
        if not body.force_regenerate:
            cached = _lookup(session, "company", ticker)
            if cached and cached.summary_text and not cached.summary_text.startswith("Error:"):
                return _response("company", ticker, cached.model_used, cached.summary_text, True)

        prompt = ai_service.build_company_prompt(ticker)
        result = await ai_service.generate_summary(prompt, body.model)
        _save("company", ticker, body.model, prompt, result)
        return _response("company", ticker, body.model, result, False)


@router.post("/macro")
async def ai_macro(body: MacroRequest):
    if not body.countries:
        raise HTTPException(status_code=400, detail="At least one country required.")

    iso_list = [c.strip().upper() for c in body.countries]
    context_key = ",".join(sorted(iso_list))

    with SessionLocal() as session:
        if not body.force_regenerate:
            cached = _lookup(session, "macro", context_key)
            if cached and cached.summary_text and not cached.summary_text.startswith("Error:"):
                return _response("macro", context_key, cached.model_used, cached.summary_text, True)

        prompt = ai_service.build_macro_prompt(iso_list)
        result = await ai_service.generate_summary(prompt, body.model)
        _save("macro", context_key, body.model, prompt, result)
        return _response("macro", context_key, body.model, result, False)


@router.post("/dashboard")
async def ai_dashboard(body: DashboardRequest):
    with SessionLocal() as session:
        if not body.force_regenerate:
            cached = _lookup(session, "dashboard", "daily")
            if cached and cached.summary_text and not cached.summary_text.startswith("Error:"):
                return _response("dashboard", "daily", cached.model_used, cached.summary_text, True)

        prompt = ai_service.build_dashboard_prompt()
        result = await ai_service.generate_summary(prompt, body.model)
        _save("dashboard", "daily", body.model, prompt, result)
        return _response("dashboard", "daily", body.model, result, False)


@router.get("/history/{summary_type}/{context_key}")
async def ai_history(summary_type: str, context_key: str):
    with SessionLocal() as session:
        rows = (
            session.query(AiSummary)
            .filter(AiSummary.summary_type == summary_type, AiSummary.context_key == context_key)
            .order_by(AiSummary.created_at.desc())
            .limit(20)
            .all()
        )
        items = [
            AiHistoryItem(id=r.id or 0, summary_text=r.summary_text, model_used=r.model_used, created_at=r.created_at.isoformat() if r.created_at else "")
            for r in rows
        ]
        return {"items": [i.model_dump() for i in items]}
