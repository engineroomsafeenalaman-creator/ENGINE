import os
import gc
import time
import random
import logging
import threading
import requests

from datetime import datetime, timezone
from flask import Flask, jsonify

# ==========================================
# CONFIG
# ==========================================

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

# Danh sách các cụm máy chủ dự phòng của Binance Futures
BINANCE_ENDPOINTS = [
    "https://binance.com",
    "https://binance.com",
    "https://binance.com",
    "https://binance.com",
    "https://binance.com"
]

# Proxy dự phòng (nếu có), phân cách bởi dấu phẩy
RAW_PROXIES = os.getenv("PROXY_LIST", "")
PROXY_POOL = [p.strip() for p in RAW_PROXIES.split(",") if p.strip()]

TARGET_SYMBOL = "BTCUSDT"
CHECK_INTERVAL = 10         # Lấy mẫu mỗi 10 giây
LOOKBACK_SECONDS = 60       # Chu kỳ 1 phút (60 giây)
MAX_SAMPLES = (LOOKBACK_SECONDS // CHECK_INTERVAL) + 1  # 7 mẫu (0s -> 60s)
MIN_OI_CHANGE = 0.001       # Ngưỡng biến động ±0.001%

HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json"
}

session = requests.Session()
endpoint_index = 0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

log = logging.getLogger("BINANCE_BTC_OI_BLOCK_1M")

app = Flask(__name__)

# ==========================================
# FLASK ROUTES
# ==========================================

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "symbol": TARGET_SYMBOL,
        "interval_seconds": CHECK_INTERVAL,
        "cycle_seconds": LOOKBACK_SECONDS
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

# ==========================================
# BINANCE API REQUEST (FAILOVER + ANTI-BAN)
# ==========================================

def get_binance_btc_oi():
    global endpoint_index

    for _ in range(len(BINANCE_ENDPOINTS)):
        base_url = BINANCE_ENDPOINTS[endpoint_index % len(BINANCE_ENDPOINTS)]
        endpoint_index += 1

        proxies = None
        if PROXY_POOL:
            chosen_proxy = random.choice(PROXY_POOL)
            proxies = {"http": chosen_proxy, "https": chosen_proxy}

        try:
            response = session.get(
                f"{base_url}/fapi/v1/openInterest",
                params={"symbol": TARGET_SYMBOL},
                headers=HEADERS,
                proxies=proxies,
                timeout=5
            )

            used_weight = int(response.headers.get("X-MBX-USED-WEIGHT-1M", 0))
            if used_weight > 2000:
                log.warning("Weight cao (%d/2400)! Tạm nghỉ 30s...", used_weight)
                time.sleep(30)

            if response.status_code in (403, 418, 429):
                retry_after = int(response.headers.get("Retry-After", 60))
                log.warning("Bị giới hạn tại %s (HTTP %d). Chờ %ds...", base_url, response.status_code, retry_after)
                if not PROXY_POOL:
                    time.sleep(retry_after)
                continue

            response.raise_for_status()
            data = response.json()

            return {
                "symbol": data["symbol"],
                "oi": float(data["openInterest"]),
                "timestamp": time.time(),
                "source": base_url
            }

        except Exception as e:
            log.warning("Lỗi kết nối %s: %s. Chuyển nguồn dự phòng...", base_url, e)
            continue

    log.error("Tất cả nguồn dự phòng Binance đều thất bại trong chu kỳ này.")
    return None

# ==========================================
# DISCORD NOTIFICATION
# ==========================================

