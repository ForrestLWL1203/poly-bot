"""Normalized market and order-book models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Side = Literal["yes", "no"]


@dataclass(frozen=True)
class OutcomeQuote:
    """Top-of-book and depth for one binary outcome."""

    side: Side
    bid: float | None = None
    ask: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None


@dataclass(frozen=True)
class MarketSnapshot:
    """Venue-normalized binary prediction market snapshot."""

    venue: str
    market_id: str
    title: str
    close_ts: str | None = None
    rules: str | None = None
    url: str | None = None
    outcomes: dict[Side, OutcomeQuote] = field(default_factory=dict)

    def quote(self, side: Side) -> OutcomeQuote | None:
        return self.outcomes.get(side)
