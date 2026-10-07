"""AI-powered summary service using Google Gemini (free tier).

All summaries are on-request only — no automatic generation.
Results are cached in the AiSummary DB table and re-served
unless the user explicitly requests regeneration.

Grounding (P1-19, owner chose both): every number comes from an APP DATA block built
from EconoSift's own cached data (``ai_context``), and Gemini's Google Search tool supplies
recent news and context only. The search sources shown to the user are the ones Gemini
reports in ``groundingMetadata``, never a list the model writes itself. If the search tool
is refused, the summary is regenerated from APP DATA alone and says so.
"""

from __future__ import annotations

import json

import httpx

from ..config import GEMINI_API_KEY

AVAILABLE_MODELS = [
    "gemini-2.5-flash",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite",
    "gemini-3.5-flash",
]

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

SYSTEM_PROMPT = (
    "You are an expert financial analyst writing for EconoSift, a self-hosted "
    "investment research platform. Your responses should be concise, data-driven, "
    "and written in plain English. Start with a 2-3 sentence paragraph headline "
    "summarising the key takeaway, then follow with 4-8 bullet points of key insights. "
    "Use % signs for percentages, $ for dollar amounts, and abbreviate large numbers "
    "(e.g. $3.2T, 142B). Be balanced — mention both strengths and risks."
)

_RULES_WITH_SEARCH = (
    "Rules:\n"
    "- Every number you state (prices, changes, ratios, valuations, macro statistics) must come from "
    "APP DATA. You may round. If a figure is not in APP DATA, do not state it.\n"
    "- Use Google Search only for recent news, events and qualitative context (earnings, guidance, "
    "deals, policy decisions). Do not take prices, ratios or statistics from search results.\n"
    "- Do not write a sources list; EconoSift shows the search sources itself."
)
_RULES_NO_SEARCH = (
    "Rules:\n"
    "- Every number you state must come from APP DATA. You may round. If a figure is not in APP DATA, "
    "do not state it.\n"
    "- You have no news source: do not describe recent news, events or releases that are not in APP DATA.\n"
    "- Do not write a sources list."
)

_TIMEOUT = httpx.Timeout(60.0, connect=10.0)  # a grounded call searches first, so allow more than 30 s


def build_prompt(task: str, facts: dict, search: bool) -> str:
    """System prompt + APP DATA (JSON) + grounding rules + the task."""
    return (f"{SYSTEM_PROMPT}\n\nAPP DATA (from EconoSift; JSON):\n"
            f"{json.dumps(facts, ensure_ascii=False, separators=(',', ':'), default=str)}\n\n"
            f"{_RULES_WITH_SEARCH if search else _RULES_NO_SEARCH}\n\nTask: {task}")


def _grounding(candidate: dict) -> dict:
    """Search sources, queries and Google's search-suggestion widget from ``groundingMetadata``."""
    gm = candidate.get("groundingMetadata") or {}
    sources, seen = [], set()
    for chunk in gm.get("groundingChunks") or []:
        web = chunk.get("web") or {}
        uri = web.get("uri")
        if uri and uri not in seen:
            seen.add(uri)
            sources.append({"title": web.get("title") or uri, "uri": uri})
    return {
        "sources": sources,
        "searchQueries": list(gm.get("webSearchQueries") or []),
        "searchEntryPoint": (gm.get("searchEntryPoint") or {}).get("renderedContent"),
    }


async def _call(client: httpx.AsyncClient, model: str, prompt: str, search: bool) -> tuple[int, dict | str]:
    payload: dict = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048, "topP": 0.95},
    }
    if search:
        payload["tools"] = [{"google_search": {}}]
    resp = await client.post(GEMINI_URL.format(model=model), params={"key": GEMINI_API_KEY}, json=payload,
                             headers={"Content-Type": "application/json"})
    if resp.status_code != 200:
        return resp.status_code, _extract_error(resp)
    return 200, resp.json()


def _error(msg: str, prompt: str = "") -> dict:
    return {"text": f"Error: {msg}", "sources": [], "searchQueries": [], "searchEntryPoint": None,
            "searchUsed": False, "searchNote": None, "prompt": prompt}


