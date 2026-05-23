"""Truth-price gap calculations for short crypto prediction windows."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

Side = Literal["up", "down"]


@dataclass(frozen=True)
class TruthGapInputs:
    open_price: float | None = None
    reference_price: float | None = None
    up_ask: float | None = None
    down_ask: float | None = None
    up_bid: float | None = None
    down_bid: float | None = None


@dataclass(frozen=True)
class TruthGap:
    truth_side: Side | None
    truth_move_bps: float | None
    truth_side_ask: float | None
    opposite_side_ask: float | None
    truth_side_bid: float | None
    opposite_side_bid: float | None
    truth_side_edge_to_even: float | None
    market_side_by_ask: Side | None
    market_side_by_bid: Side | None
    truth_market_disagreement: bool | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compute_truth_gap(inputs: TruthGapInputs) -> TruthGap:
    truth_side: Side | None = None
    truth_move_bps: float | None = None
    if inputs.open_price is not None and inputs.reference_price is not None and inputs.open_price > 0:
        truth_move_bps = ((inputs.reference_price - inputs.open_price) / inputs.open_price) * 10_000.0
        if truth_move_bps > 0:
            truth_side = "up"
        elif truth_move_bps < 0:
            truth_side = "down"

    truth_ask = _side_value(truth_side, inputs.up_ask, inputs.down_ask)
    opposite_ask = _side_value(_opposite(truth_side), inputs.up_ask, inputs.down_ask)
    truth_bid = _side_value(truth_side, inputs.up_bid, inputs.down_bid)
    opposite_bid = _side_value(_opposite(truth_side), inputs.up_bid, inputs.down_bid)
    market_side_by_ask = _lower_ask_side(inputs.up_ask, inputs.down_ask)
    market_side_by_bid = _higher_bid_side(inputs.up_bid, inputs.down_bid)

    return TruthGap(
        truth_side=truth_side,
        truth_move_bps=round(truth_move_bps, 6) if truth_move_bps is not None else None,
        truth_side_ask=truth_ask,
        opposite_side_ask=opposite_ask,
        truth_side_bid=truth_bid,
        opposite_side_bid=opposite_bid,
        truth_side_edge_to_even=round(1.0 - truth_ask, 6) if truth_ask is not None else None,
        market_side_by_ask=market_side_by_ask,
        market_side_by_bid=market_side_by_bid,
        truth_market_disagreement=(truth_side != market_side_by_ask) if truth_side is not None and market_side_by_ask is not None else None,
    )


def depth_notional(levels: list[tuple[float, float]], *, depth: int) -> float | None:
    if depth <= 0:
        return None
    total = 0.0
    used = 0
    for price, size in levels[:depth]:
        total += float(price) * float(size)
        used += 1
    if used == 0:
        return None
    return round(total, 6)


def side_book(
    *,
    bid_levels: list[tuple[float, float]],
    ask_levels: list[tuple[float, float]],
    depth: int,
    bid_age_sec: float | None = None,
    ask_age_sec: float | None = None,
) -> dict[str, Any]:
    best_bid = bid_levels[0][0] if bid_levels else None
    best_ask = ask_levels[0][0] if ask_levels else None
    bid_size = bid_levels[0][1] if bid_levels else None
    ask_size = ask_levels[0][1] if ask_levels else None
    return {
        "bb": best_bid,
        "bs": bid_size,
        "ba": best_ask,
        "as": ask_size,
        "bid": [[price, size] for price, size in bid_levels[:depth]],
        "ask": [[price, size] for price, size in ask_levels[:depth]],
        "bid_depth_notional": depth_notional(bid_levels, depth=depth),
        "ask_depth_notional": depth_notional(ask_levels, depth=depth),
        "bid_age_sec": bid_age_sec,
        "ask_age_sec": ask_age_sec,
    }


def _opposite(side: Side | None) -> Side | None:
    if side == "up":
        return "down"
    if side == "down":
        return "up"
    return None


def _side_value(side: Side | None, up_value: float | None, down_value: float | None) -> float | None:
    if side == "up":
        return up_value
    if side == "down":
        return down_value
    return None


def _lower_ask_side(up_ask: float | None, down_ask: float | None) -> Side | None:
    if up_ask is None or down_ask is None or up_ask == down_ask:
        return None
    return "up" if up_ask < down_ask else "down"


def _higher_bid_side(up_bid: float | None, down_bid: float | None) -> Side | None:
    if up_bid is None or down_bid is None or up_bid == down_bid:
        return None
    return "up" if up_bid > down_bid else "down"
