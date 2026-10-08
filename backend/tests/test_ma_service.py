"""Tests for ma_service — M&A merger news (fully offline, no network)."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest


# Test data: sample Finnhub merger news items
_FAKE_NEWS_ITEMS = [
    {
        "headline": "Acme Corp to buy Beta Inc for $2 billion",
        "related": "",
        "datetime": 1759795200,  # 2025-10-07 UTC
        "source": "X",
        "url": "u1",
    },
    {
        "headline": "AAPL in talks",
        "related": "AAPL,MSFT",
        "datetime": 1757116800,  # 2025-09-06 UTC
        "source": "Y",
        "url": "u2",
    },
    {
        "headline": "No date item",
        "related": "",
        "source": "Z",
        "url": "u3",
        # Note: no datetime field
    },
]


@pytest.mark.asyncio
async def test_ma_service_news_shape(monkeypatch):
    """Verify the response shape: news items with date, related, sector (not acquirer/target/value)."""
    from backend.services import ma_service

    # Mock FINNHUB_API_KEY so the service tries to fetch
    monkeypatch.setattr(ma_service, "FINNHUB_API_KEY", "fake_key")

    # Mock httpx.AsyncClient
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = _FAKE_NEWS_ITEMS

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_async_client_class = MagicMock(return_value=mock_client)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client_class)

    # Call the service function
    result = await ma_service.get_ma_data()

    # Verify the response structure
    assert "asOf" in result
    assert "source" in result
    assert result["source"] == "Finnhub"
    assert "news" in result
    assert "monthlyCount" in result
    assert "sectorCount" in result

    # Verify no old keys
    assert "deals" not in result
    assert "monthlyVolume" not in result
    assert "sectorHeatmap" not in result

    # Verify news items
    news = result["news"]
    assert len(news) == 3

    # First item: newest (2025-10-07), no related/sector
    assert news[0]["date"] == "2025-10-07"
    assert news[0]["related"] == []
    assert news[0]["sector"] is None
    assert news[0]["headline"] == "Acme Corp to buy Beta Inc for $2 billion"
    assert news[0]["source"] == "X"
    assert news[0]["url"] == "u1"
    assert "acquirer" not in news[0]
    assert "target" not in news[0]
    assert "value" not in news[0]

    # Second item: 2025-09-06, with related tickers [AAPL, MSFT]
    assert news[1]["date"] == "2025-09-06"
    assert news[1]["related"] == ["AAPL", "MSFT"]
    # AAPL is in the map, so sector should be Technology
    assert news[1]["sector"] == "Technology"
    assert news[1]["headline"] == "AAPL in talks"

    # Third item: no date, sorted last
    assert news[2]["date"] is None
    assert news[2]["related"] == []
    assert news[2]["sector"] is None
    assert news[2]["headline"] == "No date item"
    assert news[2] is news[-1], "Item without date should be last"


@pytest.mark.asyncio
async def test_ma_service_monthly_count(monkeypatch):
    """Verify monthlyCount: only items with dates, ascending months."""
    from backend.services import ma_service

    monkeypatch.setattr(ma_service, "FINNHUB_API_KEY", "fake_key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = _FAKE_NEWS_ITEMS

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_async_client_class = MagicMock(return_value=mock_client)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client_class)

    result = await ma_service.get_ma_data()
    monthly_count = result["monthlyCount"]

    # Should have 2 months (2025-09 and 2025-10), 1 item each, ascending order
    assert len(monthly_count) == 2
    assert monthly_count[0]["month"] == "2025-09"
    assert monthly_count[0]["count"] == 1
    assert monthly_count[1]["month"] == "2025-10"
    assert monthly_count[1]["count"] == 1


@pytest.mark.asyncio
async def test_ma_service_sector_count(monkeypatch):
    """Verify sectorCount: only items with sector not null, desc by count."""
    from backend.services import ma_service

    monkeypatch.setattr(ma_service, "FINNHUB_API_KEY", "fake_key")

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = _FAKE_NEWS_ITEMS

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_async_client_class = MagicMock(return_value=mock_client)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client_class)

    result = await ma_service.get_ma_data()
    sector_count = result["sectorCount"]

    # Only one sector (Technology from AAPL in item 2)
    assert len(sector_count) == 1
    assert sector_count[0]["sector"] == "Technology"
    assert sector_count[0]["count"] == 1


@pytest.mark.asyncio
async def test_ma_service_empty_no_key(monkeypatch):
    """Verify empty response when no FINNHUB_API_KEY."""
    from backend.services import ma_service

    monkeypatch.setattr(ma_service, "FINNHUB_API_KEY", None)

    result = await ma_service.get_ma_data()

    assert result["news"] == []
    assert result["monthlyCount"] == []
    assert result["sectorCount"] == []


@pytest.mark.asyncio
async def test_ma_service_invalid_datetime(monkeypatch):
    """Verify date is None for invalid timestamps."""
    from backend.services import ma_service

    monkeypatch.setattr(ma_service, "FINNHUB_API_KEY", "fake_key")

    # Test with invalid timestamp
    invalid_items = [
        {
            "headline": "Test invalid",
            "related": "",
            "datetime": "not_a_number",  # Invalid
            "source": "X",
            "url": "u1",
        },
    ]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = invalid_items

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_async_client_class = MagicMock(return_value=mock_client)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client_class)

    result = await ma_service.get_ma_data()

    # Invalid datetime should result in date: None
    assert result["news"][0]["date"] is None


@pytest.mark.asyncio
async def test_ma_service_sector_map(monkeypatch):
    """Verify sector mapping for known tickers."""
    from backend.services import ma_service

    monkeypatch.setattr(ma_service, "FINNHUB_API_KEY", "fake_key")

    # Test with multiple tickers, only first known one should be used
    test_items = [
        {
            "headline": "Deal with MSFT",
            "related": "UNKNOWN1,MSFT,JPM",  # MSFT is Technology
            "datetime": 1759795200,
            "source": "X",
            "url": "u1",
        },
    ]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = test_items

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_async_client_class = MagicMock(return_value=mock_client)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client_class)

    result = await ma_service.get_ma_data()
    news = result["news"]

    # MSFT should map to Technology
    assert news[0]["related"] == ["UNKNOWN1", "MSFT", "JPM"]
    assert news[0]["sector"] == "Technology"


@pytest.mark.asyncio
async def test_ma_service_headline_truncation(monkeypatch):
    """Verify headlines are truncated to 160 chars."""
    from backend.services import ma_service

    monkeypatch.setattr(ma_service, "FINNHUB_API_KEY", "fake_key")

    long_headline = "A" * 200  # 200 chars, should be truncated to 160

    test_items = [
        {
            "headline": long_headline,
            "related": "",
            "datetime": 1759795200,
            "source": "X",
            "url": "u1",
        },
    ]

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = test_items

    mock_client = MagicMock()
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)
    mock_client.get = AsyncMock(return_value=mock_response)

    mock_async_client_class = MagicMock(return_value=mock_client)

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", mock_async_client_class)

    result = await ma_service.get_ma_data()
    news = result["news"]

    assert len(news[0]["headline"]) == 160
