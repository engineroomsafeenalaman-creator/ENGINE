import os
import time
import logging
import threading
import requests

from datetime import datetime, timezone
from flask import Flask, jsonify

# ==========================================
# CONFIG
# ==========================================

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")

TOP_SEARCH_URL = (
    "https://web3.binance.com/bapi/defi/v1/public/"
    "wallet-direct/buw/wallet/market/token/pulse/"
    "unified/rank/list/ai"
)

FUTURES_URL = "https://fapi.binance.com"
CG_URL = "https://api.coingecko.com/api/v3"

WAIT_SECONDS = 60
TOP_N = 3
MIN_RATIO_CHANGE = 0.001
COIN_COOLDOWN = 300

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.binance.com/"
}

session = requests.Session()
coin_last_alert = {}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("OI_MC_RADAR")

app = Flask(__name__)

# ==========================================
# FLASK
# ==========================================

@app.route("/")
def home():
    return jsonify({"status": "online"})

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

# ==========================================
# REQUEST
# ==========================================

def get_json(url, method="GET", params=None, body=None,
             headers=None):

    try:
        response = session.request(
            method,
            url,
            params=params,
            json=body,
            headers=headers or HEADERS,
            timeout=15
        )

        if response.status_code in (418, 429):
            log.warning("Rate limited: %s", url)
            time.sleep(60)
            return None

        response.raise_for_status()
        return response.json()

    except Exception as e:
        log.error("Request error: %s", e)
        return None

# ==========================================
# TOP 10 SEARCH
# ==========================================

def get_top_search():

    data = get_json(
        TOP_SEARCH_URL,
        method="POST",
        body={
            "rankType": 11,
            "sortBy": 2,
            "orderAsc": False,
            "page": 1,
            "size": 10
        }
    )

    if not isinstance(data, dict):
        return None

    result = data.get("data")

    if isinstance(result, dict):
        result = result.get("tokens", [])

    if not isinstance(result, list):
        return None

    symbols = []

    for item in result:
        if isinstance(item, dict) and item.get("symbol"):
            symbols.append(item["symbol"].upper().strip())

    return list(dict.fromkeys(symbols)) or None

# ==========================================
# COINGECKO MARKET CAP
# ==========================================

def get_marketcaps(symbols):

    headers = {
        "User-Agent": "OI-MC-Radar"
    }

    if COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = COINGECKO_API_KEY

    data = get_json(
        f"{CG_URL}/coins/markets",
        params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "sparkline": "false"
        },
        headers=headers
    )

    if not isinstance(data, list):
        return None

    result = {}

    for item in data:

        symbol = item.get("symbol", "").upper()
        mc = item.get("market_cap")

        if symbol in symbols and mc:

            rank = item.get("market_cap_rank") or 999999

            if (
                symbol not in result
                or rank < result[symbol]["rank"]
            ):
                result[symbol] = {
                    "market_cap": float(mc),
                    "name": item.get("name", symbol),
                    "rank": rank
                }

    return result

# ==========================================
# BINANCE FUTURES MAP
# ==========================================

def get_futures_map():

    data = get_json(
        f"{FUTURES_URL}/fapi/v1/exchangeInfo"
    )

    if not isinstance(data, dict):
        return None

    result = {}

    for item in data.get("symbols", []):

        if (
            item.get("status") == "TRADING"
            and item.get("quoteAsset") == "USDT"
            and item.get("contractType") == "PERPETUAL"
        ):

            base = item.get("baseAsset", "").upper()

            result.setdefault(base, item["symbol"])

    return result

# ==========================================
# BUILD TARGETS
# ==========================================

def build_targets():

    top = get_top_search()

    if not top:
        return None

    marketcaps = get_marketcaps(top)

    if not marketcaps:
        return None

    futures = get_futures_map()

    if not futures:
        return None

    targets = []

    for token in top:

        if token not in marketcaps or token not in futures:
            continue

        targets.append({
            "symbol": futures[token],
            "base": token,
            "name": marketcaps[token]["name"],
            "market_cap": marketcaps[token]["market_cap"]
        })

    log.info("TARGETS: %s", [x["symbol"] for x in targets])

    return targets or None

# ==========================================
# GET OI + MARK PRICE
# ==========================================

