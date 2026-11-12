
import os
import time
import logging
import threading
import requests

from datetime import datetime, timezone
from flask import Flask, jsonify

# ==========================================
# 1. CONFIG
# ==========================================

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

TOP_SEARCH_URL = (
    "https://web3.binance.com/bapi/defi/v1/public/"
    "wallet-direct/buw/wallet/market/token/pulse/"
    "unified/rank/list/ai"
)

ALPHA_URL = (
    "https://www.binance.com/bapi/defi/v1/public/"
    "wallet-direct/buw/wallet/cex/alpha/all/token/list"
)

FUTURES_URL = "https://fapi.binance.com"

WAIT_SECONDS = 60
MIN_OI_CHANGE = 0.001
TOP_N = 3
COIN_COOLDOWN = 300

TOP_REFRESH = 600
ALPHA_REFRESH = 1800
REQUEST_INTERVAL = 0.5

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

log = logging.getLogger("ALPHA_RADAR")

# ==========================================
# 3. GLOBAL STATE
# ==========================================

session = requests.Session()

api_lock = threading.Lock()
api_block_until = 0.0
next_request_time = 0.0

coin_last_alert = {}

# ==========================================
# 4. FLASK
# ==========================================

app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "bot": "Binance Alpha OI Radar"
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

# ==========================================
# 5. BINANCE REQUEST HANDLER
# ==========================================

def get_json(url, method="GET", params=None, body=None):

    global api_block_until, next_request_time

    with api_lock:

        now = time.monotonic()

        if now < api_block_until:
            log.warning(
                "Binance cooldown: %.0f seconds remaining",
                api_block_until - now
            )
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
            headers=HEADERS,
            timeout=15
        )

        if response.status_code in (418, 429):

            retry_after = response.headers.get("Retry-After")

            try:
                delay = float(retry_after)
            except (TypeError, ValueError):
                delay = (
                    900 if response.status_code == 418
                    else 60
                )

            delay = max(60, delay)

            with api_lock:
                api_block_until = max(
                    api_block_until,
                    time.monotonic() + delay
                )

            log.error(
                "Binance HTTP %s. Pausing %.0f seconds",
                response.status_code,
                delay
            )

            return None

        if response.status_code in (403, 451):

            log.error(
                "Binance access restricted: HTTP %s",
                response.status_code
            )
            return None

        response.raise_for_status()

        return response.json()

    except requests.RequestException as e:

        log.error("Binance request failed: %s", e)

    except ValueError:

        log.error("Invalid Binance JSON")

    return None

# ==========================================
# 6. GET TOP 10 SEARCH
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

    if data.get("success") is False:
        log.error("Top Search API unsuccessful")
        return None

    result = data.get("data")

    if isinstance(result, dict):
        result = result.get("tokens", [])

    if not isinstance(result, list):
        log.error("Invalid Top Search response")
        return None

    symbols = []

    for item in result[:10]:

        if not isinstance(item, dict):
            continue

        symbol = item.get("symbol")

        if symbol:
            symbols.append(symbol.upper().strip())

    log.info("TOP SEARCH: %s", symbols)

    return symbols if symbols else None

# ==========================================
# 7. GET ALPHA TOKENS
# ==========================================

def get_alpha_tokens():

    data = get_json(ALPHA_URL)

    if not isinstance(data, dict):
        return None

    token_data = data.get("data")

    if isinstance(token_data, dict):
        token_data = (
            token_data.get("tokens")
            or token_data.get("list")
            or token_data.get("data")
        )

    if not isinstance(token_data, list):
        log.error("Invalid Alpha token response")
        return None

    symbols = set()

    for item in token_data:

        if not isinstance(item, dict):
            continue

        symbol = item.get("symbol")

        if symbol:
            symbols.add(symbol.upper().strip())

    log.info("ALPHA TOKENS: %s", len(symbols))

    return symbols if symbols else None

# ==========================================
# 8. MATCH FUTURES SYMBOLS
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
                result[base] = symbol

    log.info("FUTURES SYMBOLS: %s", len(result))

    return result

