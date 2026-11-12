import os
import time
import logging
import threading
import requests

from flask import Flask, jsonify
from concurrent.futures import ThreadPoolExecutor, as_completed


# =====================================================
# CONFIGURATION
# =====================================================

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

MAX_WORKERS = 10
MAX_RETRIES = 3

MIN_SUCCESS_RATIO = 0.80
REFRESH_TARGETS_SECONDS = 1800

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}


# =====================================================
# LOGGING
# =====================================================

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("ALPHA_RADAR")


# =====================================================
# HTTP SESSION
# =====================================================

http = requests.Session()
http.headers.update(HEADERS)


# =====================================================
# RENDER HEALTH CHECK
# =====================================================

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


def start_health_server():
    port = int(os.getenv("PORT", "10000"))

    app.run(
        host="0.0.0.0",
        port=port,
        threaded=True,
        use_reloader=False
    )


# =====================================================
# API REQUEST WITH RETRY
# =====================================================

def get_json(url, params=None, timeout=12):

    for attempt in range(MAX_RETRIES):

        try:
            response = requests.get(
                url,
                params=params,
                headers=HEADERS,
                timeout=timeout
            )

            if response.status_code in (418, 429):

                retry = response.headers.get(
                    "Retry-After", "5"
                )

                try:
                    delay = min(float(retry), 60)
                except ValueError:
                    delay = 5

                log.warning(
                    "Rate limit %s. Waiting %.1fs",
                    response.status_code,
                    delay
                )

                time.sleep(delay)
                continue

            response.raise_for_status()

            return response.json()

        except (requests.RequestException, ValueError) as e:

            log.warning(
                "API retry %s/%s: %s",
                attempt + 1,
                MAX_RETRIES,
                e
            )

            if attempt < MAX_RETRIES - 1:
                time.sleep(2 ** attempt)

    return None


# =====================================================
# GET BINANCE ALPHA TOKENS
# =====================================================

def get_binance_alpha_tokens():

    data = get_json(ALPHA_URL, timeout=20)

    if not isinstance(data, dict):
        log.error("Alpha API unavailable")
        return None

    if data.get("success") is False:
        log.error("Alpha API error: %s", data)
        return None

    token_data = data.get("data")

    if isinstance(token_data, dict):
        token_data = (
            token_data.get("tokens")
            or token_data.get("list")
            or token_data.get("data")
        )

    if not isinstance(token_data, list):
        log.error("Invalid Alpha token list structure")
        return None

    symbols = set()

    for token in token_data:

        if not isinstance(token, dict):
            continue

        symbol = token.get("symbol")

        if isinstance(symbol, str) and symbol.strip():
            symbols.add(symbol.strip().upper())

    if not symbols:
        log.error("No Alpha symbols found")
        return None

    log.info("Alpha tokens: %s", len(symbols))

    return symbols


# =====================================================
# GET ACTIVE FUTURES
# =====================================================

def get_active_futures_symbols():

    data = get_json(
        f"{FUTURES_URL}/fapi/v1/exchangeInfo"
    )

    if not isinstance(data, dict):
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

    log.info("Futures symbols: %s", len(futures_map))

    return futures_map


# =====================================================
# MATCH ALPHA + FUTURES
# =====================================================

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

    log.info("Tracking %s Alpha Futures", len(targets))

    log.info("TARGETS: %s", ", ".join(targets))

    return targets


# =====================================================
# GET SINGLE OPEN INTEREST
# =====================================================

def fetch_single_oi(symbol):

    data = get_json(
        f"{FUTURES_URL}/fapi/v1/openInterest",
        params={"symbol": symbol},
        timeout=10
    )

    if not isinstance(data, dict):
        return symbol, None

    try:
        return symbol, float(data["openInterest"])
    except (KeyError, TypeError, ValueError):
        return symbol, None


# =====================================================
# SNAPSHOT ALL OI
# =====================================================

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

            except Exception as e:
                log.warning("Snapshot error: %s", e)

    ratio = len(snapshot) / len(symbols) if symbols else 0

    log.info(
        "OI Snapshot: %s/%s (%.1f%%)",
        len(snapshot),
        len(symbols),
        ratio * 100
    )

    if ratio < MIN_SUCCESS_RATIO:
        log.warning("Incomplete snapshot - skipped")
        return None

    return snapshot


# =====================================================
# GET MARK PRICES
# =====================================================

def get_all_mark_prices():

    data = get_json(
        f"{FUTURES_URL}/fapi/v1/premiumIndex",
        timeout=15
    )

    if not isinstance(data, list):
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

    return prices


# =====================================================
# CALCULATE OI CHANGE
# =====================================================

