import os
import time
import logging
import threading
import requests

from flask import Flask, jsonify

# ==========================================
# 1. CONFIG
# ==========================================

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY")

TOP_SEARCH_URL = (
    "https://web3.binance.com/bapi/defi/v1/public/"
    "wallet-direct/buw/wallet/market/token/pulse/"
    "unified/rank/list/ai"
)

FUTURES_URL = "https://fapi.binance.com"

COINGECKO_URL = (
    "https://api.coingecko.com/api/v3/coins/markets"
)

WAIT_SECONDS = 60

MIN_OI_CHANGE = 0.001

TOP_N = 3

COIN_COOLDOWN = 300

TOP_REFRESH = 600

MARKETCAP_REFRESH = 1800

REQUEST_INTERVAL = 0.5

# Market Cap filter (USD)
MIN_MARKET_CAP = 1_000_000
MAX_MARKET_CAP = 100_000_000_000

# Number of Top Search tokens
TOP_SEARCH_SIZE = 10

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Accept-Encoding": "identity",
    "Referer": "https://www.binance.com/"
}

# ==========================================
# 2. LOGGING
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("BINANCE_MARKETCAP_OI")

# ==========================================
# 3. GLOBAL STATE
# ==========================================

session = requests.Session()

api_lock = threading.Lock()

api_block_until = 0.0

next_request_time = 0.0

coin_last_alert = {}

marketcap_cache = {}

# ==========================================
# 4. FLASK
# ==========================================

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "bot": "Binance Top Search MarketCap OI Radar"
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

# ==========================================
# 5. REQUEST HANDLER
# ==========================================

def get_json(url, method="GET", params=None, body=None,
             headers=None):

    global api_block_until, next_request_time

    with api_lock:

        now = time.monotonic()

        if now < api_block_until:
            return None

        wait = next_request_time - now

        if wait > 0:
            time.sleep(wait)

        next_request_time = (
            time.monotonic() + REQUEST_INTERVAL
        )

    try:

        response = session.request(
            method,
            url,
            params=params,
            json=body,
            headers=headers or HEADERS,
            timeout=20
        )

        if response.status_code in (418, 429):

            retry_after = response.headers.get("Retry-After")

            try:
                delay = float(retry_after)
            except (TypeError, ValueError):
                delay = 900 if response.status_code == 418 else 60

            delay = max(60, delay)

            with api_lock:
                api_block_until = max(
                    api_block_until,
                    time.monotonic() + delay
                )

            log.error(
                "HTTP %s. Cooldown %.0f seconds",
                response.status_code,
                delay
            )

            return None

        if response.status_code in (403, 451):
            log.error("Access restricted: %s",
                      response.status_code)
            return None

        response.raise_for_status()

        return response.json()

    except requests.RequestException as e:
        log.error("Request failed: %s", e)

    except ValueError:
        log.error("Invalid JSON")

    return None

# ==========================================
# 6. BINANCE TOP SEARCH
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
            "size": TOP_SEARCH_SIZE
        }
    )

    if not isinstance(data, dict):
        return None

    result = data.get("data")

    if isinstance(result, dict):
        result = result.get("tokens", [])

    if not isinstance(result, list):
        return None

    tokens = []

    for item in result:

        if not isinstance(item, dict):
            continue

        symbol = item.get("symbol")

        if symbol:
            tokens.append(symbol.upper().strip())

    tokens = list(dict.fromkeys(tokens))

    log.info("TOP SEARCH: %s", tokens)

    return tokens if tokens else None

# ==========================================
# 7. COINGECKO MARKET CAP
# ==========================================

