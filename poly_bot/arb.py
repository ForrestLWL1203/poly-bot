"""Executable edge calculations for cross-venue binary arbitrage."""

from __future__ import annotations

from dataclasses import dataclass

from poly_bot.markets import MarketSnapshot, Side


@dataclass(frozen=True)
class CrossVenueArb:
    """A same-event hedge candidate between two venues."""

    long_market: MarketSnapshot
    long_side: Side
    hedge_market: MarketSnapshot
    hedge_side: Side
    cost: float
    edge: float
    max_size: float | None
    reason: str


def binary_cross_venue_cost(long: MarketSnapshot, long_side: Side, hedge: MarketSnapshot, hedge_side: Side) -> float | None:
    """Return cost of buying two complementary binary legs, if quoted."""

    long_quote = long.quote(long_side)
    hedge_quote = hedge.quote(hedge_side)
    if long_quote is None or hedge_quote is None:
        return None
    if long_quote.ask is None or hedge_quote.ask is None:
        return None
    return float(long_quote.ask) + float(hedge_quote.ask)


def detect_binary_cross_venue_arb(
    long: MarketSnapshot,
    long_side: Side,
    hedge: MarketSnapshot,
    hedge_side: Side,
    *,
    fee_buffer: float = 0.0,
    safety_buffer: float = 0.0,
) -> CrossVenueArb | None:
    """Detect a simple buy/buy hedge where total cost is below payout."""

    cost = binary_cross_venue_cost(long, long_side, hedge, hedge_side)
    if cost is None:
        return None
    edge = 1.0 - cost - fee_buffer - safety_buffer
    if edge <= 0:
        return None
    long_quote = long.quote(long_side)
    hedge_quote = hedge.quote(hedge_side)
    sizes = [quote.ask_size for quote in (long_quote, hedge_quote) if quote is not None and quote.ask_size is not None]
    max_size = min(sizes) if sizes else None
    return CrossVenueArb(
        long_market=long,
        long_side=long_side,
        hedge_market=hedge,
        hedge_side=hedge_side,
        cost=cost,
        edge=edge,
        max_size=max_size,
        reason="buy_buy_cost_below_payout",
    )
