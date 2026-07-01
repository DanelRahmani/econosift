"""AI-powered summary service using Google Gemini (free tier).

All summaries are on-request only — no automatic generation.
Results are cached in the AiSummary DB table and re-served
unless the user explicitly requests regeneration.

Prompt strategy: simple queries that let Gemini do the research.
No server-side data gathering — we trust Gemini's broad financial
knowledge, which eliminates yfinance rate-limit bottlenecks.
"""

from __future__ import annotations

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
    "You are an expert financial analyst writing for Axiom Finance, a self-hosted "
    "investment research platform. Your responses should be concise, data-driven, "
    "and written in plain English. Start with a 2-3 sentence paragraph headline "
    "summarising the key takeaway, then follow with 4-8 bullet points of key insights. "
    "Use % signs for percentages, $ for dollar amounts, and abbreviate large numbers "
    "(e.g. $3.2T, 142B). Be balanced — mention both strengths and risks. "
    "You may reference publicly available data from Yahoo Finance, FRED, and other "
    "financial sources."
)


async def generate_summary(prompt: str, model: str = "gemini-2.5-flash") -> str:
    """Call the Gemini REST API and return the generated text."""
    if not GEMINI_API_KEY:
        return "Error: Gemini API key not configured. Add your key on the Admin page."

    url = GEMINI_URL.format(model=model)
    payload = {
        "contents": [{"parts": [{"text": SYSTEM_PROMPT + "\n\n" + prompt}]}],
        "generationConfig": {"temperature": 0.4, "maxOutputTokens": 2048, "topP": 0.95},
    }

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=10.0)) as client:
            resp = await client.post(url, params={"key": GEMINI_API_KEY}, json=payload, headers={"Content-Type": "application/json"})
            if resp.status_code != 200:
                detail = _extract_error(resp)
                return f"Error: Gemini API returned {resp.status_code} - {detail}"
            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                feedback = data.get("promptFeedback", {})
                reason = feedback.get("blockReason", "No candidates returned")
                return f"Error: Gemini blocked the request - {reason}"
            parts = candidates[0].get("content", {}).get("parts", [])
            text = "".join(p.get("text", "") for p in parts)
            if not text.strip():
                return "Error: Gemini returned an empty response."
            return text.strip()
    except httpx.TimeoutException:
        return "Error: Gemini API request timed out after 30 seconds."
    except Exception as exc:
        return f"Error: Gemini API call failed - {exc}"


def _extract_error(resp: httpx.Response) -> str:
    try:
        data = resp.json()
        err = data.get("error", {})
        return err.get("message", str(data))
    except Exception:
        return resp.text[:200]


def build_company_prompt(ticker: str) -> str:
    """Simple prompt - Gemini looks up the ticker itself."""
    return (
        f"Give a concise analyst summary for {ticker} stock. "
        f"Cover: recent price action, key valuation metrics (P/E, market cap), "
        f"recent news or earnings if notable, competitive position, and a balanced "
        f"bull/bear take. Format: 2-3 sentence headline, then 4-8 bullet points. "
        f"At the end, list the key sources you referenced (e.g. Yahoo Finance)."
    )


def build_macro_prompt(countries: list[str]) -> str:
    """Simple prompt - Gemini summarises macro conditions for given countries."""
    names = ", ".join(countries)
    return (
        f"Give a comparative macroeconomic summary for: {names}. "
        f"For each country, briefly cover: GDP growth, inflation, unemployment, "
        f"interest rates, and any notable fiscal or trade developments. "
        f"Compare and contrast where relevant. "
        f"Format: 2-3 sentence headline, then 4-8 bullet points. "
        f"At the end, list the key sources you referenced (e.g. World Bank, IMF)."
    )


def build_dashboard_prompt() -> str:
    """Simple prompt - Gemini summarises today's market conditions."""
    from datetime import datetime
    today = datetime.utcnow().strftime("%B %d, %Y")
    return (
        f"Give a daily market briefing for {today}. "
        f"Cover: major US index performance (S&P 500, Nasdaq, Dow), "
        f"market breadth and sentiment, notable sector moves, "
        f"top gainers/losers, and any key economic events or data releases today. "
        f"Format: 2-3 sentence headline, then 4-8 bullet points. "
        f"At the end, list the key sources you referenced (e.g. Yahoo Finance, FRED)."
    )
