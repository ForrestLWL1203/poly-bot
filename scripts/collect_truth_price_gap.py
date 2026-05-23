#!/usr/bin/env python3
"""Collect truth-price gap evidence for Polymarket BTC 5-minute windows.

This script is read-only. It subscribes to public Polymarket order-book and
live BTC reference-price feeds, then writes replay-grade JSONL samples.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from poly_bot.chainlink import ChainlinkBtcFeed
from poly_bot.jsonl import JsonlWriter, utc_now_iso
from poly_bot.polymarket import Btc5mSeries, MarketWindow, PriceStream, PriceUpdate, find_window_after
from poly_bot.truth_gap import TruthGapInputs, compute_truth_gap, side_book

UTC = dt.timezone.utc


def utc_timestamp() -> str:
    return dt.datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def default_jsonl_path() -> Path:
    return ROOT / "data" / f"truth-gap-{utc_timestamp()}.jsonl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--windows", type=int, default=12, help="Number of complete BTC 5m windows to collect.")
    parser.add_argument("--interval-sec", type=float, default=1.0, help="Sample interval in seconds.")
    parser.add_argument("--preopen-sec", type=float, default=60.0, help="Seconds before window open to start sampling.")
    parser.add_argument("--postopen-sec", type=float, default=300.0, help="Seconds after window open to keep sampling.")
    parser.add_argument("--levels", type=int, default=5, help="Book depth levels to log for each side.")
    parser.add_argument("--max-book-age-sec", type=float, default=5.0, help="Reject book levels older than this age.")
    parser.add_argument("--open-forward-sec", type=float, default=5.0, help="Max seconds after window start for open reference.")
    parser.add_argument("--close-forward-sec", type=float, default=90.0, help="Max seconds after window end for close reference.")
    parser.add_argument("--jsonl", type=Path, default=default_jsonl_path(), help="Output JSONL path.")
    return parser.parse_args()


async def noop_price_update(_update: PriceUpdate) -> None:
    return None


async def wait_until(epoch: float) -> None:
    while True:
        delay = epoch - time.time()
        if delay <= 0:
            return
        await asyncio.sleep(min(delay, 1.0))


def price_source_for_open(feed: ChainlinkBtcFeed, start_epoch: int, forward_sec: float) -> tuple[float | None, str | None]:
    first_after = feed.first_price_at_or_after(start_epoch, max_forward_sec=forward_sec)
    if first_after is not None:
        return first_after, "chainlink_first_after_open"
    before = feed.price_at_or_before(start_epoch, max_backward_sec=2.0)
    if before is not None:
        return before, "chainlink_before_open"
    return None, None


def close_price_for_window(feed: ChainlinkBtcFeed, end_epoch: int, forward_sec: float) -> tuple[float | None, str | None]:
    first_after = feed.first_price_at_or_after(end_epoch, max_forward_sec=forward_sec)
    if first_after is not None:
        return first_after, "chainlink_first_after_close"
    before = feed.price_at_or_before(end_epoch, max_backward_sec=2.0)
    if before is not None:
        return before, "chainlink_before_close"
    return None, None


def phase_and_age(window: MarketWindow, now_epoch: float) -> tuple[str, float | None, float | None]:
    age = now_epoch - window.start_epoch
    to_start = window.start_epoch - now_epoch
    phase = "preopen" if age < 0 else "postopen"
    return phase, age, to_start


def window_event(window: MarketWindow, *, index: int, total: int) -> dict[str, Any]:
    return {
        "e": "window_selected",
        "schema": "truth_price_gap_v1",
        "ts": utc_now_iso(),
        "index": index,
        "total": total,
        "slug": window.slug,
        "question": window.question,
        "start": window.start_time.isoformat(),
        "end": window.end_time.isoformat(),
        "up_token": window.up_token,
        "down_token": window.down_token,
    }


def sample_event(
    *,
    window: MarketWindow,
    feed: ChainlinkBtcFeed,
    stream: PriceStream,
    args: argparse.Namespace,
    open_price: float | None,
    open_source: str | None,
) -> dict[str, Any]:
    now_epoch = time.time()
    phase, age, to_start = phase_and_age(window, now_epoch)
    up_bids = stream.bid_levels(window.up_token, args.max_book_age_sec)
    up_asks = stream.ask_levels(window.up_token, args.max_book_age_sec)
    down_bids = stream.bid_levels(window.down_token, args.max_book_age_sec)
    down_asks = stream.ask_levels(window.down_token, args.max_book_age_sec)
    up_age = stream.book_age_sec(window.up_token)
    down_age = stream.book_age_sec(window.down_token)
    up = side_book(bid_levels=up_bids, ask_levels=up_asks, depth=args.levels, bid_age_sec=up_age, ask_age_sec=up_age)
    down = side_book(bid_levels=down_bids, ask_levels=down_asks, depth=args.levels, bid_age_sec=down_age, ask_age_sec=down_age)
    reference_price = feed.latest_price
    truth_gap = compute_truth_gap(
        TruthGapInputs(
            open_price=open_price,
            reference_price=reference_price,
            up_ask=up["ba"],
            down_ask=down["ba"],
            up_bid=up["bb"],
            down_bid=down["bb"],
        )
    )
    warnings: list[str] = []
    if open_price is None:
        warnings.append("missing_open_price")
    if reference_price is None:
        warnings.append("missing_reference_price")
    if up["bb"] is None or up["ba"] is None or down["bb"] is None or down["ba"] is None:
        warnings.append("missing_book")
    if up_age is not None and up_age > args.max_book_age_sec:
        warnings.append("stale_up_book")
    if down_age is not None and down_age > args.max_book_age_sec:
        warnings.append("stale_down_book")

    return {
        "e": "sample",
        "schema": "truth_price_gap_v1",
        "ts": utc_now_iso(),
        "ts_epoch": now_epoch,
        "slug": window.slug,
        "phase": phase,
        "age": round(age, 3) if age is not None else None,
        "to_start": round(to_start, 3) if to_start is not None else None,
        "start": window.start_time.isoformat(),
        "end": window.end_time.isoformat(),
        "open_price": open_price,
        "open_source": open_source,
        "reference_price": reference_price,
        "reference_age_sec": feed.latest_age_sec(now_epoch),
        "up": up,
        "down": down,
        "truth_gap": truth_gap.to_dict(),
        "stream": stream.diagnostics(reset_counts=True),
        "warnings": warnings,
    }


def settlement_event(
    *,
    window: MarketWindow,
    feed: ChainlinkBtcFeed,
    open_price: float | None,
    open_source: str | None,
    args: argparse.Namespace,
) -> dict[str, Any]:
    close_price, close_source = close_price_for_window(feed, window.end_epoch, args.close_forward_sec)
    move_bps = None
    side = None
    if open_price is not None and close_price is not None and open_price > 0:
        move_bps = ((close_price - open_price) / open_price) * 10_000.0
        if move_bps > 0:
            side = "up"
        elif move_bps < 0:
            side = "down"
    return {
        "e": "settlement_estimate",
        "schema": "truth_price_gap_v1",
        "ts": utc_now_iso(),
        "slug": window.slug,
        "open_price": open_price,
        "open_source": open_source,
        "close_price": close_price,
        "close_source": close_source,
        "settlement_side": side,
        "move_bps": round(move_bps, 6) if move_bps is not None else None,
    }


async def collect_window(
    *,
    writer: JsonlWriter,
    feed: ChainlinkBtcFeed,
    stream: PriceStream,
    window: MarketWindow,
    index: int,
    args: argparse.Namespace,
) -> None:
    writer.write(window_event(window, index=index, total=args.windows))
    await stream.switch_tokens([window.up_token, window.down_token])
    sample_start = window.start_epoch - args.preopen_sec
    sample_end = window.start_epoch + args.postopen_sec
    await wait_until(sample_start)
    open_price: float | None = None
    open_source: str | None = None
    last_sample = 0.0
    while time.time() <= sample_end:
        if open_price is None and time.time() >= window.start_epoch:
            open_price, open_source = price_source_for_open(feed, window.start_epoch, args.open_forward_sec)
        now = time.time()
        if now - last_sample >= args.interval_sec:
            writer.write(sample_event(window=window, feed=feed, stream=stream, args=args, open_price=open_price, open_source=open_source))
            last_sample = now
        await asyncio.sleep(min(args.interval_sec / 4.0, 0.25))
    if open_price is None:
        open_price, open_source = price_source_for_open(feed, window.start_epoch, args.open_forward_sec)
    writer.write(settlement_event(window=window, feed=feed, open_price=open_price, open_source=open_source, args=args))


async def run(args: argparse.Namespace) -> None:
    args.jsonl.parent.mkdir(parents=True, exist_ok=True)
    feed = ChainlinkBtcFeed(max_history_sec=args.preopen_sec + args.postopen_sec + args.close_forward_sec + 300)
    stream = PriceStream(noop_price_update)
    series = Btc5mSeries()
    await feed.start()
    first_window = find_window_after(int(time.time()), series)
    if first_window is None:
        raise SystemExit("No future BTC 5m market found.")
    await stream.connect([first_window.up_token, first_window.down_token])
    try:
        with JsonlWriter(args.jsonl) as writer:
            writer.write(
                {
                    "e": "config",
                    "schema": "truth_price_gap_v1",
                    "ts": utc_now_iso(),
                    "args": {key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()},
                }
            )
            window = first_window
            for index in range(1, args.windows + 1):
                await collect_window(writer=writer, feed=feed, stream=stream, window=window, index=index, args=args)
                next_window = find_window_after(window.start_epoch + series.slug_step, series)
                if next_window is None:
                    raise SystemExit("No next BTC 5m market found.")
                window = next_window
    finally:
        await asyncio.gather(feed.stop(), stream.close(), return_exceptions=True)


def main() -> None:
    asyncio.run(run(parse_args()))


if __name__ == "__main__":
    main()
