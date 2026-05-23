"""Polymarket live-data BTC/USD Chainlink feed."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from bisect import bisect_left, bisect_right
from collections import deque
from typing import Any

import websockets

POLYMARKET_LIVE_DATA_WS_URL = "wss://ws-live-data.polymarket.com"
log = logging.getLogger(__name__)


def subscribe_message(symbol: str = "btc/usd") -> dict[str, Any]:
    return {
        "action": "subscribe",
        "subscriptions": [{
            "topic": "crypto_prices_chainlink",
            "type": "update",
            "filters": json.dumps({"symbol": symbol.lower()}, separators=(",", ":")),
        }],
    }


def price_ticks_from_message(data: dict[str, Any]) -> list[tuple[float, float]]:
    payload = data.get("payload") if isinstance(data, dict) else None
    if not isinstance(payload, dict):
        return []
    batch = payload.get("data")
    items = batch if isinstance(batch, list) else [payload]
    ticks: list[tuple[float, float]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        try:
            timestamp_ms = float(item["timestamp"])
            value = float(item["value"])
        except (KeyError, TypeError, ValueError):
            continue
        if timestamp_ms > 0 and value > 0:
            ticks.append((timestamp_ms / 1000.0, value))
    return ticks


class ChainlinkBtcFeed:
    def __init__(self, symbol: str = "btc/usd", max_history_sec: float = 900.0, stale_reconnect_sec: float = 5.0):
        self._symbol = symbol
        self._max_history_sec = max_history_sec
        self._stale_reconnect_sec = stale_reconnect_sec
        self._history: deque[tuple[float, float]] = deque()
        self._running = False
        self._task: asyncio.Task | None = None
        self._ws: websockets.WebSocketClientProtocol | None = None

    @property
    def latest_price(self) -> float | None:
        return self._history[-1][1] if self._history else None

    def latest_age_sec(self, now: float | None = None) -> float | None:
        if not self._history:
            return None
        return max(0.0, (now if now is not None else time.time()) - self._history[-1][0])

    def price_at_or_before(self, ts: float, max_backward_sec: float | None = None) -> float | None:
        if not self._history:
            return None
        ts_values = [tick_ts for tick_ts, _ in self._history]
        idx = bisect_right(ts_values, ts) - 1
        if idx < 0:
            return None
        price_ts, price = self._history[idx]
        if max_backward_sec is not None and ts - price_ts > max_backward_sec:
            return None
        return price

    def first_price_at_or_after(self, ts: float, max_forward_sec: float = 30.0) -> float | None:
        if not self._history:
            return None
        ts_values = [tick_ts for tick_ts, _ in self._history]
        idx = bisect_left(ts_values, ts)
        if idx >= len(self._history):
            return None
        price_ts, price = self._history[idx]
        if price_ts - ts > max_forward_sec:
            return None
        return price

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._recv_loop())

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)
            self._task = None
        if self._ws:
            await self._ws.close()
            self._ws = None

    def _inject(self, ts: float, price: float) -> None:
        if not self._history or ts > self._history[-1][0]:
            self._history.append((ts, price))
        elif ts == self._history[-1][0]:
            self._history[-1] = (ts, price)
        self._prune(time.time())

    async def _recv_loop(self) -> None:
        subscribe = subscribe_message(self._symbol)
        backoff = 1.0
        while self._running:
            try:
                self._ws = await websockets.connect(POLYMARKET_LIVE_DATA_WS_URL, ping_interval=20, ping_timeout=20)
                await self._ws.send(json.dumps(subscribe, separators=(",", ":")))
                last_tick_mono = time.monotonic()
                async for msg in self._ws:
                    try:
                        data = json.loads(msg)
                    except json.JSONDecodeError:
                        continue
                    ticks = price_ticks_from_message(data)
                    for tick_ts, price in ticks:
                        self._inject(tick_ts, price)
                    if ticks:
                        last_tick_mono = time.monotonic()
                    if time.monotonic() - last_tick_mono > self._stale_reconnect_sec:
                        break
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("Chainlink websocket error: %s", exc)
            if self._ws:
                try:
                    await self._ws.close()
                except Exception:
                    pass
                self._ws = None
            if self._running:
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 30.0)

    def _prune(self, now: float) -> None:
        cutoff = now - self._max_history_sec
        while self._history and self._history[0][0] < cutoff:
            self._history.popleft()