def calculate_results(before, after, prices):

    results = []

    for symbol, previous in before.items():

        if symbol not in after or symbol not in prices:
            continue

        current = after[symbol]

        if previous <= 0:
            continue

        change = (
            (current - previous) / previous
        ) * 100

        # Strictly greater than 0.001%
        if abs(change) <= MIN_OI_CHANGE:
            continue

        results.append({
            "symbol": symbol,
            "oi_change_pct": change,
            "abs_change_pct": abs(change),
            "current_oi_usd": current * prices[symbol]
        })

    results.sort(
        key=lambda x: x["abs_change_pct"],
        reverse=True
    )

    return results


# =====================================================
# PER-COIN COOLDOWN
# =====================================================

coin_last_alert = {}
discord_lock = threading.Lock()


# =====================================================
# SEND DISCORD
# =====================================================

def send_discord_notification(coins):

    if not DISCORD_WEBHOOK_URL:
        log.error("Missing DISCORD_WEBHOOK_URL")
        return False

    if not coins:
        return False

    now = time.time()

    with discord_lock:

        eligible = []

        for coin in coins:

            symbol = coin["symbol"]

            last = coin_last_alert.get(symbol, 0)

            if now - last >= COIN_COOLDOWN:
                eligible.append(coin)

        eligible = eligible[:TOP_N]

        if not eligible:
            log.info("All matching coins are in cooldown")
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
            "allowed_mentions": {"parse": []},
            "embeds": [{
                "title": "⚡ BINANCE ALPHA - OI RADAR",
                "description": (
                    "TOP 3 Open Interest movements\n"
                    f"Threshold: `{MIN_OI_CHANGE}%`\n"
                    "Timeframe: `60 seconds`\n"
                    "Cooldown: `5 minutes per coin`"
                ),
                "color": 16766720,
                "fields": fields,
                "footer": {
                    "text": "Binance USD-M Futures | OI Scanner"
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
                    coin_last_alert[coin["symbol"]] = now

                log.info(
                    "DISCORD SENT: %s",
                    ", ".join(c["symbol"] for c in eligible)
                )

                return True

            log.error(
                "Discord HTTP %s: %s",
                response.status_code,
                response.text[:300]
            )

        except requests.RequestException as e:
            log.error("Discord error: %s", e)

        return False


# =====================================================
# MAIN BOT
# =====================================================

def main():

    log.info("====================================")
    log.info("BINANCE ALPHA OI RADAR STARTING")
    log.info("====================================")

    log.info("Threshold: %.5f%%", MIN_OI_CHANGE)
    log.info("Interval: %s seconds", WAIT_SECONDS)
    log.info("Coin cooldown: %s seconds", COIN_COOLDOWN)

    # Retry initialization instead of exiting
    targets = None

    while not targets:

        targets = get_target_symbols()

        if not targets:
            log.error("Initialization failed. Retry in 60s")
            time.sleep(60)

    before = None

    while before is None:

        before = snapshot_all_oi(targets)

        if before is None:
            log.warning("Initial snapshot failed. Retry in 30s")
            time.sleep(30)

    last_refresh = time.monotonic()

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

                    new_snapshot = snapshot_all_oi(new_targets)

                    if new_snapshot:

                        targets = new_targets
                        before = new_snapshot

                        log.info("Target list refreshed")

                last_refresh = cycle_start

            elapsed = time.monotonic() - cycle_start

            sleep_time = max(
                0,
                WAIT_SECONDS - elapsed
            )

            log.info("Waiting %.1f seconds", sleep_time)

            time.sleep(sleep_time)

            after = snapshot_all_oi(targets)

            if after is None:
                log.warning("Bad snapshot. Keeping previous data")
                continue

            prices = get_all_mark_prices()

            if not prices:
                log.warning("Mark price unavailable")
                before = after
                continue

            results = calculate_results(
                before,
                after,
                prices
            )

            log.info(
                "Coins above %.5f%%: %s",
                MIN_OI_CHANGE,
                len(results)
            )

            # Display TOP 10 in Render logs
            for idx, coin in enumerate(results[:10], 1):

                log.info(
                    "RANK %s | %s | OI: %+.5f%% | USD: $%s",
                    idx,
                    coin["symbol"],
                    coin["oi_change_pct"],
                    f"{coin['current_oi_usd']:,.2f}"
                )

            if results:
                send_discord_notification(results)
            else:
                log.info("No qualifying OI movements")

            before = after

            log.info("SCAN COMPLETED")

        except KeyboardInterrupt:
            log.info("Bot stopped")
            break

        except Exception:
            log.exception("Main loop error")
            time.sleep(10)


# =====================================================
# START APPLICATION
# =====================================================

if __name__ == "__main__":

    threading.Thread(
        target=start_health_server,
        daemon=True
    ).start()

    main()
