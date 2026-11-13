import os
import gc
import json
import time
import logging
import threading
import requests
import websocket  # Đảm bảo đã có websocket-client trong requirements.txt

from datetime import datetime, timezone
from flask import Flask, jsonify

# ==========================================
# 1. CẤU HÌNH CHÍNH
# ==========================================

# Dán trực tiếp link Discord Webhook của bạn vào đây:
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"

COIN_CONFIG_FILE = "coin.txt"   # Tệp chứa tên coin muốn theo dõi
DEFAULT_COIN = "BTCUSDT"        # Coin mặc định nếu chưa tạo tệp coin.txt

CHECK_INTERVAL = 10             # Lấy mẫu mỗi 10 giây
LOOKBACK_SECONDS = 60           # Chu kỳ chốt 1 phút (60 giây)
MAX_SAMPLES = (LOOKBACK_SECONDS // CHECK_INTERVAL) + 1  # 7 mẫu (0s -> 60s)
MIN_OI_CHANGE = 0.001           # Ngưỡng biến động ±0.001%

# Luồng WebSocket công khai của Bybit V5 (Hợp đồng tương lai USDT Perpetual)
BYBIT_WS_URL = "wss://://bybit.com"

# ==========================================
# 2. BIẾN TRẠNG THÁI TOÀN CỤC
# ==========================================

current_symbol = DEFAULT_COIN
latest_oi_data = None
ws_app = None
reset_flag = False

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
log = logging.getLogger("BYBIT_WS_OI")

app = Flask(__name__)

# ==========================================
# 3. HÀM ĐỌC TÊN COIN TỪ TỆP coin.txt
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
    except Exception as e:
        log.error("Lỗi đọc tệp %s: %s", COIN_CONFIG_FILE, e)
        return DEFAULT_COIN

# ==========================================
# 4. FLASK ROUTES (GIỮ SERVICE LUÔN SỐNG)
# ==========================================

@app.route("/")
def home():
    return jsonify({
        "status": "online",
        "exchange": "Bybit Futures (WebSocket)",
        "tracking_coin": current_symbol,
        "threshold_pct": MIN_OI_CHANGE
    })

@app.route("/health")
def health():
    return jsonify({"status": "healthy"})

# ==========================================
# 5. BYBIT WEBSOCKET WORKFLOW
# ==========================================

def on_open(ws):
    log.info("✅ Đã kết nối Bybit WebSocket! Đang đăng ký kênh tickers.%s ...", current_symbol)
    sub_msg = {
        "op": "subscribe",
        "args": [f"tickers.{current_symbol}"]
    }
    ws.send(json.dumps(sub_msg))

def on_message(ws, message):
    global latest_oi_data
    try:
        res = json.loads(message)
        
        # Bybit gửi dữ liệu ticker dạng snapshot hoặc delta trong trường "data"
        if res.get("topic") == f"tickers.{current_symbol}" and "data" in res:
            data = res["data"]
            # Chỉ cập nhật khi gói tin có chứa trường openInterest
            if "openInterest" in data:
                latest_oi_data = {
                    "symbol": current_symbol,
                    "oi": float(data["openInterest"]),
                    "timestamp": time.time()
                }
    except Exception as e:
        log.error("Lỗi giải mã dữ liệu Bybit: %s", e)

def on_error(ws, error):
    log.warning("Lỗi Bybit WebSocket: %s", error)

def on_close(ws, close_status_code, close_msg):
    log.warning("Mất kết nối Bybit WebSocket. Tự động kết nối lại sau 3s...")

def start_websocket():
    global ws_app
    while True:
        log.info("Đang kết nối tới %s cho đồng %s ...", BYBIT_WS_URL, current_symbol)
        ws_app = websocket.WebSocketApp(
            BYBIT_WS_URL,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        # Bybit yêu cầu gửi ping định kỳ để giữ kết nối sống
        ws_app.run_forever(ping_interval=20, ping_timeout=10)
        time.sleep(3)

# ==========================================
# 6. GỬI THÔNG BÁO DISCORD
# ==========================================

def send_discord(current, start_of_minute, change_pct):
    if not DISCORD_WEBHOOK_URL or "YOUR_WEBHOOK_ID" in DISCORD_WEBHOOK_URL:
        log.error("❌ Bạn chưa dán link Discord Webhook vào biến DISCORD_WEBHOOK_URL!")
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
                    {
                        "name": "Biến động (%)",
                        "value": f"`{change_pct:+.5f}%`",
                        "inline": True
                    },
                    {
                        "name": f"Chênh lệch ({base_asset})",
                        "value": f"`{diff_amount:+,.3f} {base_asset}`",
                        "inline": True
                    },
                    {
                        "name": f"OI Đầu Phút ({actual_seconds}s trước)",
                        "value": f"`{start_of_minute['oi']:,.3f} {base_asset}`",
                        "inline": False
                    },
                    {
                        "name": "OI Cuối Phút",
                        "value": f"`{current['oi']:,.3f} {base_asset}`",
                        "inline": False
                    }
                ],
                "footer": {
                    "text": f"Nguồn: Bybit V5 WebSocket ({current['symbol']}) | Chu kỳ 1 phút"
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        ]
    }

    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        res.raise_for_status()
        log.info("✅ Đã gửi thông báo Discord | %s | %+.5f%% (%+.3f %s)",
                 direction, change_pct, diff_amount, base_asset)
        return True
    except Exception as e:
        log.error("Lỗi gửi Discord: %s", e)
        return False

