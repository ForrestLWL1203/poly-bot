from __future__ import annotations

from poly_bot.chainlink import price_ticks_from_message, subscribe_message


def test_subscribe_message_filters_btc_usd() -> None:
    message = subscribe_message("BTC/USD")

    assert message["action"] == "subscribe"
    assert message["subscriptions"][0]["topic"] == "crypto_prices_chainlink"
    assert '"symbol":"btc/usd"' in message["subscriptions"][0]["filters"]


def test_price_ticks_from_message_parses_single_payload() -> None:
    ticks = price_ticks_from_message({"payload": {"timestamp": 1_700_000_000_000, "value": "100123.45"}})

    assert ticks == [(1_700_000_000.0, 100123.45)]


def test_price_ticks_from_message_parses_batch_and_skips_bad_rows() -> None:
    ticks = price_ticks_from_message(
        {
            "payload": {
                "data": [
                    {"timestamp": 1_700_000_001_000, "value": "100001"},
                    {"timestamp": "bad", "value": "100002"},
                    {"timestamp": 1_700_000_002_000, "value": 100003},
                ]
            }
        }
    )

    assert ticks == [(1_700_000_001.0, 100001.0), (1_700_000_002.0, 100003.0)]
