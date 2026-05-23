from __future__ import annotations

import asyncio
import datetime as dt
import json

import pytest

import poly_bot.polymarket as polymarket
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


def test_price_stream_switch_tokens_reconnects_when_existing_ws_is_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    class ClosedWs:
        async def send(self, _message: str) -> None:
            raise RuntimeError("closed")

        async def close(self) -> None:
            return None

    class FreshWs:
        def __init__(self) -> None:
            self.sent: list[str] = []

        async def send(self, message: str) -> None:
            self.sent.append(message)

        async def close(self) -> None:
            return None

        def __aiter__(self) -> "FreshWs":
            return self

        async def __anext__(self) -> str:
            await asyncio.sleep(60)
            return "{}"

    fresh = FreshWs()

    async def fake_connect(_url: str) -> FreshWs:
        return fresh

    async def noop(_update: polymarket.PriceUpdate) -> None:
        return None

    async def run() -> None:
        stream = polymarket.PriceStream(noop)
        stream._running = True
        stream._ws = ClosedWs()
        stream._connected_tokens = ["old-token"]
        monkeypatch.setattr(polymarket.websockets, "connect", fake_connect)

        await stream.switch_tokens(["new-token"])
        await stream.close()

    asyncio.run(run())

    assert len(fresh.sent) == 1
    assert json.loads(fresh.sent[0]) == {
        "type": "market",
        "assets_ids": ["new-token"],
        "operation": "subscribe",
        "custom_feature_enabled": True,
    }
