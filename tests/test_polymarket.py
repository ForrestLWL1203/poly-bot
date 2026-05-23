from __future__ import annotations

import datetime as dt
import json

from poly_bot.polymarket import Btc5mSeries, build_window, parse_book_side, parse_dt


def test_parse_book_side_sorts_and_drops_zero_size() -> None:
    raw = [
        {"price": "0.51", "size": "0"},
        {"price": "0.50", "size": "10"},
        {"price": "0.52", "size": "5"},
        {"price": "bad", "size": "8"},
    ]

    assert parse_book_side(raw, reverse=True) == [(0.52, 5.0), (0.5, 10.0)]
    assert parse_book_side(raw, reverse=False) == [(0.5, 10.0), (0.52, 5.0)]


def test_build_window_reads_token_ids_and_dates() -> None:
    raw = {
        "question": "BTC Up or Down?",
        "slug": "btc-updown-5m-1770000000",
        "clobTokenIds": json.dumps(["up-token", "down-token"]),
        "eventStartTime": "2026-02-03T00:00:00Z",
        "endDate": "2026-02-03T00:05:00Z",
        "description": "desc",
        "resolutionSource": "src",
    }

    window = build_window(raw, Btc5mSeries())

    assert window is not None
    assert window.up_token == "up-token"
    assert window.down_token == "down-token"
    assert window.start_time == dt.datetime(2026, 2, 3, 0, 0, tzinfo=dt.timezone.utc)
    assert window.end_time == dt.datetime(2026, 2, 3, 0, 5, tzinfo=dt.timezone.utc)


def test_parse_dt_normalizes_timezone() -> None:
    assert parse_dt("2026-02-03T08:00:00+08:00") == dt.datetime(2026, 2, 3, 0, 0, tzinfo=dt.timezone.utc)
