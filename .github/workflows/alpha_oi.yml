import os
import gc
import json
import time
import logging
import threading
import requests
import websocket  # Cài đặt: pip install websocket-client

from datetime import datetime, timezone
from flask import Flask, jsonify

# ==========================================
# CONFIG
# ==========================================

# DÁN TRỰC TIẾP LINK DISCORD WEBHOOK CỦA BẠN VÀO DƯỚI ĐÂY:
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"

TARGET_SYMBOL = "btcusdt"  # WebSocket yêu cầu chữ thường

# Các cụm máy chủ WebSocket dự phòng chuẩn của Binance Futures
WS_ENDPOINTS = [
    f"wss://://binance.com{TARGET_SYMBOL}@openInterest",
    f"wss://://binance.com{TARGET_SYMBOL}@openInterest",
    f"wss://://binance.com{TARGET_SYMBOL}@openInterest"
]

CHECK_INTERVAL = 10         # Lấy mẫu mỗi 10 giây
LOOKBACK_SECONDS = 60       # Chu kỳ 1 phút (60 giây)
MAX_SAMPLES = (LOOKBACK_SECONDS // CHECK_INTERVAL) + 1  # 7 mẫu (0s -> 60s)
MIN_OI_CHANGE = 0.001       # Ngưỡng biến động ±0.001%

latest_oi_data = None
ws_index = 0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("BINANCE_WS_OI")

app = Flask(__name__)

# ==========================================
# FLASK ROUTES
# ==========================================

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "mode": "WebSocket (Zero Rate Limit)",
        "symbol": TARGET_SYMBOL.upper()
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

# ==========================================
# WEBSOCKET LISTENER (NHẬN DỮ LIỆU REALTIME)
# ==========================================

def on_message(ws, message):
    global latest_oi_data
    try:
        data = json.loads(message)
        if "o" in data:
            latest_oi_data = {
                "symbol": data.get("s", TARGET_SYMBOL.upper()),
                "oi": float(data["o"]),
                "timestamp": time.time()
            }
    except Exception as e:
        log.error("Lỗi đọc dữ liệu WebSocket: %s", e)

def on_error(ws, error):
    log.warning("Lỗi WebSocket: %s", error)

def on_close(ws, close_status_code, close_msg):
    log.warning("Mất kết nối WebSocket. Đang tự động kết nối lại sau 3s...")

def on_open(ws):
    log.info("✅ Đã kết nối thành công tới Binance WebSocket!")

def start_websocket():
    global ws_index
    while True:
        url = WS_ENDPOINTS[ws_index % len(WS_ENDPOINTS)]
        ws_index += 1
        log.info("Đang kết nối tới %s ...", url)
        
        ws = websocket.WebSocketApp(
            url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        ws.run_forever(ping_interval=20, ping_timeout=10)
        time.sleep(3)

# ==========================================
# DISCORD NOTIFICATION
# ==========================================

def send_discord(current, start_of_minute, change_pct):
    if not DISCORD_WEBHOOK_URL or "YOUR_WEBHOOK_ID" in DISCORD_WEBHOOK_URL:
        log.error("Bạn chưa dán link Discord Webhook vào biến DISCORD_WEBHOOK_URL!")
        return False

    diff_btc = current["oi"] - start_of_minute["oi"]
    actual_seconds = round(current["timestamp"] - start_of_minute["timestamp"], 1)
    direction = "TĂNG VƯỢT NGƯỠNG 🟢" if change_pct > 0 else "GIẢM VƯỢT NGƯỠNG 🔴"
    color = 5763719 if change_pct > 0 else 15548997

    payload = {
        "embeds": [
            {
                "title": f"🚨 BINANCE OI {current['symbol']} ({direction})",
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
                    "text": "Nguồn: Binance WebSocket | Không giới hạn IP"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]
    }

    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        res.raise_for_status()
        log.info("Đã gửi thông báo Discord | %s | %+.5f%% (%+.3f BTC)", direction, change_pct, diff_btc)
        return True
    except Exception as e:
        log.error("Lỗi gửi Discord: %s", e)
        return False

# ==========================================
# MAIN RADAR LOOP (XỬ LÝ MỖI 10S & CHỐT 1 PHÚT)
# ==========================================

def radar_loop():
    log.info("Bắt đầu chu kỳ lấy mẫu mỗi %ss & chốt sổ mỗi 1 phút...", CHECK_INTERVAL)
    oi_history = []
    last_alert_state = None

    while True:
        loop_start = time.time()

        if latest_oi_data:
            current = dict(latest_oi_data)
            oi_history.append(current)

            if len(oi_history) >= MAX_SAMPLES:
                start_of_minute = oi_history[0]

                if start_of_minute["oi"] > 0:
                    change_pct = ((current["oi"] - start_of_minute["oi"]) / start_of_minute["oi"]) * 100

                    log.info(
                        "[Chốt 1 Phút] Đầu: %.3f BTC | Cuối: %.3f BTC | Change: %+.5f%% | State: %s",
                        start_of_minute["oi"],
                        current["oi"],
                        change_pct,
                        last_alert_state
                    )

                    if change_pct > MIN_OI_CHANGE and last_alert_state != "UP":
                        if send_discord(current, start_of_minute, change_pct):
                            last_alert_state = "UP"

                    elif change_pct < -MIN_OI_CHANGE and last_alert_state != "DOWN":
                        if send_discord(current, start_of_minute, change_pct):
                            last_alert_state = "DOWN"

                # Xóa sạch bộ nhớ đệm cuối mỗi phút
                oi_history.clear()
                gc.collect()
                log.info("🧹 Đã xóa sạch bộ nhớ đệm cuối phút!")
            else:
                log.info("Đang lấy mẫu (%d/%d)... OI: %.3f BTC", len(oi_history), MAX_SAMPLES, current["oi"])
        else:
            log.info("Đang đợi dữ liệu đầu tiên từ Binance WebSocket...")

        elapsed = time.time() - loop_start
        time.sleep(max(0, CHECK_INTERVAL - elapsed))

# ==========================================
# ENTRY POINT
# ==========================================

if __name__ == "__main__":
    ws_thread = threading.Thread(target=start_websocket, daemon=True)
    ws_thread.start()

    radar_thread = threading.Thread(target=radar_loop, daemon=True)
    radar_thread.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
