
import os
import time
import logging
import requests
from concurrent.futures import ThreadPoolExecutor
from threading import Lock

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

# 0.1%: ngưỡng lọc biến động OI
# Có thể giảm xuống 0.001 nếu muốn nhạy hơn.
MIN_OI_CHANGE = 0.1

TOP_N = 3

# Không gửi thông báo quá thường xuyên
DISCORD_COOLDOWN = 300

MAX_WORKERS = 8
MAX_RETRIES = 3

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("AlphaRadar")

http = requests.Session()
http.headers.update(HEADERS)

# Trạng thái chống spam trong thời gian process chạy
last_discord_sent = 0
last_fingerprint = None
discord_lock = Lock()


# =====================================================
# HTTP REQUEST WITH RETRY
# =====================================================

def get_json(url, params=None, timeout=12):

    for attempt in range(MAX_RETRIES):

        try:
            response = http.get(
                url,
                params=params,
                timeout=timeout
            )

            if response.status_code in (418, 429):
                retry_after = response.headers.get(
                    "Retry-After", "5"
                )

                try:
                    delay = min(float(retry_after), 60)
                except ValueError:
                    delay = 5

                log.warning(
                    "Binance rate limit. Chờ %.1f giây",
                    delay
                )

                time.sleep(delay)
                continue

            response.raise_for_status()

            return response.json()

        except (requests.RequestException, ValueError) as e:

            log.warning(
                "API lỗi lần %s/%s: %s",
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

def extract_alpha_symbols(data):

    symbols = set()

    def scan(obj):

        if isinstance(obj, dict):

            for key, value in obj.items():

                if key.lower() in (
                    "symbol",
                    "tokensymbol",
                    "ticker"
                ):

                    if isinstance(value, str):
                        value = value.upper().strip()

                        if value:
                            symbols.add(value)

                if isinstance(value, (dict, list)):
                    scan(value)

        elif isinstance(obj, list):

            for item in obj:
                scan(item)

    scan(data)

    return symbols


def get_binance_alpha_tokens():

    data = get_json(ALPHA_URL)

    if not isinstance(data, dict):
        log.error("Không lấy được Binance Alpha Token List")
        return set()

    if data.get("success") is False:
        log.error("Binance Alpha API báo lỗi: %s", data)
        return set()

    tokens = extract_alpha_symbols(data.get("data", data))

    if not tokens:
        log.error(
            "Alpha Token List không có symbol hợp lệ. "
            "Kiểm tra cấu trúc JSON API."
        )
        return set()

    log.info("Đã lấy %s Alpha tokens", len(tokens))

    return tokens


# =====================================================
# GET FUTURES SYMBOLS
# =====================================================

def get_active_futures_symbols():

    data = get_json(
        f"{FUTURES_URL}/fapi/v1/exchangeInfo"
    )

    if not isinstance(data, dict):
        return {}

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

                # Hỗ trợ một số token dạng 1000XXX
                if base.startswith("1000"):
                    futures_map[base[4:]] = symbol

    log.info(
        "Đã tìm thấy %s cặp USDT-M Futures",
        len(futures_map)
    )

    return futures_map


# =====================================================
# MATCH ALPHA WITH FUTURES
# =====================================================

def get_target_symbols():

    alpha_tokens = get_binance_alpha_tokens()
    futures_map = get_active_futures_symbols()

    if not alpha_tokens or not futures_map:
        return []

    targets = sorted({
        futures_map[token]
        for token in alpha_tokens
        if token in futures_map
    })

    log.info(
        "Tìm thấy %s cặp Alpha có Futures",
        len(targets)
    )

    return targets


# =====================================================
# GET ALL MARK PRICES
# =====================================================

def get_all_mark_prices():

    data = get_json(
        f"{FUTURES_URL}/fapi/v1/premiumIndex"
    )

    if not isinstance(data, list):
        log.error("Không lấy được Mark Price")
        return {}

    prices = {}

    for item in data:

        try:
            prices[item["symbol"]] = float(
                item["markPrice"]
            )
        except (KeyError, TypeError, ValueError):
            continue

    return prices


# =====================================================
# GET OPEN INTEREST
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


def snapshot_all_oi(symbols):

    snapshot = {}

    with ThreadPoolExecutor(
        max_workers=MAX_WORKERS
    ) as executor:

        results = executor.map(
            fetch_single_oi,
            symbols
        )

        for symbol, oi in results:

            if oi is not None:
                snapshot[symbol] = oi

    log.info(
        "Đã lấy OI thành công %s/%s cặp",
        len(snapshot),
        len(symbols)
    )

    return snapshot


# =====================================================
# CALCULATE OI CHANGES
# =====================================================

def calculate_results(before, after, prices):

    results = []

    for symbol in before:

        if symbol not in after:
            continue

        if symbol not in prices:
            continue

        prev_qty = before[symbol]
        curr_qty = after[symbol]

        if prev_qty <= 0:
            continue

        change_pct = (
            (curr_qty - prev_qty) / prev_qty
        ) * 100

        if abs(change_pct) < MIN_OI_CHANGE:
            continue

        price = prices[symbol]

        results.append({
            "symbol": symbol,
            "oi_change_pct": change_pct,
            "abs_change_pct": abs(change_pct),
            "current_oi_usd": curr_qty * price
        })

    results.sort(
        key=lambda x: x["abs_change_pct"],
        reverse=True
    )

    return results[:TOP_N]


# =====================================================
# SEND DISCORD
# =====================================================

def send_discord_notification(coins):

    global last_discord_sent
    global last_fingerprint

    if not DISCORD_WEBHOOK_URL:
        log.error("Thiếu DISCORD_WEBHOOK_URL")
        return False

    if not coins:
        log.info("Không có biến động OI đạt ngưỡng")
        return False

    fingerprint = tuple(
        (
            coin["symbol"],
            round(coin["oi_change_pct"], 3)
        )
        for coin in coins
    )

    with discord_lock:

        now = time.time()

        if fingerprint == last_fingerprint:
            log.info("Bỏ qua thông báo trùng")
            return False

        if now - last_discord_sent < DISCORD_COOLDOWN:
            log.info("Đang trong thời gian cooldown Discord")
            return False

        fields = []

        for idx, coin in enumerate(coins, 1):

            change = coin["oi_change_pct"]

            icon = "🟢" if change > 0 else "🔴"
            sign = "+" if change > 0 else ""

            fields.append({
                "name": (
                    f"#{idx} {coin['symbol']} {icon}"
                ),
                "value": (
                    f"• **OI Change (60s):** "
                    f"`{sign}{change:.4f}%`\n"
                    f"• **Current OI:** "
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
                "title": "⚡ TOP 3 BINANCE ALPHA OI RADAR",
                "description": (
                    f"Open Interest changes over 60 seconds.\n"
                    f"Threshold: `{MIN_OI_CHANGE}%`"
                ),
                "color": 16766720,
                "fields": fields,
                "footer": {
                    "text": "Binance Futures | 60s OI Scanner"
                }
            }]
        }

        try:

            response = http.post(
                DISCORD_WEBHOOK_URL,
                json=payload,
                timeout=15
            )

            if response.status_code in (200, 204):

                last_discord_sent = now
                last_fingerprint = fingerprint

                log.info(
                    "Discord notification sent successfully"
                )

                return True

            if response.status_code == 429:
                log.warning(
                    "Discord rate limit: %s",
                    response.text[:300]
                )
                return False

            log.error(
                "Discord HTTP %s: %s",
                response.status_code,
                response.text[:300]
            )

        except requests.RequestException as e:

            log.error("Discord request error: %s", e)

        return False


# =====================================================
# MAIN CONTINUOUS LOOP
# =====================================================

def main():

    log.info("======================================")
    log.info("BINANCE ALPHA OI RADAR STARTED")
    log.info("======================================")

    targets = get_target_symbols()

    if not targets:
        log.error("Không tìm thấy Alpha Futures")
        return

    log.info("Đang theo dõi %s cặp coin", len(targets))

    before = snapshot_all_oi(targets)

    if not before:
        log.error("Không lấy được dữ liệu OI ban đầu")
        return

    while True:

        try:

            log.info(
                "Chờ %s giây để đo OI tiếp theo...",
                WAIT_SECONDS
            )

            time.sleep(WAIT_SECONDS)

            # Lấy snapshot tiếp theo
            after = snapshot_all_oi(targets)

            if not after:
                log.warning("Snapshot mới thất bại")
                continue

            # Lấy giá Mark Price
            prices = get_all_mark_prices()

            if not prices:
                log.warning("Không có Mark Price")
                before = after
                continue

            # Tính biến động
            top_coins = calculate_results(
                before,
                after,
                prices
            )

            if top_coins:

                for coin in top_coins:
                    log.info(
                        "%s | OI Change: %.4f%% | OI USD: $%.2f",
                        coin["symbol"],
                        coin["oi_change_pct"],
                        coin["current_oi_usd"]
                    )

                send_discord_notification(top_coins)

            else:
                log.info("Không có coin đạt ngưỡng")

            # Snapshot mới trở thành mốc so sánh tiếp theo
            before = after

        except KeyboardInterrupt:

            log.info("Bot stopped")
            break

        except Exception:

            log.exception("Lỗi vòng lặp chính")
            time.sleep(10)


if __name__ == "__main__":
    main()
