"""Phase 70 item 1: a strategy on date t sees only members on t, bars up to t and facts filed before t."""
import pandas as pd
import pytest

from backend import fetcher, store
from backend.services import pit
from backend.services.strategy_context import Panel, StrategyContext

TABLES = ("index_membership", "price_daily", "corporate_action", "fundamental", "fetch_queue", "security")
DAYS = pd.bdate_range("2019-06-03", "2020-06-30")
SENTINEL = 9999.0  # AAA's close on 2020-02-03: no view before that date may contain it


@pytest.fixture(autouse=True)
def _store():
    def wipe():
        with store.connect() as conn:
            for t in TABLES:
                conn.execute(f"DELETE FROM {t}")
    store.init_schema()
    wipe()
    pit._facts.cache_clear()
    membership = [("AAA", "", None), ("BBB", "2020-03-02", None), ("CCC", "", "2020-02-14"),
                  ("DDD", "", None), ("EEE", "", None)]
    store.upsert("index_membership", [dict(index_name="sp500", symbol=s, start=a, end=e) for s, a, e in membership],
                 ("index_name", "symbol", "start"))
    bars = []
    for i, d in enumerate(DAYS):
        day = d.date().isoformat()
        # AAA trades at 200 + i; a 2:1 split on 2020-04-01 and a 1.0 dividend on 2020-05-01.
        # Like Yahoo, stored closes are split-adjusted for every later split, and adj_close
        # is also dividend-adjusted.
        traded = SENTINEL if day == "2020-02-03" else 200.0 + i
        if d >= pd.Timestamp("2020-04-01"):
            traded /= 2
        close = traded / 2 if d < pd.Timestamp("2020-04-01") else traded
        adj = close * (0.99 if d < pd.Timestamp("2020-05-01") else 1.0)
        bars.append(dict(symbol="AAA", date=day, open=close, high=close, low=close, close=close, adj_close=adj,
                         volume=1000.0 * (2 if d < pd.Timestamp("2020-04-01") else 1)))
        for sym, px in (("BBB", 50.0 + i), ("CCC", 30.0)):
            if sym == "CCC" and d > pd.Timestamp("2020-02-20"):
                continue  # delisted: its history ends
            bars.append(dict(symbol=sym, date=day, open=px, high=px, low=px, close=px, adj_close=px, volume=1.0))
    store.upsert("price_daily", bars, ("symbol", "date"))
    store.upsert("corporate_action", [dict(symbol="AAA", date="2020-04-01", type="split", value=2.0),
                                      dict(symbol="AAA", date="2020-05-01", type="dividend", value=1.0)],
                 ("symbol", "date", "type"))
    with store.connect() as conn:
        conn.execute("INSERT INTO fetch_queue (kind, key, priority, created_at, attempts) VALUES "
                     "('history', 'DDD', 6, 'x', ?)", (fetcher.MAX_ATTEMPTS,))
    facts = [("2019-12-31", "2020-02-03", 10.0), ("2019-12-31", "2020-03-10", 12.0)]  # filed, then restated
    store.upsert("fundamental", [dict(symbol="AAA", concept="Net Income", period_end=end, filed=filed, value=v,
                                      unit="USD", form="10-K", source="sec:us-gaap:NetIncomeLoss")
                                 for end, filed, v in facts], ("symbol", "concept", "period_end", "filed"))
    yield
    wipe()


def _data():
    return pit.PITData("sp500", "2020-01-01", "2020-06-30", warmup_days=60)


def _ctx(feed: pit.Feed, panel: Panel, t: str) -> StrategyContext:
    msg, _ = feed.step(t)
    if "panel" in msg:
        panel.apply(msg["panel"])
    return StrategyContext(panel, msg, fundamentals_fn=lambda s: feed.data.facts(s, t))


def test_members_follow_the_interval_and_gaps_are_listed_not_filled():
    universe, excluded = _data().members("2020-02-28")
    assert universe == ["AAA"]  # BBB joins 2020-03-02, CCC left 2020-02-14
    assert {e["symbol"]: e["reason"] for e in excluded} == {
        "DDD": "Yahoo has no history for this symbol", "EEE": "history not fetched yet"}
    assert _data().members("2020-03-02")[0] == ["AAA", "BBB"]
    assert _data().members("2020-02-13")[0] == ["AAA", "CCC"]


def test_a_future_bar_is_nowhere_in_the_strategy_process():
    feed, panel = pit.Feed(_data()), Panel()
    ctx = _ctx(feed, panel, "2020-01-31")
    assert ctx.prices().index.max() == pd.Timestamp("2020-01-31")
    for f, frame in panel.frames.items():  # everything the strategy's process holds, not just the API
        assert frame.index.max() <= pd.Timestamp("2020-01-31"), f
        assert not (frame == SENTINEL).any().any() and not (frame == SENTINEL / 2).any().any()
    assert "BBB" not in panel.frames["close"].columns  # it joins the index later: even its past is hidden
    ctx = _ctx(feed, panel, "2020-02-03")
    assert ctx.prices("close").loc["2020-02-03", "AAA"] == SENTINEL  # visible from its own date on


def test_a_later_split_or_dividend_does_not_change_what_is_visible():
    feed, panel = pit.Feed(_data()), Panel()
    ctx = _ctx(feed, panel, "2020-03-31")
    close = ctx.prices("close")["AAA"]
    i = DAYS.get_loc(pd.Timestamp("2020-03-31"))
    assert close.iloc[-1] == pytest.approx(200.0 + i)  # as quoted then, not halved by the April split
    assert ctx.prices()["AAA"].iloc[-1] == pytest.approx(close.iloc[-1])  # adj = quoted on its own date
    assert ctx.prices("volume")["AAA"].iloc[-1] == pytest.approx(1000.0)
    ctx = _ctx(feed, panel, "2020-04-30")  # after the split, history is restated as it was then
    assert ctx.prices("close")["AAA"].loc["2020-03-31"] == pytest.approx((200.0 + i) / 2)
    assert ctx.prices("volume")["AAA"].loc["2020-03-31"] == pytest.approx(2000.0)
    returns = ctx.prices()["AAA"].pct_change().dropna()
    stored = store.prices(["AAA"], "2019-11-01", "2020-04-30")["AAA"].pct_change().dropna()
    pd.testing.assert_series_equal(returns, stored.loc[returns.index], check_names=False)  # returns untouched


def test_an_earlier_date_after_a_later_one_sees_the_same_as_a_fresh_run():
    feed, panel = pit.Feed(_data()), Panel()
    _ctx(feed, panel, "2020-05-29")
    rewound = _ctx(feed, panel, "2020-03-31")  # walk-forward reruns a window already shown
    fresh = _ctx(pit.Feed(_data()), Panel(), "2020-03-31")
    for f in ("adj_close", "close", "volume"):
        pd.testing.assert_frame_equal(rewound.prices(f), fresh.prices(f))
    assert rewound.universe == fresh.universe


def test_a_filing_is_visible_only_after_its_filing_date_and_restatements_later():
    feed, panel = pit.Feed(_data()), Panel()
    assert _ctx(feed, panel, "2020-02-03").fundamentals("AAA") == {}  # filed that day: maybe after the close
    assert _ctx(feed, panel, "2020-02-04").fundamentals("AAA")["Net Income"]["2019-12-31"]["value"] == 10.0
    assert _ctx(feed, panel, "2020-03-11").fundamentals("AAA")["Net Income"]["2019-12-31"]["value"] == 12.0
    with pytest.raises(KeyError):
        _ctx(feed, panel, "2020-03-11").fundamentals("CCC")  # no longer a member
