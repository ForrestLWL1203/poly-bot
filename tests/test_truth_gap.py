from __future__ import annotations

from poly_bot.truth_gap import TruthGapInputs, compute_truth_gap, depth_notional, side_book


def test_compute_truth_gap_marks_truth_side_and_gap() -> None:
    result = compute_truth_gap(
        TruthGapInputs(
            open_price=100_000,
            reference_price=100_120,
            up_ask=0.54,
            down_ask=0.49,
            up_bid=0.53,
            down_bid=0.48,
        )
    )

    assert result.truth_side == "up"
    assert result.truth_move_bps == 12.0
    assert result.truth_side_ask == 0.54
    assert result.opposite_side_ask == 0.49
    assert result.truth_side_edge_to_even == 0.46
    assert result.market_side_by_ask == "down"
    assert result.market_side_by_bid == "up"
    assert result.truth_market_disagreement is True


def test_compute_truth_gap_handles_flat_or_missing_inputs() -> None:
    assert compute_truth_gap(TruthGapInputs(open_price=0, reference_price=100)).truth_side is None
    flat = compute_truth_gap(TruthGapInputs(open_price=100, reference_price=100, up_ask=0.5, down_ask=0.5))
    assert flat.truth_side is None
    assert flat.truth_move_bps == 0.0


def test_depth_notional_uses_top_levels() -> None:
    levels = [(0.50, 10), (0.51, 20), (0.52, 30)]

    assert depth_notional(levels, depth=2) == 15.2
    assert depth_notional(levels, depth=0) is None


def test_side_book_summarizes_levels() -> None:
    book = side_book(
        bid_levels=[(0.49, 10), (0.48, 20)],
        ask_levels=[(0.51, 11), (0.52, 21)],
        depth=2,
        bid_age_sec=1.2,
        ask_age_sec=1.5,
    )

    assert book["bb"] == 0.49
    assert book["ba"] == 0.51
    assert book["bid_depth_notional"] == 14.5
    assert book["ask_depth_notional"] == 16.53
    assert book["bid_age_sec"] == 1.2