def get_marketcap_data():

    headers = {
        "Accept": "application/json",
        "User-Agent": "MarketCap-OI-Radar"
    }

    if COINGECKO_API_KEY:
        headers["x-cg-demo-api-key"] = COINGECKO_API_KEY

    data = get_json(
        COINGECKO_URL,
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
        log.error("CoinGecko MarketCap unavailable")
        return None

    result = {}

    for item in data:

        symbol = item.get("symbol", "").upper()

        market_cap = item.get("market_cap")

        name = item.get("name", "")

        if not symbol or not market_cap:
            continue

        result.setdefault(symbol, {
            "name": name,
            "market_cap": float(market_cap)
        })

    log.info("MARKETCAP DATA: %s", len(result))

    return result if result else None

# ==========================================
# 8. BINANCE FUTURES SYMBOL MAP
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

            symbol = item.get("symbol")

            if base and symbol:
                result.setdefault(base, symbol)

    log.info("FUTURES SYMBOLS: %s", len(result))

    return result

# ==========================================
# 9. BUILD TARGETS
# ==========================================

def build_targets():

    top = get_top_search()

    if not top:
        return None

    marketcap = get_marketcap_data()

    if not marketcap:
        return None

    futures = get_futures_map()

    if not futures:
        return None

    targets = []

    for token in top:

        if token not in marketcap:
            log.info("%s missing MarketCap", token)
            continue

        mc = marketcap[token]["market_cap"]

        if not (
            MIN_MARKET_CAP <= mc <= MAX_MARKET_CAP
        ):
            continue

        if token not in futures:
            continue

        targets.append({
            "symbol": futures[token],
            "base": token,
            "name": marketcap[token]["name"],
            "market_cap": mc
        })

    log.info(
        "MATCHED TOP SEARCH + MARKETCAP + FUTURES: %s",
        len(targets)
    )

    for coin in targets:
        log.info(
            "%s | MC: $%s",
            coin["symbol"],
            f"{coin['market_cap']:,.0f}"
        )

    return targets if targets else None

# ==========================================
# 10. FETCH OPEN INTEREST
# ==========================================

def fetch_oi(symbol):

    data = get_json(
        f"{FUTURES_URL}/fapi/v1/openInterest",
        params={"symbol": symbol}
    )

    if not isinstance(data, dict):
        return None

    try:
        return float(data["openInterest"])
    except (KeyError, TypeError, ValueError):
        return None

# ==========================================
# 11. SNAPSHOT
# ==========================================

def snapshot_oi(targets):

    snapshot = {}

    for coin in targets:

        symbol = coin["symbol"]

        oi = fetch_oi(symbol)

        if oi is not None and oi > 0:

            snapshot[symbol] = {
                "oi": oi,
                "market_cap": coin["market_cap"],
                "base": coin["base"],
                "name": coin["name"]
            }

    log.info(
        "OI SNAPSHOT: %s/%s",
        len(snapshot),
        len(targets)
    )

    return snapshot if snapshot else None

# ==========================================
# 12. CALCULATE OI CHANGE
# ==========================================

def calculate_results(before, after):

    results = []

    for symbol, previous in before.items():

        current = after.get(symbol)

        if current is None:
            continue

        old_oi = previous["oi"]
        new_oi = current["oi"]

        if old_oi <= 0:
            continue

        change = (
            (new_oi - old_oi) / old_oi
        ) * 100

        if change > MIN_OI_CHANGE:

            results.append({
                "symbol": symbol,
                "base": current["base"],
                "name": current["name"],
                "market_cap": current["market_cap"],
                "oi_change_pct": change,
                "previous_oi": old_oi,
                "current_oi": new_oi
            })

    results.sort(
        key=lambda x: x["oi_change_pct"],
        reverse=True
    )

    return results

# ==========================================
# 13. DISCORD ALERT
# ==========================================

def send_discord(coins):

    if not DISCORD_WEBHOOK_URL:
        log.error("Discord webhook missing")
        return

    now = time.time()

    eligible = [
        coin for coin in coins
        if now - coin_last_alert.get(
            coin["symbol"], 0
        ) >= COIN_COOLDOWN
    ][:TOP_N]

    if not eligible:
        return

    fields = []

    for index, coin in enumerate(eligible, 1):

        fields.append({
            "name": f"#{index} {coin['symbol']} 🟢",
            "value": (
                f"**Name:** `{coin['name']}`\n"
                f"**OI Increase:** `+{coin['oi_change_pct']:.4f}%`\n"
                f"**Previous OI:** `{coin['previous_oi']:,.4f}`\n"
                f"**Current OI:** `{coin['current_oi']:,.4f}`\n"
                f"**Market Cap:** `${coin['market_cap']:,.0f}`"
            ),
            "inline": False
        })

    payload = {
        "username": "Binance MarketCap OI Radar",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": "🚨 BINANCE TOP SEARCH OI ALERT",
            "description": (
                f"OI Increase > `{MIN_OI_CHANGE}%`\n"
                f"MarketCap source: CoinGecko\n"
                f"Comparison: {WAIT_SECONDS}-second snapshot"
            ),
            "color": 5763719,
            "fields": fields,
            "footer": {
                "text": "Binance Futures | Top Search + MarketCap Radar"
            },
            "timestamp": (
                __import__("datetime")
                .datetime.now(__import__("datetime").timezone.utc)
                .isoformat()
            )
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

        elif response.status_code == 429:
            log.warning("Discord rate limit")

        else:
            log.error(
                "Discord HTTP %s: %s",
                response.status_code,
                response.text[:300]
            )

    except requests.RequestException:
        log.exception("Discord connection failed")

# ==========================================
# 14. MAIN SCANNER
# ==========================================

def main():

    log.info("BINANCE TOP SEARCH MARKETCAP OI STARTED")

    targets = None
    before = None

    last_refresh = 0

    while True:

        try:

            now = time.monotonic()

            if (
                targets is None
                or now - last_refresh >= TOP_REFRESH
            ):

                new_targets = build_targets()

                if new_targets:

                    new_snapshot = snapshot_oi(new_targets)

                    if new_snapshot:

                        targets = new_targets
                        before = new_snapshot

                        last_refresh = time.monotonic()

                        log.info("TARGETS UPDATED")

                if targets is None:

                    log.warning("Initialization failed")

                    time.sleep(60)
                    continue

            time.sleep(WAIT_SECONDS)

            after = snapshot_oi(targets)

            if after is None:
                log.warning("Snapshot failed")
                continue

            if any(
                coin["symbol"] not in after
                for coin in targets
            ):
                log.warning("Incomplete snapshot; skipping")
                continue

            results = calculate_results(before, after)

            log.info(
                "OI INCREASE ABOVE %.5f%%: %s",
                MIN_OI_CHANGE,
                len(results)
            )

            for coin in results[:10]:

                log.info(
                    "%s | OI +%.4f%% | MC $%s",
                    coin["symbol"],
                    coin["oi_change_pct"],
                    f"{coin['market_cap']:,.0f}"
                )

            if results:
                send_discord(results)

            before = after

        except Exception:

            log.exception("Scanner error")
            time.sleep(10)

# ==========================================
# 15. START SERVER
# ==========================================

if __name__ == "__main__":

    port = int(os.getenv("PORT", "10000"))

    bot = threading.Thread(
        target=main,
        daemon=True
    )

    bot.start()

    log.info("HTTP SERVER PORT: %s", port)

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,
        use_reloader=False
    )
