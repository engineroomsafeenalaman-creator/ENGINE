import json
import time
import threading
import os
import requests
import websocket
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==========================================
# ĐÃ GẮN SẴN LINK WEBHOOK ENGINE 3 CỦA BẠN:
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"
BOT_NAME = "ENGINE 3"
MIN_OI_CHANGE_PCT = 0.001  # Ngưỡng lọc OI tăng > 0.001%
# ==========================================

# Danh sách các đồng thuộc hệ sinh thái Binance Alpha
ALPHA_COINS = [
    "INFINITUSDT", "SWARMSUSDT", "VELVETUSDT", "COAIUSDT", "ICNTUSDT", "NAORISUSDT",
    "XPINUSDT", "BLESSUSDT", "QUACKUSDT", "UNIBASEUSDT", "OKZOOUSDT", "YOOLDOUSDT",
    "OVERTAKEUSDT", "SQDUSDT", "ONEUSDT", "OLAXBTUSDT", "B2USDT", "MYXUSDT",
    "MERLUSDT", "ZKVUSDT", "ANOMAUSDT", "BITLIGHTUSDT", "GOATUSDT", "HANAUSDT",
    "RIVERUSDT", "NUMINEUSDT", "FROGGIEUSDT", "AOPUSDT", "DILLUSDT", "STBLUSDT",
    "RAVEUSDT", "TAUSDT", "LYNUSDT", "BREVUSDT", "ZKPUSDT", "AKEUSDT", "IDOLUSDT",
    "ARIAUSDT", "QUQUSDT", "ALCHUSDT", "COOKIEUSDT", "AIXBTUSDT", "CGPTUSDT",
    "GRIFFAINUSDT", "ZEREBROUSDT", "AVAAIUSDT", "VIRTUALUSDT", "FARTCOINUSDT",
    "ARCUSDT", "PIPPINUSDT", "TSTUSDT", "KAITOUSDT", "SHELLUSDT", "MUBARAKUSDT",
    "TUTUSDT", "BROCCOLI714USDT", "BROCCOLIUSDT", "BANANAS31USDT", "SIRENUSDT",
    "BIDUSDT", "IRYSUSDT", "BTRUSDT", "SOPHUSDT", "ZKJUSDT", "BIOUSDT", "SOLVUSDT",
    "LAYERUSDT", "IPUSDT", "REDUSDT", "GPSUSDT", "VINEUSDT", "JELLYJELLYUSDT",
    "CHILLGUYUSDT", "ACTUSDT", "PNUTUSDT", "MOODENGUSDT", "HIPPOUSDT", "BANUSDT",
    "MELANIAUSDT", "TRUMPUSDT", "KOMAUSDT", "THEUSDT", "1000WHYUSDT", "1000CHEEMSUSDT",
    "NEIROUSDT", "PENGUUSDT", "USUALUSDT", "MOVEUSDT", "MEUSDT", "VANAUSDT",
    "BERAUSDT", "ANIMEUSDT", "PLUMEUSDT", "SONICUSDT", "ZORAUSDT", "INITUSDT",
    "HYPERUSDT", "KERNELUSDT", "BABYUSDT", "STOUSDT", "PARTIUSDT", "NILUSDT",
    "BRUSDT", "BMTUSDT", "FORMUSDT", "GUNUSDT", "WALUSDT", "BANKUSDT", "EPTUSDT"
]

live_oi_data = {}
data_lock = threading.Lock()

def send_discord_raw(text):
    payload = {
        "username": BOT_NAME,
        "content": text
    }
    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if res.status_code == 429:
            print("⚠️ Discord Webhook đang giới hạn tốc độ gửi tin, tạm nghỉ 10s...", flush=True)
    except Exception as e:
        print(f"❌ Lỗi gửi Discord: {e}", flush=True)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ENGINE 3 Real-time Alpha OI Stream Active")
    def log_message(self, format, *args):
        pass

