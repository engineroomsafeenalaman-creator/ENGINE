import requests
import time
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==========================================
# 👉 DÁN LINK WEBHOOK DISCORD CỦA BẠN VÀO ĐÂY:
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jNY"
BOT_NAME = "ENGINE 3"
MIN_OI_CHANGE_PCT = 0.01  # Ngưỡng lọc lớn hơn 0.01%
# ==========================================

# Danh sách các đồng thuộc hệ sinh thái Binance Alpha (có hợp đồng Futures)
ALPHA_COINS_RAW = [
    "ALCHUSDT", "SWARMSUSDT", "COOKIEUSDT", "AIXBTUSDT", "CGPTUSDT",
    "GRIFFAINUSDT", "ZEREBROUSDT", "AVAAIUSDT", "VIRTUALUSDT", "FARTCOINUSDT",
    "ARCUSDT", "PIPPINUSDT", "TSTUSDT", "KAITOUSDT", "SHELLUSDT",
    "MUBARAKUSDT", "TUTUSDT", "BROCCOLI714USDT", "BANANAS31USDT", "SIRENUSDT",
    "BIDUSDT", "AKEUSDT", "IDOLUSDT", "ARIAUSDT", "IRYSUSDT",
    "BTRUSDT", "SOPHUSDT", "MYXUSDT", "SQDUSDT", "MERLUSDT",
    "ICNTUSDT", "OLAXBTUSDT", "B2USDT", "ZKJUSDT", "HANAUSDT"
]

BINANCE_ENDPOINTS = [
    "https://fapi.binance.com",
    "https://fapi1.binance.com",
    "https://fapi2.binance.com",
    "https://fapi3.binance.com"
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

ACTIVE_BASE_URL = BINANCE_ENDPOINTS[0]

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

# Kiểm tra các đồng Alpha đang thực sự mở giao dịch trên Binance Futures
def get_valid_alpha_symbols():
    global ACTIVE_BASE_URL
    last_error = ""
    for base_url in BINANCE_ENDPOINTS:
        url = f"{base_url}/fapi/v1/exchangeInfo"
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code == 200 and res.text.strip():
                ACTIVE_BASE_URL = base_url
                data = res.json()
                trading_symbols = {
                    s['symbol'] for s in data.get('symbols', [])
                    if s.get('status') == 'TRADING'
                }
                # Chỉ giữ lại các mã Alpha có mặt trên Binance Futures
                valid_alphas = [sym for sym in ALPHA_COINS_RAW if sym in trading_symbols]
                return valid_alphas, None
            else:
                last_error = f"Mã {res.status_code} từ {base_url}"
        except Exception as e:
            last_error = f"Lỗi mạng {base_url}: {str(e)}"
    return [], last_error

# Lấy OI an toàn từng đồng (tránh lỗi 429)
def get_all_oi_safe(symbols):
    oi_map = {}
    for symbol in symbols:
        url = f"{ACTIVE_BASE_URL}/fapi/v1/openInterest?symbol={symbol}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=5)
            if res.status_code == 200:
                oi_map[symbol] = float(res.json()['openInterest'])
            elif res.status_code == 429:
                print("⚠️ Chạm ngưỡng 429 khi lấy OI, tạm dừng lượt quét này!", flush=True)
                return None
        except Exception:
            pass
        time.sleep(0.25) # Nghỉ 0.25s giữa mỗi đồng để giữ an toàn tuyệt đối cho IP
    return oi_map

def run_bot():
    print("🚀 Đang khởi động bot quét Binance Alpha OI...", flush=True)
    send_discord_raw(f"✅ **Bot {BOT_NAME} đã khởi động!** Đang lọc nhóm **Binance Alpha** trên Futures (Điều kiện: OI 1m `> {MIN_OI_CHANGE_PCT}%`)...")

    while True:
        symbols, error_msg = get_valid_alpha_symbols()
        if not symbols:
            print(f"❌ Lỗi lấy danh sách Alpha: {error_msg}. Đợi 2 phút...", flush=True)
            time.sleep(120)
            continue

        print(f"📋 Tìm thấy {len(symbols)} đồng Binance Alpha đang giao dịch trên Futures: {symbols}", flush=True)
        previous_oi = get_all_oi_safe(symbols)
        if not previous_oi:
            time.sleep(120)
            continue

        while True:
            time.sleep(60)
            current_oi = get_all_oi_safe(symbols)
            if current_oi is None:
                print("⏳ IP bị giới hạn 429, nghỉ 2 phút rồi tự chạy lại...", flush=True)
                time.sleep(120)
                break

            changes = []
            for sym, oi_now in current_oi.items():
                oi_prev = previous_oi.get(sym)
                if oi_prev and oi_prev > 0:
                    pct_change = ((oi_now - oi_prev) / oi_prev) * 100
                    # Lọc các coin có biến động OI 1 phút > 0.01%
                    if pct_change > MIN_OI_CHANGE_PCT:
                        changes.append({
                            "symbol": sym,
                            "oi_change_pct": pct_change,
                            "oi_now": oi_now
                        })
            
            # Chọn Top 3 đồng Alpha tăng OI cao nhất
            top_3 = sorted(changes, key=lambda x: x['oi_change_pct'], reverse=True)[:3]
            
            if top_3:
                message = f"**🔥 TOP 3 BINANCE ALPHA BIẾN ĐỘNG OI 1 PHÚT (> {MIN_OI_CHANGE_PCT}%):**\n\n"
                for idx, item in enumerate(top_3, start=1):
                    symbol = item['symbol']
                    oi_change = item['oi_change_pct']
                    oi_now = item['oi_now']
                    message += f"**{idx}. {symbol}** 🟢\n• Biến động OI (1m): `{oi_change:+.4f}%`\n• Tổng OI: `{oi_now:,.0f} {symbol.replace('USDT', '')}`\n\n"
                send_discord_raw(message)
                print(f"📨 Đã gửi Top {len(top_3)} Alpha OI lên Discord!", flush=True)
            else:
                print(f"⏳ Không có đồng Alpha nào có OI 1m > {MIN_OI_CHANGE_PCT}%.", flush=True)
                
            previous_oi = current_oi

if __name__ == "__main__":
    threading.Thread(target=start_web_server, daemon=True).start()
    run_bot()
