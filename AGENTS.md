# AGENTS.md - Poly Bot

## Project Intent

`poly-bot` is a clean research workspace for prediction-market strategy
research. It is not a continuation of `wild-poly`'s BTC direction strategy.

The current priority is Polymarket BTC 5-minute truth-price gap research:
record whether the real BTC reference price has already moved away from the
window open while Polymarket still prices the true side cheaply enough to be
interesting.

Use this repo for:

- Read-only BTC 5-minute truth-price gap collection.
- Chainlink/reference-price timing research.
- Polymarket order-book normalization.
- Replayable JSONL evidence logs.
- Later, Polymarket/Kalshi/SX.bet/sportsbook same-event market discovery.
- Later, executable arbitrage calculation after fees, slippage, and partial-fill
  risk.

Do not use this repo for:

- Importing or continuing `wild-poly`'s BTC direction prediction experiments.
- Copying `wild-poly` strategy logic.
- Live trading before scanner evidence exists.

## Relationship To Other Repos

`wild-poly` may be used only as a reference for safe JSONL logging, dashboard
ideas, and Polymarket API familiarity. Do not import `wild_poly.*`.

`new-poly` is historical reference only. Do not import `new_poly.*` and do not
use its virtualenv.

`poly-bot` must own its dependencies through this repo's `requirements.txt`.

## Local Development

Use the repo-local virtualenv:

```bash
cd /Users/forrestliao/workspace/poly-bot
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest
```

Rules:

- `.venv/` is local-only and ignored by git.
- Do not use `../wild-poly/.venv` or `../new-poly/.venv`.
- If a dependency is needed, add it to `requirements.txt`.

## Research Rules

- Start read-only. Scanner first, execution later.
- The current collector must not read account config, private keys, cookies, or
  CLOB auth. It uses public Gamma, CLOB market websocket, and Polymarket
  live-data Chainlink feeds only.
- For BTC 5m truth-price gap logs, preserve enough raw evidence to replay new
  thresholds later: open/reference price, reference age, UP/DOWN bid/ask,
  shallow depth levels, truth side, market side, and settlement estimate.
- Separate truth-price edge research from old order-book strength heuristics.
  Do not promote a strategy because post/pre depth “looks strong” unless the
  truth-price gap data supports it.
- Treat KOL screenshots and extreme ROI claims as untrusted until reproduced
  with raw order-book evidence.
- A real arbitrage must include both legs' executable depth, fees,
  settlement/rule compatibility, and a safety buffer.
- Distinguish true arbitrage from market making. If one leg is a resting order
  waiting for fill, it is inventory risk, not risk-free arbitrage.
- Log every detected opportunity with enough fields to replay the calculation.
- Do not call anything risk-free unless both sides are already executable and
  the rules are compatible.

## Current Scripts

Truth-price gap collector:

```bash
cd /Users/forrestliao/workspace/poly-bot
.venv/bin/python scripts/collect_truth_price_gap.py \
  --windows 12 \
  --interval-sec 1 \
  --preopen-sec 60 \
  --postopen-sec 300 \
  --levels 5 \
  --jsonl data/truth-gap-12w-$(date -u +%Y%m%dT%H%M%SZ).jsonl
```

Important event names:

- `config`
- `window_selected`
- `sample`
- `settlement_estimate`

Priority order now:

1. Polymarket BTC 5m truth-price gap collector and replay analysis.
2. Cross-venue same-event scanner: Polymarket vs Kalshi/SX.bet/sportsbooks.
3. Polymarket internal combinatorial arbitrage scanner.
4. Liquidity rewards/rebate research.
5. New-market queue-priority research.

No live mode until explicitly requested and protected by a risk flag.

## Secret Handling

Do not commit API keys, account configs, private keys, cookies, session tokens,
or VPS passwords.
