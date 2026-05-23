"""Read-only Polymarket BTC 5-minute market and book helpers."""

from __future__ import annotations

import asyncio
import datetime as dt
import json
import logging
import time
import urllib.parse
import urllib.request
from collections import Counter
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

import websockets

GAMMA_API = "https://gamma-api.polymarket.com/markets"
CLOB_WS_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"
UTC = dt.timezone.utc
log = logging.getLogger(__name__)


@dataclass(frozen=True)
class MarketWindow:
    question: str
    up_token: str
    down_token: str
    start_time: dt.datetime
    end_time: dt.datetime
    slug: str
    description: str | None = None
    resolution_source: str | None = None

    @property
    def start_epoch(self) -> int:
        return int(self.start_time.timestamp())

    @property
    def end_epoch(self) -> int:
        return int(self.end_time.timestamp())


@dataclass(frozen=True)
class PriceUpdate:
    token_id: str
    best_bid: float | None
    best_ask: float | None
    source: str
    received_at: float


class Btc5mSeries:
    slug_prefix = "btc-updown-5m"
    slug_step = 300

    def epoch_to_slug(self, epoch: int) -> str:
        return f"{self.slug_prefix}-{epoch}"


def find_window_after(after_epoch: int, series: Btc5mSeries | None = None) -> MarketWindow | None:
    series = series or Btc5mSeries()
    next_boundary = -(-after_epoch // series.slug_step) * series.slug_step
    return _scan_forward(next_boundary, series, include_future=True)


def find_next_window(series: Btc5mSeries | None = None) -> MarketWindow | None:
    series = series or Btc5mSeries()
    now_epoch = int(dt.datetime.now(UTC).timestamp())
    current_start = (now_epoch // series.slug_step) * series.slug_step
    return _scan_forward(current_start, series, include_future=False)


def _scan_forward(from_epoch: int, series: Btc5mSeries, *, include_future: bool, max_windows: int = 24) -> MarketWindow | None:
    now = dt.datetime.now(UTC)
    base_epoch = (from_epoch // series.slug_step) * series.slug_step
    for offset in range(max_windows):
        epoch = base_epoch + offset * series.slug_step
        raw = fetch_market_by_slug(series.epoch_to_slug(epoch))
        if raw is None or raw.get("closed"):
            continue
        window = build_window(raw, series)
        if window is None or window.end_time <= now:
            continue
        if include_future:
            if window.start_epoch >= from_epoch:
                return window
            continue
        if raw.get("active"):
            return window
    return None


def fetch_market_by_slug(slug: str) -> dict[str, Any] | None:
    url = GAMMA_API + "?" + urllib.parse.urlencode({"slug": slug})
    req = urllib.request.Request(url, headers={"User-Agent": "poly-bot/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:
        log.warning("failed to fetch Gamma market %s: %s", slug, exc)
        return None
    if isinstance(data, list):
        for market in data:
            if isinstance(market, dict) and market.get("slug") == slug:
                return market
    return None


def build_window(raw: dict[str, Any], series: Btc5mSeries | None = None) -> MarketWindow | None:
    series = series or Btc5mSeries()
    try:
        tokens = parse_tokens(raw.get("clobTokenIds", []))
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    if len(tokens) < 2:
        return None
    end_time = parse_dt(raw.get("endDate"))
    if end_time is None:
        return None
    start_time = parse_dt(raw.get("eventStartTime")) or (end_time - dt.timedelta(seconds=series.slug_step))
    return MarketWindow(
        question=str(raw.get("question") or ""),
        up_token=str(tokens[0]),
        down_token=str(tokens[1]),
        start_time=start_time,
        end_time=end_time,
        slug=str(raw.get("slug") or ""),
        description=raw.get("description"),
        resolution_source=raw.get("resolutionSource"),
    )


def parse_tokens(raw: object) -> list[Any]:
    if isinstance(raw, str):
        return list(json.loads(raw))
    return list(raw or [])


def parse_dt(value: str | None) -> dt.datetime | None:
    if not value:
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


class PriceStream:
    def __init__(self, on_price: Callable[[PriceUpdate], Awaitable[None]]):
        self._on_price = on_price
        self._ws: websockets.WebSocketClientProtocol | None = None
        self._running = False
        self._connected_tokens: list[str] = []
        self._books: dict[str, dict[str, Any]] = {}
        self._prices: dict[str, PriceUpdate] = {}
        self._recv_task: asyncio.Task | None = None
        self._last_message_at = 0.0
        self._event_counts_since_read: Counter[str] = Counter()

    async def connect(self, token_ids: list[str]) -> None:
        self._connected_tokens = list(token_ids)
        self._running = True
        self._ws = await websockets.connect(CLOB_WS_URL)
        await self._subscribe(token_ids)
        self._recv_task = asyncio.create_task(self._recv_loop())

    async def switch_tokens(self, token_ids: list[str]) -> None:
        if not self._running:
            return
        old = list(self._connected_tokens)
        self._connected_tokens = list(token_ids)
        self._books.clear()
        self._prices.clear()
        if self._ws is None:
            await self.connect(token_ids)
            return
        if old:
            await self._ws.send(json.dumps({"assets_ids": old, "operation": "unsubscribe"}))
        await self._subscribe(token_ids)

    async def close(self) -> None:
        self._running = False
        if self._recv_task:
            self._recv_task.cancel()
            await asyncio.gather(self._recv_task, return_exceptions=True)
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    def bid_levels(self, token_id: str, max_age_sec: float | None = None) -> list[tuple[float, float]]:
        book = self._fresh_book(token_id, max_age_sec)
        return list(book.get("bids", [])) if book else []

    def ask_levels(self, token_id: str, max_age_sec: float | None = None) -> list[tuple[float, float]]:
        book = self._fresh_book(token_id, max_age_sec)
        return list(book.get("asks", [])) if book else []

    def book_age_sec(self, token_id: str) -> float | None:
        book = self._books.get(token_id)
        if not book:
            return None
        received_at = float(book.get("received_at") or 0.0)
        return max(0.0, time.monotonic() - received_at) if received_at > 0 else None

    def diagnostics(self, *, reset_counts: bool = False) -> dict[str, Any]:
        now = time.monotonic()
        row = {
            "last_message_age_ms": round((now - self._last_message_at) * 1000) if self._last_message_at else None,
            "event_counts_since_read": dict(self._event_counts_since_read),
            "subscribed_tokens": len(self._connected_tokens),
        }
        if reset_counts:
            self._event_counts_since_read.clear()
        return row

    async def _subscribe(self, token_ids: list[str]) -> None:
        assert self._ws is not None
        await self._ws.send(json.dumps({"type": "market", "assets_ids": token_ids, "operation": "subscribe", "custom_feature_enabled": True}))

    def _fresh_book(self, token_id: str, max_age_sec: float | None) -> dict[str, Any] | None:
        book = self._books.get(token_id)
        if not book:
            return None
        received_at = float(book.get("received_at") or 0.0)
        if max_age_sec is not None and received_at > 0 and time.monotonic() - received_at > max_age_sec:
            return None
        return book

    async def _recv_loop(self) -> None:
        while self._running:
            try:
                assert self._ws is not None
                async for msg in self._ws:
                    self._last_message_at = time.monotonic()
                    self._dispatch(msg)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.warning("CLOB websocket error: %s", exc)
                await asyncio.sleep(1.0)

    def _dispatch(self, raw: str) -> None:
        try:
            data = json.loads(raw)
        except (TypeError, json.JSONDecodeError):
            return
        events = data if isinstance(data, list) else [data]
        for event in events:
            if isinstance(event, dict):
                self._handle_event(event)

    def _handle_event(self, event: dict[str, Any]) -> None:
        event_type = str(event.get("event_type") or "missing")
        self._event_counts_since_read[event_type] += 1
        if event_type == "book":
            self._handle_book(event)
        elif event_type == "price_change":
            self._handle_price_change(event)
        elif event_type == "best_bid_ask":
            self._handle_best_bid_ask(event)

    def _handle_book(self, event: dict[str, Any]) -> None:
        token = str(event.get("asset_id") or "")
        if not token:
            return
        now = time.monotonic()
        bids = parse_book_side(event.get("bids", []), reverse=True)
        asks = parse_book_side(event.get("asks", []), reverse=False)
        self._books[token] = {"bids": bids, "asks": asks, "received_at": now}
        self._prices[token] = PriceUpdate(token, bids[0][0] if bids else None, asks[0][0] if asks else None, "book", now)

    def _handle_price_change(self, event: dict[str, Any]) -> None:
        changes = event.get("price_changes", []) or ([event] if event.get("price") is not None else [])
        for change in changes:
            token = str(change.get("asset_id") or "")
            if not token:
                continue
            try:
                price = float(change.get("price"))
                size = float(change.get("size", 0))
            except (TypeError, ValueError):
                continue
            side_key = "bids" if change.get("side") == "BUY" else "asks" if change.get("side") == "SELL" else None
            if side_key is not None:
                self._apply_book_change(token, side_key, price, size)

    def _handle_best_bid_ask(self, event: dict[str, Any]) -> None:
        token = str(event.get("asset_id") or "")
        if not token:
            return
        try:
            bid = float(event["best_bid"]) if event.get("best_bid") is not None else None
            ask = float(event["best_ask"]) if event.get("best_ask") is not None else None
        except (TypeError, ValueError):
            return
        self._prices[token] = PriceUpdate(token, bid, ask, "best_bid_ask", time.monotonic())

    def _apply_book_change(self, token: str, side_key: str, price: float, size: float) -> None:
        book = self._books.setdefault(token, {"bids": [], "asks": [], "received_at": time.monotonic()})
        levels = list(book.get(side_key, []))
        kept = [(level_price, level_size) for level_price, level_size in levels if abs(level_price - price) > 1e-9]
        if size > 0:
            kept.append((price, size))
        kept.sort(key=lambda item: item[0], reverse=(side_key == "bids"))
        book[side_key] = kept
        book["received_at"] = time.monotonic()


def parse_book_side(levels: list[dict[str, Any]], *, reverse: bool) -> list[tuple[float, float]]:
    parsed: list[tuple[float, float]] = []
    for level in levels:
        try:
            price = float(level.get("price"))
            size = float(level.get("size", 0))
        except (AttributeError, TypeError, ValueError):
            continue
        if size > 0:
            parsed.append((price, size))
    parsed.sort(key=lambda item: item[0], reverse=reverse)
    return parsed
