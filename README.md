# Poly Bot

Prediction-market research lab.

This repository is intentionally separate from `wild-poly`. The current focus
is not another盘口强弱方向策略, but a cleaner BTC 5-minute question:

> When the real BTC reference price has already moved away from the window
> open, is Polymarket still pricing the correct side cheaply enough to create
> an edge?

## First Goal

Build a read-only truth-price gap collector for Polymarket BTC 5-minute
markets. It records:

- window open/reference price
- Chainlink latest price and update age
- Polymarket UP/DOWN bid/ask and shallow depth
- truth side from reference price vs open price
- market side from bid/ask
- truth-price gap fields
- later settlement estimate

No live trading should be added until collected logs prove a repeatable edge.

## Initial Modules

- `poly_bot.truth_gap`: pure truth-price gap calculations.
- `poly_bot.polymarket`: read-only Polymarket Gamma/CLOB helpers.
- `poly_bot.chainlink`: read-only Polymarket live-data Chainlink BTC feed.
- `poly_bot.jsonl`: JSONL evidence writer.
- `poly_bot.arb`: early cross-venue arbitrage primitives, currently secondary.
- `scripts/collect_truth_price_gap.py`: BTC 5m truth-price gap collector.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest
```

## Collect Truth-Price Gap Data

```bash
.venv/bin/python scripts/collect_truth_price_gap.py \
  --windows 12 \
  --interval-sec 1 \
  --preopen-sec 60 \
  --postopen-sec 300 \
  --levels 5 \
  --jsonl data/truth-gap-12w-$(date -u +%Y%m%dT%H%M%SZ).jsonl
```

The collector is public-data-only and does not read account config or submit
orders.