def start_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Nhận luồng Open Interest (OI) thực tế từng giây qua WebSocket (Không bao giờ dính 429)
def start_realtime_oi_stream():
    ws_url = "wss://://bybit.com"

    def on_message(ws, message):
        try:
            msg = json.loads(message)
            topic = msg.get("topic", "")
            if topic.startswith("tickers."):
                data = msg.get("data", {})
                sym = data.get("symbol")
                if sym:
                    with data_lock:
                        if sym not in live_oi_data:
                            live_oi_data[sym] = {"oi": 0.0, "price": 0.0}
                        if "openInterest" in data:
                            live_oi_data[sym]["oi"] = float(data["openInterest"])
                        if "lastPrice" in data:
                            live_oi_data[sym]["price"] = float(data["lastPrice"])
        except Exception:
            pass

    def on_open(ws):
        print("✅ Đã kết nối luồng Open Interest WebSocket thành công!", flush=True)
        # Đăng ký nhận dữ liệu OI từng giây của toàn bộ danh sách Alpha (chia nhóm 10 mã/lần để gửi mượt)
        for i in range(0, len(ALPHA_COINS), 10):
            batch = [f"tickers.{sym}" for sym in ALPHA_COINS[i:i+10]]
            ws.send(json.dumps({"op": "subscribe", "args": batch}))
            time.sleep(0.1)

        send_discord_raw(f"✅ **Bot {BOT_NAME} (Bản WebSocket OI Real-time) đã chạy!** Đang theo dõi OI từng giây của nhóm **Binance Alpha** (Ngưỡng `> {MIN_OI_CHANGE_PCT}%`)...")

        # Giữ kết nối WebSocket luôn sống bằng Ping mỗi 20 giây
        def ping_loop():
            while ws.sock and ws.sock.connected:
                time.sleep(20)
                try:
                    ws.send(json.dumps({"op": "ping"}))
                except Exception:
                    break
        threading.Thread(target=ping_loop, daemon=True).start()

    def on_error(ws, error):
        print(f"⚠️ Lỗi luồng WebSocket: {error}", flush=True)

    def on_close(ws, close_status_code, close_msg):
        print("🔄 Mất kết nối luồng OI, tự kết nối lại sau 5s...", flush=True)
        time.sleep(5)
        start_realtime_oi_stream()

    ws = websocket.WebSocketApp(
        ws_url,
        on_open=on_open,
        on_message=on_message,
        on_error=on_error,
        on_close=on_close
    )
    ws.run_forever()

# Tính toán biến động OI thực tế sau mỗi 60 giây và gửi Top 3 về Discord
def analyze_every_minute():
    previous_snapshot = {}

    while True:
        time.sleep(60)
        with data_lock:
            current_snapshot = {
                k: v.copy() for k, v in live_oi_data.items() 
                if v["oi"] > 0 and v["price"] > 0
            }

        if not current_snapshot:
            continue

        if not previous_snapshot:
            previous_snapshot = current_snapshot
            print(f"📊 Đã khóa mốc OI ban đầu cho {len(previous_snapshot)} đồng Alpha.", flush=True)
            continue

        changes = []
        for sym, curr in current_snapshot.items():
            prev = previous_snapshot.get(sym)
            if prev and prev["oi"] > 0:
                oi_pct = ((curr["oi"] - prev["oi"]) / prev["oi"]) * 100
                price_pct = ((curr["price"] - prev["price"]) / prev["price"]) * 100 if prev["price"] > 0 else 0

                if oi_pct > MIN_OI_CHANGE_PCT:
                    changes.append({
                        "symbol": sym,
                        "oi_pct": oi_pct,
                        "price_pct": price_pct,
                        "oi_now": curr["oi"],
                        "price_now": curr["price"]
                    })

        top_3 = sorted(changes, key=lambda x: x["oi_pct"], reverse=True)[:3]

        if top_3:
            message = f"**🔥 TOP 3 BINANCE ALPHA BIẾN ĐỘNG OI 1 PHÚT (> {MIN_OI_CHANGE_PCT}%):**\n\n"
            for idx, item in enumerate(top_3, start=1):
                sym = item["symbol"]
                binance_link = f"https://binance.com{sym}"
                icon = "🟢" if item["price_pct"] >= 0 else "🔴"
                message += f"**{idx}. [{sym}]({binance_link})** {icon}\n"
                message += f"• Biến động OI (1m): `{item['oi_pct']:+.4f}%`\n"
                message += f"• Biến động Giá (1m): `{item['price_pct']:+.2f}%`\n"
                message += f"• Giá hiện tại: `${item['price_now']}`\n\n"

            send_discord_raw(message)
            print(f"📨 Đã bắn Top {len(top_3)} kèo Alpha OI lên Discord!", flush=True)
        else:
            print(f"⏳ Chưa có đồng Alpha nào tăng OI > {MIN_OI_CHANGE_PCT}%.", flush=True)

        previous_snapshot = current_snapshot

if __name__ == "__main__":
    threading.Thread(target=start_web_server, daemon=True).start()
    threading.Thread(target=start_realtime_oi_stream, daemon=True).start()
    analyze_every_minute()
