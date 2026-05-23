# AGENTS.md - Poly Bot

## Project Intent

`poly-bot` is a clean research workspace for cross-platform prediction-market
arbitrage. It is not a continuation of `wild-poly`'s BTC direction strategy.

Use this repo for:

- Polymarket/Kalshi/SX.bet/sportsbook market discovery research.
- Same-event mapping across venues.
- Resolution-rule and market-text comparison.
- Order-book normalization.
- Executable arbitrage calculation after fees, slippage, and partial-fill risk.
- Read-only evidence logging for opportunities.

Do not use this repo for:

- BTC 5-minute direction prediction experiments.
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
- Treat KOL screenshots and extreme ROI claims as untrusted until reproduced
  with raw order-book evidence.
- A real arbitrage must include both legs' executable depth, fees,
  settlement/rule compatibility, and a safety buffer.
- Distinguish true arbitrage from market making. If one leg is a resting order
  waiting for fill, it is inventory risk, not risk-free arbitrage.
- Log every detected opportunity with enough fields to replay the calculation.
- Do not call anything risk-free unless both sides are already executable and
  the rules are compatible.

## Initial Strategy Direction

Priority order:

1. Cross-venue same-event scanner: Polymarket vs Kalshi/SX.bet/sportsbooks.
2. Polymarket internal combinatorial arbitrage scanner.
3. Liquidity rewards/rebate research.
4. New-market queue-priority research.

No live mode until explicitly requested and protected by a risk flag.

## Secret Handling

Do not commit API keys, account configs, private keys, cookies, session tokens,
or VPS passwords.