async def generate_summary(task: str, facts: dict, model: str = "gemini-2.5-flash") -> dict:
    """Generate a summary grounded in ``facts`` (APP DATA) and, when available, Google Search.

    Returns ``{text, sources, searchQueries, searchEntryPoint, searchUsed, searchNote, prompt}``;
    ``text`` starts with "Error:" on failure.
    """
    if not GEMINI_API_KEY:
        return _error("Gemini API key not configured. Add your key on the Admin page.")

    prompt = build_prompt(task, facts, search=True)
    note = None
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            status, data = await _call(client, model, prompt, search=True)
            search_used = status == 200
            if status >= 500:  # Gemini overloaded or down: retrying without search would not help
                return _error(f"Gemini API returned {status} - {data}", prompt)
            if status != 200:
                # The search tool can be refused (400/403: model without grounding; 429: grounding quota
                # spent): answer from APP DATA alone, with rules that forbid news from memory.
                note = f"Google Search was not available ({status}: {data}); this summary uses EconoSift data only."
                prompt = build_prompt(task, facts, search=False)
                status, data = await _call(client, model, prompt, search=False)
                if status != 200:
                    return _error(f"Gemini API returned {status} - {data}", prompt)
    except httpx.TimeoutException:
        return _error(f"Gemini API request timed out after {int(_TIMEOUT.read)} seconds.", prompt)
    except Exception as exc:
        return _error(f"Gemini API call failed - {exc}", prompt)

    candidates = data.get("candidates", [])
    if not candidates:
        reason = (data.get("promptFeedback") or {}).get("blockReason", "No candidates returned")
        return _error(f"Gemini blocked the request - {reason}", prompt)
    parts = (candidates[0].get("content") or {}).get("parts", [])
    text = "".join(p.get("text", "") for p in parts).strip()
    if not text:
        return _error("Gemini returned an empty response.", prompt)
    grounding = _grounding(candidates[0]) if search_used else {"sources": [], "searchQueries": [], "searchEntryPoint": None}
    return {"text": text, **grounding, "searchUsed": search_used, "searchNote": note, "prompt": prompt}


def _extract_error(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        err = data.get("error", {})
        return err.get("message", str(data))
    except Exception:
        return resp.text[:200]


def build_company_prompt(tickers: str | list[str]) -> str:
    """Task for a company summary; the figures come from APP DATA."""
    if isinstance(tickers, list) and len(tickers) > 1:
        names = ", ".join(tickers)
        return (
            f"Give a concise comparative analyst summary of these separate companies: {names}. "
            f"APP DATA lists each ticker's own figures under \"tickers\"; quote each company's numbers only "
            f"from its own entry and never combine them into one entity. For each company cover today's "
            f"price move, valuation (fair-value composite, model range, P/E), financial health, analyst "
            f"targets and notable news, then compare them. Format: 2-3 sentence headline, then 4-8 bullet points."
        )
    ticker = tickers[0] if isinstance(tickers, list) else tickers
    return (
        f"Give a concise analyst summary for {ticker}. "
        f"Cover: today's price move, valuation (the fair-value composite and model range, P/E), "
        f"financial health scores, analyst targets, notable recent news or earnings, and a balanced "
        f"bull/bear take. Format: 2-3 sentence headline, then 4-8 bullet points."
    )


def build_macro_prompt(countries: list[str]) -> str:
    """Task for a comparative macro summary; the figures come from APP DATA."""
    names = ", ".join(countries)
    return (
        f"Give a comparative macroeconomic summary for: {names} (ISO country codes). "
        f"For each country, briefly cover GDP growth, inflation, unemployment, government debt and the "
        f"current account, naming the data year, plus any notable recent policy, fiscal or trade developments. "
        f"Compare and contrast where relevant. Format: 2-3 sentence headline, then 4-8 bullet points."
    )


def build_dashboard_prompt() -> str:
    """Task for the daily market briefing; the figures come from APP DATA."""
    from datetime import datetime, timezone
    today = datetime.now(timezone.utc).strftime("%B %d, %Y")
    return (
        f"Give a daily market briefing for {today}. "
        f"Cover: major index performance, market breadth and sentiment (Fear & Greed), "
        f"top gainers/losers, and any key economic events or data releases. "
        f"Format: 2-3 sentence headline, then 4-8 bullet points."
    )
