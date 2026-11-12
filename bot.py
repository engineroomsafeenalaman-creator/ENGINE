import requests
import time
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==========================================
# 👉 DÁN LINK WEBHOOK DISCORD CỦA BẠN VÀO ĐÂY:
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"
BOT_NAME = "ENGINE 3"
MIN_OI_CHANGE_PCT = 0.01  # Ngưỡng lọc > 0.01%
# ==========================================

# Danh sách các đồng thuộc hệ sinh thái Binance Alpha
ALPHA_COINS_SET = {
    "ALCHUSDT", "SWARMSUSDT", "COOKIEUSDT", "AIXBTUSDT", "CGPTUSDT",
    "GRIFFAINUSDT", "ZEREBROUSDT", "AVAAIUSDT", "VIRTUALUSDT", "FARTCOINUSDT",
    "ARCUSDT", "PIPPINUSDT", "TSTUSDT", "KAITOUSDT", "SHELLUSDT",
    "MUBARAKUSDT", "TUTUSDT", "BROCCOLI714USDT", "BANANAS31USDT", "SIRENUSDT",
    "BIDUSDT", "AKEUSDT", "IDOLUSDT", "ARIAUSDT", "IRYSUSDT",
    "BTRUSDT", "SOPHUSDT", "MYXUSDT", "SQDUSDT", "MERLUSDT",
    "ICNTUSDT", "OLAXBTUSDT", "B2USDT", "ZKJUSDT", "HANAUSDT"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

def send_discord_raw(text):
    payload = {
        "username": BOT_NAME,
        "content": text
    }
    try:
        res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if res.status_code != 204:
            print(f"❌ Lỗi gửi Discord ({res.status_code}): {res.text}", flush=True)
    except Exception as e:
        print(f"❌ Lỗi kết nối Discord: {e}", flush=True)

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot Alpha OI is running!")
    def log_message(self, format, *args):
        pass

def start_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Lấy toàn bộ OI của nhóm Alpha chỉ bằng ĐÚNG 1 REQUEST DUY NHẤT (Không bao giờ dính 429)
def fetch_alpha_oi_single_call():
    url = "https://bybit.com"
    try:
        res = requests.get(url, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            tickers = data.get("result", {}).get("list", [])
            oi_map = {}
            for item in tickers:
                sym = item.get("symbol")
                if sym in ALPHA_COINS_SET:
                    oi_val = float(item.get("openInterest", 0))
                    price_val = float(item.get("lastPrice", 0))
                    if oi_val > 0:
                        oi_map[sym] = {
                            "oi": oi_val,
                            "price": price_val
                        }
            return oi_map, None
        else:
            return None, f"Mã lỗi {res.status_code}: {res.text[:100]}"
    except Exception as e:
        return None, str(e)

def run_bot():
    print("🚀 Đang khởi động bot quét Alpha OI (1-Request Mode)...", flush=True)
    send_discord_raw(f"✅ **Bot {BOT_NAME} đã khởi động!** Đang quét nhóm **Alpha** mỗi 1 phút (Điều kiện: OI 1m `> {MIN_OI_CHANGE_PCT}%`)...")

    previous_data = None

    while True:
        current_data, err = fetch_alpha_oi_single_call()
        if not current_data:
            print(f"⚠️ Lỗi lấy dữ liệu: {err}. Thử lại sau 30 giây...", flush=True)
            time.sleep(30)
            continue

        if previous_data is None:
            previous_data = current_data
            print(f"✅ Đã ghi nhận mốc OI ban đầu cho {len(previous_data)} đồng Alpha. Chờ 60 giây...", flush=True)
            time.sleep(60)
            continue

        changes = []
        for sym, curr in current_data.items():
            prev = previous_data.get(sym)
            if prev and prev["oi"] > 0:
                oi_pct = ((curr["oi"] - prev["oi"]) / prev["oi"]) * 100
                price_pct = ((curr["price"] - prev["price"]) / prev["price"]) * 100 if prev["price"] > 0 else 0
                
                # Lọc các đồng Alpha có mức tăng OI trong 1 phút > 0.01%
                if oi_pct > MIN_OI_CHANGE_PCT:
                    changes.append({
                        "symbol": sym,
                        "oi_pct": oi_pct,
                        "price_pct": price_pct,
                        "oi_now": curr["oi"],
                        "price_now": curr["price"]
                    })

        # Chọn Top 3 đồng Alpha có biến động tăng OI cao nhất
        top_3 = sorted(changes, key=lambda x: x["oi_pct"], reverse=True)[:3]

        if top_3:
            message = f"**🔥 TOP 3 ALPHA BIẾN ĐỘNG OI 1 PHÚT (> {MIN_OI_CHANGE_PCT}%):**\n\n"
            for idx, item in enumerate(top_3, start=1):
                sym = item["symbol"]
                binance_link = f"https://binance.com{sym}"
                message += f"**{idx}. [{sym}]({binance_link})** 🟢\n"
                message += f"• Biến động OI (1m): `{item['oi_pct']:+.4f}%`\n"
                message += f"• Biến động Giá (1m): `{item['price_pct']:+.2f}%`\n"
                message += f"• Giá hiện tại: `${item['price_now']}`\n\n"
            
            send_discord_raw(message)
            print(f"📨 Đã gửi Top {len(top_3)} Alpha OI lên Discord!", flush=True)
        else:
            print(f"⏳ Không có đồng Alpha nào có OI 1m > {MIN_OI_CHANGE_PCT}%.", flush=True)

        previous_data = current_data
        time.sleep(60)

if __name__ == "__main__":
    threading.Thread(target=start_web_server, daemon=True).start()
    run_bot()
