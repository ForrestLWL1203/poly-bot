from __future__ import annotations

from poly_bot.arb import detect_binary_cross_venue_arb
from poly_bot.markets import MarketSnapshot, OutcomeQuote


def market(venue: str, yes_ask: float, no_ask: float) -> MarketSnapshot:
    return MarketSnapshot(
        venue=venue,
        market_id=f"{venue}-1",
        title="Will Team A win?",
        outcomes={
            "yes": OutcomeQuote("yes", ask=yes_ask, ask_size=100),
            "no": OutcomeQuote("no", ask=no_ask, ask_size=80),
        },
    )


def test_detects_buy_buy_cost_below_payout() -> None:
    poly = market("polymarket", yes_ask=0.42, no_ask=0.60)
    kalshi = market("kalshi", yes_ask=0.50, no_ask=0.53)

    arb = detect_binary_cross_venue_arb(poly, "yes", kalshi, "no", fee_buffer=0.01, safety_buffer=0.01)

    assert arb is not None
    assert arb.cost == 0.95
    assert round(arb.edge, 6) == 0.03
    assert arb.max_size == 80


def test_rejects_when_fee_buffer_consumes_edge() -> None:
    poly = market("polymarket", yes_ask=0.48, no_ask=0.53)
    kalshi = market("kalshi", yes_ask=0.50, no_ask=0.51)

    arb = detect_binary_cross_venue_arb(poly, "yes", kalshi, "no", fee_buffer=0.02)

    assert arb is None
