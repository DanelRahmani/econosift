"""Example strategy: 12-1 momentum, equal weight, long only.

A strategy is one file with a top-level ``generate_weights(ctx)``. On each
rebalance date it gets ``ctx``:

    ctx.date          the rebalance date (you trade at its close)
    ctx.universe      index members on that date with a stored price
    ctx.prices(field="adj_close", lookback=None)   bars up to ctx.date only
                      (fields: adj_close, close, volume)
    ctx.fundamentals(symbol)   SEC facts filed before ctx.date
    ctx.params        parameters for this run (walk-forward fills them from a grid)
    ctx.holdings      current weights after drifting since the last rebalance

and returns {symbol: weight}: fractions of equity, negative = short, the rest
is cash. Only numpy, pandas and the standard library modules already loaded
are available; there is no network and no file access.
"""

PARAMS = {"top_n": 50, "lookback": 252, "skip": 21}


def generate_weights(ctx):
    p = {**PARAMS, **ctx.params}
    px = ctx.prices(lookback=p["lookback"] + 1)
    if len(px) <= p["lookback"]:
        return {}  # not enough history yet: stay in cash
    momentum = (px.iloc[-1 - p["skip"]] / px.iloc[0] - 1.0).dropna()
    winners = momentum.nlargest(int(p["top_n"])).index
    return {sym: 1.0 / len(winners) for sym in winners}
