import os
import time
import logging
import threading
import requests

from flask import Flask, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed


# ==========================================
# 1. CONFIGURATION
# ==========================================

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

ALPHA_URL = (
    "https://www.binance.com/bapi/defi/v1/public/"
    "wallet-direct/buw/wallet/cex/alpha/all/token/list"
)

FUTURES_URL = "https://fapi.binance.com"

WAIT_SECONDS = 60
MIN_OI_CHANGE = 0.001
COIN_COOLDOWN = 300
TOP_N = 3

MAX_WORKERS = 2
REQUEST_INTERVAL = 0.5
MIN_SUCCESS_RATIO = 0.80
REFRESH_TARGETS_SECONDS = 1800

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Referer": "https://www.binance.com/"
}


# ==========================================
# 2. LOGGING
# ==========================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    force=True
)

log = logging.getLogger("ALPHA_RADAR")


# ==========================================
# 3. GLOBAL STATE
# ==========================================

api_lock = threading.Lock()
api_block_until = 0.0
next_request_time = 0.0

discord_lock = threading.Lock()
coin_last_alert = {}


# ==========================================
# 4. FLASK HEALTH CHECK
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

def get_json(url, params=None, timeout=15):

    global api_block_until
    global next_request_time

    for attempt in range(2):

        with api_lock:

            now = time.monotonic()

            if now < api_block_until:
                log.warning("Binance API is in cooldown")
                return None

            wait = next_request_time - now

            if wait > 0:
                time.sleep(wait)

            if time.monotonic() < api_block_until:
                return None

            next_request_time = (
                time.monotonic() + REQUEST_INTERVAL
            )

        try:

            response = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=timeout
            )

         if response.status_code in (418, 429):

                retry_after = response.headers.get(
                    "Retry-After"
                )

                log.error(
                    "Binance HTTP %s | Retry-After: %s",
                    response.status_code,
                    retry_after or "Not provided"
                )

                try:
                    delay = float(retry_after)
                except (TypeError, ValueError):
                    delay = (
                        900 if response.status_code == 418
                        else 60
                    )

                delay = max(delay, 60)

                with api_lock:
                    api_block_until = max(
                        api_block_until,
                        time.monotonic() + delay
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

            log.warning(
                "Request attempt %s failed: %s",
                attempt + 1,
                e
            )

        except ValueError as e:

            log.error("Invalid JSON response: %s", e)
            return None

        if attempt == 0:
            time.sleep(3)

    return None

                retry_after = response.headers.get(
                    "Retry-After"
                )

                try:
                    delay = float(retry_after)
                except (TypeError, ValueError):
                    delay = (
                        300 if response.status_code == 418
                        else 60
                    )

                delay = min(max(delay, 60), 900)

                with api_lock:
                    api_block_until = max(
                        api_block_until,
                        time.monotonic() + delay
                    )

                log.error(
                    "Binance HTTP %s. Pausing API %.0f seconds",
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

            log.warning(
                "Request attempt %s failed: %s",
                attempt + 1,
                e
            )

        except ValueError as e:

            log.error("Invalid JSON response: %s", e)
            return None

        if attempt == 0:
            time.sleep(3)

    return None


# ==========================================
# 6. BINANCE ALPHA TOKEN LIST
# ==========================================

def get_binance_alpha_tokens():

    log.info("Loading Binance Alpha tokens...")

    try:

        response = requests.get(
            ALPHA_URL,
            headers=HEADERS,
            timeout=20
        )

        log.info(
            "ALPHA HTTP STATUS: %s",
            response.status_code
        )

        if response.status_code in (418, 429):

            log.error(
                "Alpha API rate limited: HTTP %s",
                response.status_code
            )

            return None

        if response.status_code in (403, 451):

            log.error(
                "Alpha API access restricted: HTTP %s",
                response.status_code
            )

            return None

        response.raise_for_status()

        data = response.json()

        if not isinstance(data, dict):
            log.error("Alpha response is not a JSON object")
            return None

        if data.get("success") is False:

            log.error(
                "Alpha API error: %s",
                str(data)[:500]
            )

            return None

        if data.get("code") not in (None, "000000"):

            log.error(
                "Alpha API code: %s",
                data.get("code")
            )

            return None

        token_data = data.get("data")

        if isinstance(token_data, dict):

            token_data = (
                token_data.get("tokens")
                or token_data.get("list")
                or token_data.get("data")
            )

        if not isinstance(token_data, list):

            log.error(
                "Unexpected Alpha response structure: %s",
                str(data)[:800]
            )

            return None

        symbols = set()

        for item in token_data:

            if not isinstance(item, dict):
                continue

            symbol = item.get("symbol")

            if isinstance(symbol, str) and symbol.strip():
                symbols.add(symbol.strip().upper())

        if not symbols:
            log.error("Alpha token list is empty")
            return None

        log.info(
            "ALPHA TOKENS LOADED: %s",
            len(symbols)
        )

        return symbols

    except Exception:

        log.exception("ALPHA TOKEN REQUEST FAILED")
        return None
        # ==========================================
# 7. LOAD BINANCE FUTURES SYMBOLS
# ==========================================

def get_active_futures_symbols():

    log.info("Loading Binance Futures symbols...")

    data = get_json(
        f"{FUTURES_URL}/fapi/v1/exchangeInfo",
        timeout=20
    )

    if not isinstance(data, dict):

        log.error("Futures ExchangeInfo unavailable")
        return None

    futures_map = {}

    for item in data.get("symbols", []):

        if (
            item.get("status") == "TRADING"
            and item.get("quoteAsset") == "USDT"
            and item.get("contractType") == "PERPETUAL"
        ):

            base = item.get("baseAsset", "").upper()
            symbol = item.get("symbol")

            if base and symbol:

                futures_map[base] = symbol

                if base.startswith("1000") and len(base) > 4:
                    futures_map[base[4:]] = symbol

    log.info(
        "ACTIVE FUTURES: %s",
        len(futures_map)
    )

    return futures_map


# ==========================================
# 8. MATCH ALPHA WITH FUTURES
# ==========================================

def get_target_symbols():

    alpha = get_binance_alpha_tokens()

    if alpha is None:
        return None

    futures = get_active_futures_symbols()

    if futures is None:
        return None

    targets = sorted({
        futures[token]
        for token in alpha
        if token in futures
    })

    if not targets:

        log.error("No matching Alpha Futures")
        return None

    log.info(
        "TRACKING ALPHA FUTURES: %s",
        len(targets)
    )

    log.info(
        "TARGETS: %s",
        ", ".join(targets)
    )

    return targets


# ==========================================
# 9. FETCH OPEN INTEREST
# ==========================================

def fetch_single_oi(symbol):

    data = get_json(
        f"{FUTURES_URL}/fapi/v1/openInterest",
        params={"symbol": symbol},
        timeout=12
    )

    if not isinstance(data, dict):
        return symbol, None

    try:
        return symbol, float(data["openInterest"])

    except (KeyError, TypeError, ValueError):
        return symbol, None


# ==========================================
# 10. SNAPSHOT ALL OPEN INTEREST
# ==========================================

def snapshot_all_oi(symbols):

    snapshot = {}

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        futures = {
            executor.submit(fetch_single_oi, symbol): symbol
            for symbol in symbols
        }

        for future in as_completed(futures):

            try:

                symbol, oi = future.result()

                if oi is not None and oi >= 0:
                    snapshot[symbol] = oi

            except Exception:

                log.exception("OI snapshot error")

    ratio = (
        len(snapshot) / len(symbols)
        if symbols else 0
    )

    log.info(
        "OI SNAPSHOT: %s/%s (%.1f%%)",
        len(snapshot),
        len(symbols),
        ratio * 100
    )

    if ratio < MIN_SUCCESS_RATIO:

        log.warning(
            "Incomplete snapshot. Skipping calculation."
        )

        return None

    return snapshot


# ==========================================
# 11. GET MARK PRICES
# ==========================================

def get_all_mark_prices():

    data = get_json(
        f"{FUTURES_URL}/fapi/v1/premiumIndex",
        timeout=20
    )

    if not isinstance(data, list):

        log.error("Mark Price unavailable")
        return None

    prices = {}

    for item in data:

        try:

            symbol = item["symbol"]
            price = float(item["markPrice"])

            if price > 0:
                prices[symbol] = price

        except (KeyError, TypeError, ValueError):
            continue

    log.info(
        "MARK PRICES LOADED: %s",
        len(prices)
    )

    return prices


# ==========================================
# 12. CALCULATE OI CHANGE
# ==========================================

def calculate_results(before, after, prices):

    results = []

    for symbol, previous in before.items():

        if symbol not in after:
            continue

        if symbol not in prices:
            continue

        current = after[symbol]

        if previous <= 0:
            continue

        change = (
            (current - previous) / previous
        ) * 100

        if abs(change) <= MIN_OI_CHANGE:
            continue

        results.append({

            "symbol": symbol,

            "oi_change_pct": change,

            "abs_change_pct": abs(change),

            "current_oi_usd": (
                current * prices[symbol]
            )

        })

    results.sort(
        key=lambda x: x["abs_change_pct"],
        reverse=True
    )

    return results
    # ==========================================
# 13. SEND DISCORD NOTIFICATION
# ==========================================

def send_discord_notification(coins):

    if not DISCORD_WEBHOOK_URL:

        log.error("DISCORD_WEBHOOK_URL is missing")
        return False

    now = time.time()

    with discord_lock:

        eligible = []

        for coin in coins:

            symbol = coin["symbol"]

            last = coin_last_alert.get(
                symbol,
                0
            )

            if now - last >= COIN_COOLDOWN:
                eligible.append(coin)

        eligible = eligible[:TOP_N]

        if not eligible:

            log.info("No coins eligible for Discord alert")
            return False

        fields = []

        for idx, coin in enumerate(eligible, 1):

            change = coin["oi_change_pct"]

            if change > 0:

                icon = "🟢"
                direction = "OI INCREASE"
                sign = "+"

            else:

                icon = "🔴"
                direction = "OI DECREASE"
                sign = ""

            fields.append({

                "name": f"#{idx} {coin['symbol']} {icon}",

                "value": (

                    f"**Direction:** {direction}\n"

                    f"**OI Change (60s):** "
                    f"`{sign}{change:.5f}%`\n"

                    f"**Current OI:** "
                    f"`${coin['current_oi_usd']:,.2f}`"

                ),

                "inline": False

            })

        payload = {

            "username": "Binance Alpha OI Radar",

            "allowed_mentions": {
                "parse": []
            },

            "embeds": [{

                "title": "⚡ BINANCE ALPHA - OI RADAR",

                "description": (

                    "TOP 3 Open Interest movements\n"

                    f"Threshold: `{MIN_OI_CHANGE}%`\n"

                    "Timeframe: approximately `60 seconds`\n"

                    "Cooldown: `5 minutes per coin`"

                ),

                "color": 16766720,

                "fields": fields,

                "footer": {

                    "text": (
                        "Binance USD-M Futures | OI Scanner"
                    )

                }

            }]

        }

        try:

            response = requests.post(
                DISCORD_WEBHOOK_URL,
                json=payload,
                headers=HEADERS,
                timeout=15
            )

            if response.status_code in (200, 204):

                for coin in eligible:

                    coin_last_alert[
                        coin["symbol"]
                    ] = now

                log.info(
                    "DISCORD SENT: %s",
                    ", ".join(
                        coin["symbol"]
                        for coin in eligible
                    )
                )

                return True

            log.error(
                "Discord HTTP %s: %s",
                response.status_code,
                response.text[:300]
            )

        except requests.RequestException:

            log.exception("Discord request failed")

        return False


# ==========================================
# 14. MAIN SCANNER
# ==========================================

def main():

    log.info("====================================")
    log.info("BINANCE ALPHA OI RADAR STARTING")
    log.info("====================================")

    log.info(
        "Threshold: %.5f%%",
        MIN_OI_CHANGE
    )

    log.info(
        "Interval: %s seconds",
        WAIT_SECONDS
    )

    log.info(
        "Coin cooldown: %s seconds",
        COIN_COOLDOWN
    )

    if not DISCORD_WEBHOOK_URL:
        log.error("DISCORD_WEBHOOK_URL is missing")

    # Load initial Alpha Futures list

    targets = None

    while not targets:

        targets = get_target_symbols()

        if not targets:

            log.error(
                "Initialization failed. Retry in 60 seconds"
            )

            time.sleep(60)

    # Initial OI snapshot

    before = None

    while before is None:

        before = snapshot_all_oi(targets)

        if before is None:

            log.warning(
                "Initial snapshot failed. Retry in 60 seconds"
            )

            time.sleep(60)

    last_refresh = time.monotonic()

    # Continuous scanning

    while True:

        try:

            cycle_start = time.monotonic()

            log.info("------------------------------------")
            log.info("START NEW OI SCAN")

            # Refresh Alpha list every 30 minutes

            if (
                cycle_start - last_refresh
                >= REFRESH_TARGETS_SECONDS
            ):

                new_targets = get_target_symbols()

                if new_targets:

                    new_snapshot = snapshot_all_oi(
                        new_targets
                    )

                    if new_snapshot:

                        targets = new_targets
                        before = new_snapshot

                        log.info("Targets refreshed")

                last_refresh = cycle_start

            # Wait until approximately 60 seconds
            # after the previous cycle started

            elapsed = (
                time.monotonic() - cycle_start
            )

            sleep_time = max(
                0,
                WAIT_SECONDS - elapsed
            )

            log.info(
                "Waiting %.1f seconds",
                sleep_time
            )

            time.sleep(sleep_time)

            # Second OI snapshot

            after = snapshot_all_oi(targets)

            if after is None:

                log.warning(
                    "Snapshot failed. Keeping previous data"
                )

                continue

            # Get mark prices

            prices = get_all_mark_prices()

            if not prices:

                log.warning(
                    "Mark Price unavailable"
                )

                before = after
                continue

            # Calculate changes

            results = calculate_results(
                before,
                after,
                prices
            )

            log.info(
                "COINS ABOVE %.5f%%: %s",
                MIN_OI_CHANGE,
                len(results)
            )

            # Print TOP 10 to logs

            for idx, coin in enumerate(results[:10], 1):

                log.info(

                    "RANK %s | %s | OI: %+.5f%% | USD: $%s",

                    idx,

                    coin["symbol"],

                    coin["oi_change_pct"],

                    f"{coin['current_oi_usd']:,.2f}"

                )

            # Send TOP 3 to Discord

            if results:

                send_discord_notification(results)

            else:

                log.info(
                    "No qualifying OI movements"
                )

            # Update baseline

            before = after

            log.info("SCAN COMPLETED")

        except Exception:

            log.exception(
                "Main scanner error"
            )

            time.sleep(10)


# ==========================================
# 15. START RENDER WEB SERVICE
# ==========================================

if __name__ == "__main__":

    port = int(
        os.getenv("PORT", "10000")
    )

    log.info(
        "Starting HTTP server on port %s",
        port
    )

    bot_thread = threading.Thread(
        target=main,
        daemon=True
    )

    bot_thread.start()

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,
        use_reloader=False
    )
