"""AI summary endpoints — all ON REQUEST only. Results cached in SQLite.

Grounded (P1-19): each request gathers the app's own cached data for the page (quote and
valuation, macro snapshot, or the dashboard panels) into an APP DATA block the model must take
its numbers from, and Gemini's Google Search tool supplies news. The search sources and the
app-data sections are stored with the summary and returned with it.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import date, datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .. import provenance as pv
from ..database import SessionLocal
from ..db_models import AiSummary
from ..services import ai_context, ai_service

log = logging.getLogger(__name__)

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


def _save(summary_type: str, context_key: str, model: str, prompt: str, text: str,
          grounding: dict | None = None) -> None:
    """Persist a summary row. Best-effort — failures are logged, not raised."""
    import os, time, sqlite3

    db_url = os.getenv("DATABASE_URL", "sqlite:///./data/axiomfinance.db")
    db_path = db_url.replace("sqlite:///", "")
    now = _utcnow().isoformat()

    for attempt in range(5):
        try:
            conn = sqlite3.connect(db_path, timeout=15)
            conn.execute(
                "INSERT INTO ai_summary (summary_type, context_key, model_used, summary_text, prompt_sent, "
                "created_at, grounding) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (summary_type, context_key, model, text, prompt, now,
                 json.dumps(grounding) if grounding is not None else None),
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


_AI_NOTE_UNGROUNDED = ("Written by the language model from its own training knowledge (generated before "
                       "summaries were grounded): EconoSift sent it no data, so figures and sources are unverified.")
_AI_NOTE = ("Written by the language model. Its numbers are instructed to come only from the EconoSift data "
            "listed in appData (the same cached data as the pages); news and context come from Google Search, "
            "whose sources are in grounding.sources. The model can still misquote: check figures against the panels.")


async def _section(name: str, coro, timeout: float = 120.0):
    """Await one app-data fetch; on failure return (None, reason) so the summary still runs without it."""
    try:
        return await asyncio.wait_for(coro, timeout), None
    except Exception as exc:  # a failed source must not block the summary; it is reported instead
        log.warning("ai summary: %s data unavailable: %s", name, exc)
        return None, f"{name} data could not be loaded ({type(exc).__name__})"


def _grounding_record(result: dict, sections: list[str], unavailable: dict[str, str]) -> dict:
    """What is stored and returned with a summary: the search grounding and the app data used."""
    return {
        "grounding": {k: result.get(k) for k in ("sources", "searchQueries", "searchEntryPoint", "searchUsed",
                                                 "searchNote")},
        "appData": {"asOf": _utcnow().date().isoformat(), "sections": sections, "unavailable": unavailable},
    }


def _response(summary_type: str, context_key: str, model: str, text: str, cached: bool,
              generated_at: datetime | None = None, record: dict | None = None) -> dict:
    out = {
        "summary_type": summary_type,
        "context_key": context_key,
        "summary_text": text,
        "model_used": model,
        # When the text was generated: a cached summary keeps its original time.
        "created_at": (generated_at or _utcnow()).isoformat(),
        "cached": cached,
        # None for summaries generated before grounding existed.
        "grounding": (record or {}).get("grounding"),
        "appData": (record or {}).get("appData"),
    }
    if text.startswith("Error:"):
        return out
    # ``generated_at`` is when a cached summary was actually written.
    observed = generated_at.date().isoformat() if generated_at else None
    stale = summary_type == "dashboard" and generated_at is not None and generated_at.date() < _utcnow().date()
    return pv.attach(out, {"*": pv.ref(
        "gemini", model, f"AI-generated {summary_type} summary", observed=observed,
        flags=["stale"] if stale else [],
        note=(_AI_NOTE if record else _AI_NOTE_UNGROUNDED)
             + (" This daily briefing was generated on an earlier day." if stale else ""))})


def _record_of(row: AiSummary) -> dict | None:
    try:
        return json.loads(row.grounding) if row.grounding else None
    except (TypeError, ValueError):
        return None


async def _generate(summary_type: str, context_key: str, model: str, task: str, facts: dict,
                    sections: list[str], unavailable: dict[str, str]) -> dict:
    result = await ai_service.generate_summary(task, facts, model)
    record = None if result["text"].startswith("Error:") else _grounding_record(result, sections, unavailable)
    await asyncio.to_thread(_save, summary_type, context_key, model, result.get("prompt") or task,
                            result["text"], record)
    return _response(summary_type, context_key, model, result["text"], False, record=record)


# ─── Endpoints ───────────────────────────────────────────────────────────────


@router.post("/company")
async def ai_company(body: CompanyRequest):
    ticker = body.ticker.strip().upper()
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker is required.")

    if not body.force_regenerate:
        cached = await asyncio.to_thread(_cached_lookup, "company", ticker)
        if cached and cached.summary_text and not cached.summary_text.startswith("Error:"):
            return _response("company", ticker, cached.model_used, cached.summary_text, True, cached.created_at,
                             _record_of(cached))

    from . import valuation as valuation_router
    from ..services import yfinance_service as yfs
    (quote, q_err), (full, f_err) = await asyncio.gather(
        _section("quote", asyncio.to_thread(yfs.get_quote, ticker)),
        _section("valuation", valuation_router.full(ticker)))
    unavailable = {k: v for k, v in (("quote", q_err), ("valuation", f_err)) if v}
    facts = {"ticker": ticker, "asOf": _utcnow().date().isoformat(), **ai_context.company_block(quote, full)}
    sections = [s for s in ("quote", "valuation") if s not in unavailable]
    return await _generate("company", ticker, body.model, ai_service.build_company_prompt(ticker), facts,
                           sections, unavailable)


@router.post("/macro")
async def ai_macro(body: MacroRequest):
    if not body.countries:
        raise HTTPException(status_code=400, detail="At least one country required.")

    iso_list = [c.strip().upper() for c in body.countries]
    context_key = ",".join(sorted(iso_list))

    if not body.force_regenerate:
        cached = await asyncio.to_thread(_cached_lookup, "macro", context_key)
        if cached and cached.summary_text and not cached.summary_text.startswith("Error:"):
            return _response("macro", context_key, cached.model_used, cached.summary_text, True, cached.created_at,
                             _record_of(cached))

    from ..services import macro_service
    snapshot, err = await _section("macro snapshot", macro_service.get_snapshot(iso_list, date.today().year))
    unavailable = {"macro snapshot": err} if err else {}
    facts = {"asOf": _utcnow().date().isoformat(), "source": "World Bank WDI, latest year per country",
             "countries": ai_context.macro_block(snapshot)}
    return await _generate("macro", context_key, body.model, ai_service.build_macro_prompt(iso_list), facts,
                           [] if err else ["macro snapshot"], unavailable)


@router.post("/dashboard")
async def ai_dashboard(body: DashboardRequest):
    # One briefing per UTC day: a constant key served the first briefing forever.
    key = f"daily:{_utcnow().date().isoformat()}"
    if not body.force_regenerate:
        cached = await asyncio.to_thread(_cached_lookup, "dashboard", key)
        if cached and cached.summary_text and not cached.summary_text.startswith("Error:"):
            return _response("dashboard", key, cached.model_used, cached.summary_text, True, cached.created_at,
                             _record_of(cached))

    from ..services import breadth_service, feargreed_service, indices_service, movers_service
    names = ("breadth", "indices", "fear & greed", "movers")
    fetched = await asyncio.gather(
        _section("breadth", asyncio.to_thread(breadth_service.breadth, "sp500")),
        _section("indices", asyncio.to_thread(indices_service.global_indices)),
        _section("fear & greed", asyncio.to_thread(feargreed_service.fear_greed)),
        _section("movers", asyncio.to_thread(movers_service.top_movers, "sp500", 5)))
    unavailable = {n: err for n, (_, err) in zip(names, fetched) if err}
    facts = {"asOf": _utcnow().date().isoformat(), **ai_context.dashboard_block(*(d for d, _ in fetched))}
    return await _generate("dashboard", key, body.model, ai_service.build_dashboard_prompt(), facts,
                           [n for n in names if n not in unavailable], unavailable)


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
        note="Earlier summaries; grounding applies only to those generated after P1-19. Each item names its "
             "model in model_used and its generation time in created_at.")})