def snapshot(targets):

    prices = get_json(
        f"{FUTURES_URL}/fapi/v1/premiumIndex"
    )

    if not isinstance(prices, list):
        return None

    price_map = {
        x["symbol"]: float(x["markPrice"])
        for x in prices
        if x.get("symbol") and x.get("markPrice")
    }

    result = {}

    for coin in targets:

        symbol = coin["symbol"]
        price = price_map.get(symbol)

        if not price:
            continue

        data = get_json(
            f"{FUTURES_URL}/fapi/v1/openInterest",
            params={"symbol": symbol}
        )

        if not isinstance(data, dict):
            continue

        try:
            oi = float(data["openInterest"])
        except (KeyError, TypeError, ValueError):
            continue

        oi_usd = oi * price

        ratio = (
            oi_usd / coin["market_cap"]
        ) * 100

        result[symbol] = {
            **coin,
            "oi": oi,
            "price": price,
            "oi_usd": oi_usd,
            "ratio": ratio
        }

    return result or None

# ==========================================
# CALCULATE CHANGE
# ==========================================

def calculate(before, after):

    results = []

    for symbol, old in before.items():

        new = after.get(symbol)

        if not new or old["ratio"] <= 0:
            continue

        change = (
            (new["ratio"] - old["ratio"])
            / old["ratio"]
        ) * 100

        if change > MIN_RATIO_CHANGE:

            results.append({
                **new,
                "previous_ratio": old["ratio"],
                "ratio_change": change
            })

    results.sort(
        key=lambda x: x["ratio_change"],
        reverse=True
    )

    return results

# ==========================================
# DISCORD
# ==========================================

def send_discord(coins):

    if not DISCORD_WEBHOOK_URL:
        log.error("Discord webhook missing")
        return

    now = time.time()

    eligible = [
        c for c in coins
        if now - coin_last_alert.get(c["symbol"], 0)
        >= COIN_COOLDOWN
    ][:TOP_N]

    if not eligible:
        return

    fields = []

    for i, coin in enumerate(eligible, 1):

        fields.append({
            "name": f"#{i} {coin['symbol']} 🚨",
            "value": (
                f"**Market Cap:** `${coin['market_cap']:,.0f}`\n"
                f"**OI USD:** `${coin['oi_usd']:,.0f}`\n"
                f"**OI / MC:** `{coin['ratio']:.6f}%`\n"
                f"**Previous Ratio:** "
                f"`{coin['previous_ratio']:.6f}%`\n"
                f"**Ratio Change:** "
                f"`+{coin['ratio_change']:.4f}%`\n"
                f"**Mark Price:** `{coin['price']}`"
            ),
            "inline": False
        })

    payload = {
        "username": "Binance OI/MC Radar",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": "🚨 OI / MARKET CAP ALERT",
            "description": (
                f"Ratio increase > `{MIN_RATIO_CHANGE}%`\n"
                f"Interval: `{WAIT_SECONDS}s`"
            ),
            "color": 16753920,
            "fields": fields,
            "footer": {
                "text": "Binance Futures | CoinGecko MarketCap"
            },
            "timestamp": datetime.now(
                timezone.utc
            ).isoformat()
        }]
    }

    try:

        response = session.post(
            DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=15
        )

        if response.status_code in (200, 204):

            for coin in eligible:
                coin_last_alert[coin["symbol"]] = now

            log.info("DISCORD ALERT SENT")

        else:
            log.error(
                "Discord HTTP %s: %s",
                response.status_code,
                response.text[:200]
            )

    except requests.RequestException:
        log.exception("Discord error")

# ==========================================
# MAIN
# ==========================================

def main():

    log.info("OI MARKETCAP RADAR STARTED")

    targets = None
    before = None

    last_refresh = 0

    while True:

        try:

            now = time.monotonic()

            if (
                targets is None
                or now - last_refresh >= 600
            ):

                new_targets = build_targets()

                if new_targets:

                    new_snapshot = snapshot(new_targets)

                    if new_snapshot:

                        targets = new_targets
                        before = new_snapshot
                        last_refresh = time.monotonic()

                        log.info("TARGETS UPDATED")

                if targets is None:
                    time.sleep(60)
                    continue

            time.sleep(WAIT_SECONDS)

            after = snapshot(targets)

            if not after:
                continue

            # Require complete snapshot
            if any(s not in after for s in before):
                log.warning("Incomplete snapshot")
                continue

            results = calculate(before, after)

            for coin in results[:10]:

                log.info(
                    "%s | OI/MC %.6f%% | CHANGE +%.4f%%",
                    coin["symbol"],
                    coin["ratio"],
                    coin["ratio_change"]
                )

            if results:
                send_discord(results)

            before = after

        except Exception:
            log.exception("Scanner error")
            time.sleep(10)

# ==========================================
# START
# ==========================================

if __name__ == "__main__":

    port = int(os.getenv("PORT", "10000"))

    threading.Thread(
        target=main,
        daemon=True
    ).start()

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,
        use_reloader=False
    )
