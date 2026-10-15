"""Per-source token bucket + circuit breaker (Phase 65, item 4)."""
import pytest
from yfinance.exceptions import YFRateLimitError

from backend import rate_limit as rl


class FakeClock:
    def __init__(self):
        self.t = 1000.0
        self.slept = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.slept += s
        self.t += s


def _guard(clock, **kw):
    return rl.SourceGuard("test", rate=2.0, burst=4, clock=clock.now, sleep=clock.sleep, **kw)


def test_bucket_allows_burst_then_throttles_to_rate():
    c = FakeClock()
    g = _guard(c)
    for _ in range(4):
        g.call(lambda: None)
    assert c.slept == 0
    for _ in range(4):
        g.call(lambda: None)
    assert c.slept == pytest.approx(2.0, abs=0.01)  # 4 more at 2/s
    assert g.status()["requests"] == 8


def test_429_opens_circuit_with_exponential_cooldown():
    c = FakeClock()
    g = _guard(c)

    def limited():
        raise YFRateLimitError()

    with pytest.raises(YFRateLimitError):
        g.call(limited)
    assert g.status()["state"] == "open"
    first = g.status()["openForSeconds"]

    calls = []
    with pytest.raises(YFRateLimitError):  # fails fast, never reaches the source
        g.call(lambda: calls.append(1))
    assert calls == []

    c.t += first + 1
    with pytest.raises(YFRateLimitError):
        g.call(limited)
    assert g.status()["openForSeconds"] == pytest.approx(first * 2, abs=1)


def test_success_closes_circuit_and_resets_backoff():
    c = FakeClock()
    g = _guard(c)
    with pytest.raises(YFRateLimitError):
        g.call(lambda: (_ for _ in ()).throw(YFRateLimitError()))
    c.t += 10_000
    assert g.call(lambda: "ok") == "ok"
    st = g.status()
    assert st["state"] == "closed" and st["consecutive429"] == 0


def test_repeated_network_errors_open_circuit():
    c = FakeClock()
    g = _guard(c)
    for _ in range(rl.ERROR_THRESHOLD):
        with pytest.raises(ConnectionError):
            g.call(lambda: (_ for _ in ()).throw(ConnectionError("down")))
    assert g.status()["state"] == "open"


def test_http_429_response_counts_as_rate_limit():
    class Resp:
        status_code = 429

    c = FakeClock()
    g = _guard(c)
    assert g.call(lambda: Resp()).status_code == 429
    assert g.status()["state"] == "open"


def test_install_wraps_yfinance_request_once():
    from yfinance.data import YfData
    rl.install_yfinance_guard()
    wrapped = YfData._make_request
    rl.install_yfinance_guard()
    assert YfData._make_request is wrapped
    assert getattr(wrapped, "_econosift_guard", False)


def test_chart_and_api_requests_use_separate_buckets():
    assert rl.guard_for_url("https://query2.finance.yahoo.com/v8/finance/chart/AAPL") is rl.YAHOO_CHART
    for url in ("https://query2.finance.yahoo.com/v10/finance/quoteSummary/AAPL",
                "https://query1.finance.yahoo.com/v7/finance/options/AAPL",
                "https://query1.finance.yahoo.com/v1/test/getcrumb", ""):
        assert rl.guard_for_url(url) is rl.YAHOO_API
    assert rl.YAHOO_CHART.rate > rl.YAHOO_API.rate


def test_a_429_on_one_bucket_leaves_the_other_open_for_calls():
    c = FakeClock()
    chart, api = _guard(c), _guard(c)
    with pytest.raises(YFRateLimitError):
        api.call(lambda: (_ for _ in ()).throw(YFRateLimitError()))
    assert api.status()["state"] == "open"
    assert chart.call(lambda: "ok") == "ok"


def test_status_reports_both_yahoo_buckets():
    assert set(rl.status()) == {"yahoo_chart", "yahoo_api"}


def test_bulk_request_yields_while_an_interactive_one_waits():
    c = FakeClock()
    g = _guard(c)
    g._high_waiting = 1  # an in-page request is queued for a token
    order = []

    def sleep(s):
        c.sleep(s)
        if not order:  # the interactive request gets its token meanwhile
            order.append("interactive")
            g._high_waiting = 0

    g._sleep = sleep
    with rl.bulk():
        g.call(lambda: order.append("bulk"))
    assert order == ["interactive", "bulk"]


def test_bulk_flag_is_scoped_to_the_context():
    assert not rl.is_bulk()
    with rl.bulk():
        assert rl.is_bulk()
    assert not rl.is_bulk()
