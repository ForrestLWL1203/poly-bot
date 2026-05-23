# Poly Bot

Cross-market prediction-market arbitrage research lab.

This repository starts as a read-only scanner and evidence logger for pricing
gaps between Polymarket and other venues such as Kalshi, SX.bet, and
sportsbooks. It is intentionally separate from `wild-poly`, which focuses on
single-platform BTC 5-minute directional experiments.

## First Goal

Build a scanner that can answer one question reliably:

> Is there a real, executable, rule-compatible arbitrage between two venues
> after fees, slippage, and partial-fill risk?

No live trading should be added until the scanner has collected enough
evidence.

## Initial Modules

- `poly_bot.markets`: normalized market and outcome models.
- `poly_bot.venues`: venue clients and adapters.
- `poly_bot.arb`: cross-venue matching and executable edge calculation.
- `poly_bot.logging`: JSONL evidence logs for later analysis.
- `scripts/`: command-line scanners and research utilities.

## Setup

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest
```