# ==========================================
# 9. BUILD TARGET LIST
# ==========================================

def build_targets():

    top = get_top_search()

    if not top:
        return None

    alpha = get_alpha_tokens()

    if not alpha:
        return None

    futures = get_futures_map()

    if not futures:
        return None

    targets = []

    for token in top:

        if token not in alpha:
            continue

        if token in futures:
            targets.append(futures[token])

    targets = list(dict.fromkeys(targets))

    log.info("MATCHED ALPHA COINS: %s", targets)

    if not targets:
        log.warning("No matching Alpha Futures in Top Search")
        return None

    return targets

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


def snapshot_oi(symbols):

    snapshot = {}

    for symbol in symbols:

        oi = fetch_oi(symbol)

        if oi is not None and oi > 0:
            snapshot[symbol] = oi

    log.info(
        "OI SNAPSHOT: %s/%s",
        len(snapshot),
        len(symbols)
    )

    if not snapshot:
        return None

    return snapshot

# ==========================================
# 11. CALCULATE OI INCREASE
# ==========================================

def calculate_results(before, after):

    results = []

    for symbol, previous in before.items():

        current = after.get(symbol)

        if current is None or previous <= 0:
            continue

        change = (
            (current - previous) / previous
        ) * 100

        # ONLY OI INCREASE ABOVE 0.001%

        if change > MIN_OI_CHANGE:

            results.append({
                "symbol": symbol,
                "oi_change_pct": change,
                "current_oi": current
            })

    results.sort(
        key=lambda x: x["oi_change_pct"],
        reverse=True
    )

    return results

# ==========================================
# 12. DISCORD NOTIFICATION
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
        log.info("No eligible Discord alerts")
        return

    fields = []

    for index, coin in enumerate(eligible, 1):

        fields.append({
            "name": f"#{index} {coin['symbol']} 🟢",
            "value": (
                f"**OI Increase:** "
                f"`+{coin['oi_change_pct']:.6f}%`\n"
                f"**Current OI:** "
                f"`{coin['current_oi']:,.4f}`"
            ),
            "inline": False
        })

    payload = {
        "username": "Binance Alpha OI Radar",
        "allowed_mentions": {"parse": []},
        "embeds": [{
            "title": "⚡ BINANCE ALPHA OI ALERT",
            "description": (
                f"OI increase above `{MIN_OI_CHANGE}%`\n"
                f"Comparison: previous 60-second snapshot"
            ),
            "color": 5763719,
            "fields": fields,
            "footer": {
                "text": "Binance Futures | Alpha Top Search Radar"
            }
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
# 13. MAIN SCANNER
# ==========================================

def main():

    log.info("BINANCE ALPHA OI RADAR STARTED")

    targets = None
    before = None

    last_refresh = 0

    while True:

        try:

            now = time.monotonic()

            # Refresh Top Search and Alpha targets

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

                    log.warning(
                        "Initialization failed. Retry in 60 seconds"
                    )

                    time.sleep(60)
                    continue

            cycle_start = time.monotonic()

            time.sleep(
                max(
                    0,
                    WAIT_SECONDS - (
                        time.monotonic() - cycle_start
                    )
                )
            )

            after = snapshot_oi(targets)

            if after is None:
                log.warning("Snapshot failed; keeping baseline")
                continue

            # Require complete matching data
            if any(symbol not in after for symbol in targets):

                log.warning("Incomplete snapshot; skipping comparison")
                continue

            results = calculate_results(before, after)

            log.info(
                "COINS ABOVE +%.5f%%: %s",
                MIN_OI_CHANGE,
                len(results)
            )

            for coin in results[:10]:

                log.info(
                    "%s | OI INCREASE: +%.6f%%",
                    coin["symbol"],
                    coin["oi_change_pct"]
                )

            if results:
                send_discord(results)

            before = after

        except Exception:

            log.exception("Scanner error")
            time.sleep(10)

# ==========================================
# 14. START RENDER SERVICE
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