# ==========================================
# 7. VÒNG LẶP XỬ LÝ CHÍNH & TỰ ĐỘNG ĐỔI COIN
# ==========================================

def radar_loop():
    global current_symbol, latest_oi_data, reset_flag

    current_symbol = read_coin_from_file()
    log.info("Khởi chạy theo dõi Bybit OI cho %s | Ngưỡng: ±%s%%", current_symbol, MIN_OI_CHANGE)

    oi_history = []
    last_alert_state = None

    while True:
        loop_start = time.time()

        # Kiểm tra xem tệp coin.txt có bị thay đổi tên coin không
        new_symbol = read_coin_from_file()
        if new_symbol != current_symbol:
            log.info("🔄 Phát hiện đổi coin từ %s sang %s! Đang chuyển kênh & xóa bộ nhớ...",
                     current_symbol, new_symbol)
            current_symbol = new_symbol
            latest_oi_data = None
            oi_history.clear()
            last_alert_state = None
            gc.collect()
            if ws_app:
                ws_app.close()  # Ngắt kết nối cũ để WebSocket tự subscribe coin mới
            time.sleep(2)
            continue

        if latest_oi_data and latest_oi_data["symbol"] == current_symbol:
            current = dict(latest_oi_data)
            oi_history.append(current)
            base_asset = current_symbol.replace("USDT", "")

            if len(oi_history) >= MAX_SAMPLES:
                # LẤY MẪU ĐẦU PHÚT (INDEX 0) - ĐÃ FIX LỖI CHỈ MỤC
                start_of_minute = oi_history

                if start_of_minute["oi"] > 0:
                    change_pct = ((current["oi"] - start_of_minute["oi"]) / start_of_minute["oi"]) * 100

                    log.info(
                        "[Chốt 1 Phút - %s] Đầu: %.3f | Cuối: %.3f | Change: %+.5f%% | State: %s",
                        current_symbol,
                        start_of_minute["oi"],
                        current["oi"],
                        change_pct,
                        last_alert_state
                    )

                    # Báo 1 lần khi tăng vượt ngưỡng
                    if change_pct > MIN_OI_CHANGE and last_alert_state != "UP":
                        if send_discord(current, start_of_minute, change_pct):
                            last_alert_state = "UP"

                    # Báo 1 lần khi giảm vượt ngưỡng
                    elif change_pct < -MIN_OI_CHANGE and last_alert_state != "DOWN":
                        if send_discord(current, start_of_minute, change_pct):
                            last_alert_state = "DOWN"

                # Luôn xóa sạch bộ nhớ đệm cuối mỗi phút
                oi_history.clear()
                gc.collect()
                log.info("🧹 Đã xóa sạch bộ nhớ đệm cuối phút cho %s!", current_symbol)
            else:
                log.info("Đang lấy mẫu %s (%d/%d)... OI: %.3f %s",
                         current_symbol, len(oi_history), MAX_SAMPLES, current["oi"], base_asset)
        else:
            log.info("Đang đợi dữ liệu đầu tiên của %s từ Bybit WebSocket...", current_symbol)

        elapsed = time.time() - loop_start
        time.sleep(max(0, CHECK_INTERVAL - elapsed))

# ==========================================
# 8. KHỞI CHẠY HỆ THỐNG
# ==========================================

if __name__ == "__main__":
    current_symbol = read_coin_from_file()

ws_thread = threading.Thread(target=start_websocket, daemon=True)
ws_thread.start()
radar_thread = threading.Thread(target=radar_loop, daemon=True)
radar_thread.start()
port = int(os.environ.get("PORT", 10000))
app.run(host="0.0.0.0", port=port)