def send_discord(current, start_of_minute, change_pct):
    if not DISCORD_WEBHOOK_URL:
        log.error("Thiếu biến môi trường DISCORD_WEBHOOK_URL!")
        return False

    diff_btc = current["oi"] - start_of_minute["oi"]
    actual_seconds = round(current["timestamp"] - start_of_minute["timestamp"], 1)
    direction = "TĂNG VƯỢT NGƯỠNG 🟢" if change_pct > 0 else "GIẢM VƯỢT NGƯỠNG 🔴"
    color = 5763719 if change_pct > 0 else 15548997

    payload = {
        "embeds": [
            {
                "title": f"🚨 BINANCE OI {TARGET_SYMBOL} ({direction})",
                "color": color,
                "fields": [
                    {
                        "name": "Biến động (%)",
                        "value": f"`{change_pct:+.5f}%`",
                        "inline": True
                    },
                    {
                        "name": "Chênh lệch (BTC)",
                        "value": f"`{diff_btc:+,.3f} BTC`",
                        "inline": True
                    },
                    {
                        "name": f"OI Đầu Phút ({actual_seconds}s trước)",
                        "value": f"`{start_of_minute['oi']:,.3f} BTC`",
                        "inline": False
                    },
                    {
                        "name": "OI Cuối Phút",
                        "value": f"`{current['oi']:,.3f} BTC`",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": f"Nguồn: {current['source']} | Chu kỳ 1 phút độc lập"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]
    }

    try:
        res = session.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        res.raise_for_status()
        log.info("Đã gửi thông báo Discord | %s | %+.5f%% (%+.3f BTC)", direction, change_pct, diff_btc)
        return True
    except Exception as e:
        log.error("Lỗi gửi Discord: %s", e)
        return False

# ==========================================
# MAIN RADAR LOOP
# ==========================================

def radar_loop():
    log.info(
        "Khởi chạy theo dõi OI %s mỗi %ss | Chốt & reset bộ nhớ mỗi 1 phút (Ngưỡng: ±%s%%)...",
        TARGET_SYMBOL, CHECK_INTERVAL, MIN_OI_CHANGE
    )

    oi_history = []
    last_alert_state = None  # Lưu trạng thái báo gần nhất: None, "UP", hoặc "DOWN"

    while True:
        loop_start = time.time()
        current = get_binance_btc_oi()

        if current:
            oi_history.append(current)

            # Khi đã thu thập đủ 7 mẫu (trọn vẹn 1 phút: 0s -> 60s)
            if len(oi_history) >= MAX_SAMPLES:
                start_of_minute = oi_history

                if start_of_minute["oi"] > 0:
                    change_pct = ((current["oi"] - start_of_minute["oi"]) / start_of_minute["oi"]) * 100

                    log.info(
                        "[Chốt 1 Phút] Đầu: %.3f BTC | Cuối: %.3f BTC | Change: %+.5f%% | State: %s",
                        start_of_minute["oi"],
                        current["oi"],
                        change_pct,
                        last_alert_state
                    )

                    # 1. Tăng vượt +0.001% (và chưa ở trạng thái báo tăng)
                    if change_pct > MIN_OI_CHANGE and last_alert_state != "UP":
                        if send_discord(current, start_of_minute, change_pct):
                            last_alert_state = "UP"

                    # 2. Giảm vượt -0.001% (và chưa ở trạng thái báo giảm)
                    elif change_pct < -MIN_OI_CHANGE and last_alert_state != "DOWN":
                        if send_discord(current, start_of_minute, change_pct):
                            last_alert_state = "DOWN"

                # Luôn xóa sạch bộ nhớ đệm và giải phóng RAM sau mỗi phút (dù có báo hay không)
                oi_history.clear()
                gc.collect()
                log.info("🧹 Đã xóa sạch bộ nhớ đệm cuối phút! Bắt đầu thu thập chu kỳ 1 phút mới...")

            else:
                log.info(
                    "Đang lấy mẫu trong phút (%d/%d)... OI: %.3f BTC",
                    len(oi_history),
                    MAX_SAMPLES,
                    current["oi"]
                )

        elapsed = time.time() - loop_start
        time.sleep(max(0, CHECK_INTERVAL - elapsed))

# ==========================================
# ENTRY POINT
# ==========================================

if __name__ == "__main__":
    worker = threading.Thread(target=radar_loop, daemon=True)
    worker.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
