"""Sentiment service: fetches Finnhub general news and computes basic macro sentiment."""
from __future__ import annotations

import re
from .finnhub_service import _get
from ..cache import cached

# Simple macro-finance sentiment keywords
POSITIVE_WORDS = {"surge", "growth", "rebound", "soar", "jump", "rally", "easing", "stimulus", "cut", "upbeat", "strong", "gains", "bull"}
NEGATIVE_WORDS = {"crash", "plunge", "recession", "slump", "fear", "panic", "tightening", "hike", "downbeat", "weak", "losses", "bear", "crisis", "inflation"}

@cached("macro_sentiment")
def get_macro_sentiment() -> dict:
    """Fetch general news from Finnhub and compute a simple macro sentiment score."""
    # Finnhub general news: category=general
    news = _get("/news", {"category": "general"})
    
    if news is None:
        return {"error": "Failed to fetch Finnhub news or API key missing."}
    
    if not isinstance(news, list):
        news = []
        
    # Analyze up to 50 recent headlines
    news = news[:50]
    
    pos_count = 0
    neg_count = 0
    scored_news = []

    for item in news:
        headline = item.get("headline", "").lower()
        summary = item.get("summary", "").lower()
        text = f"{headline} {summary}"
        
        words = set(re.findall(r'\b\w+\b', text))
        
        pos_score = len(words.intersection(POSITIVE_WORDS))
        neg_score = len(words.intersection(NEGATIVE_WORDS))
        
        if pos_score > neg_score:
            sentiment = "positive"
        elif neg_score > pos_score:
            sentiment = "negative"
        else:
            sentiment = "neutral"
            
        pos_count += pos_score
        neg_count += neg_score
        
        scored_news.append({
            "id": item.get("id"),
            "datetime": item.get("datetime"),
            "headline": item.get("headline"),
            "source": item.get("source"),
            "url": item.get("url"),
            "summary": item.get("summary"),
            "sentiment": sentiment
        })
        
    total = pos_count + neg_count
    score = (pos_count - neg_count) / total if total > 0 else 0

    if score > 0.2:
        overall = "Bullish"
    elif score < -0.2:
        overall = "Bearish"
    else:
        overall = "Neutral"

    return {
        "score": round(score, 2),
        "overall": overall,
        "articles": scored_news
    }
