import os
import gc
import json
import time
import logging
import threading
import requests
import websocket

from datetime import datetime, timezone
from flask import Flask, jsonify

# ==========================================
# 1. CẤU HÌNH CHÍNH
# ==========================================

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"

COIN_CONFIG_FILE = "coin.txt"
DEFAULT_COIN = "BTCUSDT"

CHECK_INTERVAL = 10
LOOKBACK_SECONDS = 60
MAX_SAMPLES = (LOOKBACK_SECONDS // CHECK_INTERVAL) + 1
MIN_OI_CHANGE = 0.001

# Danh sách WebSocket dự phòng của Bybit (vượt chặn IP US trên Render)
BYBIT_WS_ENDPOINTS = [
    "wss://://bytick.com",
    "wss://://bybit.com"
]

# Danh sách REST API dự phòng của Bybit để lấy dữ liệu mồi ngay lập tức
BYBIT_REST_ENDPOINTS = [
    "https://bytick.com",
    "https://bybit.com"
]

# ==========================================
# 2. BIẾN TRẠNG THÁI
# ==========================================

current_symbol = DEFAULT_COIN
latest_oi_data = None
ws_app = None
ws_index = 0

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("BYBIT_OI_RADAR")

app = Flask(__name__)

# ==========================================
# 3. ĐỌC TÊN COIN TỪ TỆP coin.txt
# ==========================================

def read_coin_from_file():
    if not os.path.exists(COIN_CONFIG_FILE):
        try:
            with open(COIN_CONFIG_FILE, "w", encoding="utf-8") as f:
                f.write(DEFAULT_COIN)
        except Exception:
            pass
        return DEFAULT_COIN

    try:
        with open(COIN_CONFIG_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip().upper()
            return content if content else DEFAULT_COIN
    except Exception:
        return DEFAULT_COIN

# ==========================================
# 4. FLASK ROUTES
# ==========================================

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "exchange": "Bybit V5",
        "tracking_coin": current_symbol,
        "has_data": latest_oi_data is not None
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

# ==========================================
# 5. LẤY DỮ LIỆU MỒI QUA REST API (TRÁNH ĐỢI LÂU)
# ==========================================

def fetch_initial_oi(symbol):
    for base_url in BYBIT_REST_ENDPOINTS:
        try:
            res = requests.get(
                f"{base_url}/v5/market/tickers",
                params={"category": "linear", "symbol": symbol},
                timeout=5
            )
            data = res.json()
            if data.get("retCode") == 0:
                ticker_list = data.get("result", {}).get("list", [])
                if ticker_list and "openInterest" in ticker_list[0]:
                    return {
                        "symbol": symbol,
                        "oi": float(ticker_list[0]["openInterest"]),
                        "timestamp": time.time()
                    }
        except Exception as e:
            log.warning("Lỗi lấy REST API từ %s: %s", base_url, e)
    return None

# ==========================================
# 6. BYBIT WEBSOCKET WORKFLOW
# ==========================================

def on_open(ws):
    log.info("✅ Đã kết nối Bybit WebSocket! Đang đăng ký tickers.%s ...", current_symbol)
    ws.send(json.dumps({
        "op": "subscribe",
        "args": [f"tickers.{current_symbol}"]
    }))

def on_message(ws, message):
    global latest_oi_data
    try:
        res = json.loads(message)
        if res.get("topic") == f"tickers.{current_symbol}" and "data" in res:
            data = res["data"]
            if "openInterest" in data:
                latest_oi_data = {
                    "symbol": current_symbol,
                    "oi": float(data["openInterest"]),
                    "timestamp": time.time()
                }
    except Exception as e:
        log.error("Lỗi đọc gói tin Bybit: %s", e)

def on_error(ws, error):
    log.warning("Lỗi kết nối Bybit WebSocket: %s", error)

def on_close(ws, close_status_code, close_msg):
    log.warning("Đóng kết nối Bybit WebSocket. Thử lại sau 3s...")

def start_websocket():
    global ws_app, ws_index
    while True:
        url = BYBIT_WS_ENDPOINTS[ws_index % len(BYBIT_WS_ENDPOINTS)]
        ws_index += 1
        log.info("Đang kết nối tới %s ...", url)
        ws_app = websocket.WebSocketApp(
            url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        ws_app.run_forever(ping_interval=20, ping_timeout=10)
        time.sleep(3)

# ==========================================
# 7. GỬI THÔNG BÁO DISCORD
# ==========================================

def send_discord(current, start_of_minute, change_pct):
    if not DISCORD_WEBHOOK_URL or "YOUR_WEBHOOK_ID" in DISCORD_WEBHOOK_URL:
        log.error("❌ Chưa dán link Discord Webhook!")
        return False

    base_asset = current["symbol"].replace("USDT", "")
    diff_amount = current["oi"] - start_of_minute["oi"]
    actual_seconds = round(current["timestamp"] - start_of_minute["timestamp"], 1)
    direction = "TĂNG VƯỢT NGƯỠNG 🟢" if change_pct > 0 else "GIẢM VƯỢT NGƯỠNG 🔴"
    color = 5763719 if change_pct > 0 else 15548997

    payload = {
        "embeds": [
            {
                "title": f"🚨 BYBIT OI {current['symbol']} ({direction})",
                "color": color,
                "fields": [
                    {"name": "Biến động (%)", "value": f"`{change_pct:+.5f}%`", "inline": True},
                    {"name": f"Chênh lệch ({base_asset})", "value": f"`{diff_amount:+,.3f} {base_asset}`", "inline": True},
                    {"name": f"OI Đầu Phút ({actual_seconds}s trước)", "value": f"`{start_of_minute['oi']:,.3f} {base_asset}`", "inline": False},
                    {"name": "OI Cuối Phút", "value": f"`{current['oi']:,.3f} {base_asset}`", "inline": False}
                ],
                "footer": {"text": f"Nguồn: Bybit V5 ({current['symbol']}) | Chu kỳ 1 phút"},
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]
    }

    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        res.raise_for_status()
        log.info("✅ Đã gửi Discord | %s | %+.5f%%", direction, change_pct)
        return True
    except Exception as e:
        log.error("Lỗi gửi Discord: %s", e)
        return False

# ==========================================
# 8. VÒNG LẶP XỬ LÝ CHÍNH
# ==========================================

def radar_loop():
    global current_symbol, latest_oi_data

    current_symbol = read_coin_from_file()
    log.info("Khởi chạy theo dõi Bybit OI cho %s...", current_symbol)

    oi_history = []
    last_alert_state = None

    while True:
        loop_start = time.time()

        # Tự động nhận diện khi sửa tên coin trong coin.txt
        new_symbol = read_coin_from_file()
        if new_symbol != current_symbol:
            log.info("🔄 Đổi coin từ %s sang %s! Đang reset...", current_symbol, new_symbol)
            current_symbol = new_symbol
            latest_oi_data = None
            oi_history.clear()
            last_alert_state = None
            gc.collect()
            if ws_app:
                ws_app.close()
            time.sleep(2)
            continue

        # Nếu WebSocket chưa kịp đẩy gói đầu tiên, dùng REST API lấy dữ liệu mồi
        if not latest_oi_data or latest_oi_data["symbol"] != current_symbol:
            latest_oi_data = fetch_initial_oi(current_symbol)

        if latest_oi_data and latest_oi_data["symbol"] == current_symbol:
            current = dict(latest_oi_data)
            oi_history.append(current)
            base_asset = current_symbol.replace("USDT", "")

            if len(oi_history) >= MAX_SAMPLES:
                start_of_minute = oi_history[0]

                if start_of_minute["oi"] > 0:
                    change_pct = ((current["oi"] - start_of_minute["oi"]) / start_of_minute["oi"]) * 100

                    log.info(
                        "[Chốt 1 Phút - %s] Đầu: %.3f | Cuối: %.3f | Change: %+.5f%% | State: %s",
                        current_symbol, start_of_minute["oi"], current["oi"], change_pct, last_alert_state
                    )

                    if change_pct > MIN_OI_CHANGE and last_alert_state != "UP":
                        if send_discord(current, start_of_minute, change_pct):
                            last_alert_state = "UP"

                    elif change_pct < -MIN_OI_CHANGE and last_alert_state != "DOWN":
                        if send_discord(current, start_of_minute, change_pct):
                            last_alert_state = "DOWN"

                oi_history.clear()
                gc.collect()
                log.info("🧹 Đã xóa sạch bộ nhớ đệm cuối phút cho %s!", current_symbol)
            else:
                log.info("Đang lấy mẫu %s (%d/%d)... OI: %.3f %s",
                         current_symbol, len(oi_history), MAX_SAMPLES, current["oi"], base_asset)
        else:
            log.warning("⚠️ Không lấy được dữ liệu từ Bybit (IP Render vùng US có thể đang bị chặn).")

        elapsed = time.time() - loop_start
        time.sleep(max(0, CHECK_INTERVAL - elapsed))

# ==========================================
# 9. KHỞI CHẠY
# ==========================================

if __name__ == "__main__":
    current_symbol = read_coin_from_file()

    ws_thread = threading.Thread(target=start_websocket, daemon=True)
    ws_thread.start()

    radar_thread = threading.Thread(target=radar_loop, daemon=True)
    radar_thread.start()

    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
