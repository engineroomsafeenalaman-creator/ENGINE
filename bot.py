import requests
import time
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor

# ==========================================
# 👉 DÁN LINK WEBHOOK DISCORD CỦA BẠN VÀO ĐÂY:
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"
BOT_NAME = "ENGINE 3"
MIN_OI_CHANGE_PCT = 0.01
# ==========================================

BINANCE_ENDPOINTS = [
    "https://binance.com",
    "https://binance.com",
    "https://binance.com",
    "https://binance.com"
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
        self.wfile.write(b"Bot is running!")
    def log_message(self, format, *args):
        pass

def start_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"🌐 Web server đang mở tại port {port}", flush=True)
    server.serve_forever()

def get_top_liquid_symbols(limit=40):
    global ACTIVE_BASE_URL
    last_error = ""
    for base_url in BINANCE_ENDPOINTS:
        url = f"{base_url}/fapi/v1/ticker/24hr"
        try:
            res = requests.get(url, headers=HEADERS, timeout=10)
            if res.status_code == 200 and res.text.strip():
                ACTIVE_BASE_URL = base_url
                data = res.json()
                usdt_pairs = [
                    x for x in data 
                    if x['symbol'].endswith('USDT') and '_' not in x['symbol']
                ]
                sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x['quoteVolume']), reverse=True)
                return [x['symbol'] for x in sorted_pairs[:limit]], None
            else:
                last_error = f"Mã {res.status_code} từ {base_url}: {res.text[:100]}"
        except Exception as e:
            last_error = f"Lỗi mạng {base_url}: {str(e)}"
    return [], last_error

def fetch_oi(symbol):
    url = f"{ACTIVE_BASE_URL}/fapi/v1/openInterest?symbol={symbol}"
    try:
        res = requests.get(url, headers=HEADERS, timeout=5)
        if res.status_code == 200:
            return symbol, float(res.json()['openInterest'])
        return symbol, None
    except Exception:
        return symbol, None

def get_all_oi(symbols):
    oi_map = {}
    with ThreadPoolExecutor(max_workers=8) as executor:
        results = executor.map(fetch_oi, symbols)
        for symbol, oi in results:
            if oi is not None:
                oi_map[symbol] = oi
    return oi_map

def run_bot():
    print("🚀 Đang khởi động bot...", flush=True)
    send_discord_raw(f"✅ **Bot {BOT_NAME} đã khởi động!** Đang quét OI 1 phút trên Binance Futures (Ngưỡng lọc: `{MIN_OI_CHANGE_PCT}%`)...")

    while True:
        symbols, error_msg = get_top_liquid_symbols(limit=40)
        if not symbols:
            print(f"❌ Lỗi lấy dữ liệu Binance: {error_msg}", flush=True)
            send_discord_raw(f"⚠️ **Lỗi kết nối Binance:** `{error_msg}`\n*(Thử lại sau 60 giây)*")
            time.sleep(60)
            continue

        previous_oi = get_all_oi(symbols)
        print(f"✅ Đã lấy mốc OI ban đầu của {len(previous_oi)}/{len(symbols)} coin.", flush=True)

        while True:
            time.sleep(60)
            current_oi = get_all_oi(symbols)
            if not current_oi:
                break

            changes = []
            for sym, oi_now in current_oi.items():
                oi_prev = previous_oi.get(sym)
                if oi_prev and oi_prev > 0:
                    pct_change = ((oi_now - oi_prev) / oi_prev) * 100
                    if pct_change >= MIN_OI_CHANGE_PCT:
                        changes.append({
                            "symbol": sym,
                            "oi_change_pct": pct_change,
                            "oi_now": oi_now
                        })
            
            top_3 = sorted(changes, key=lambda x: x['oi_change_pct'], reverse=True)[:3]
            
            if top_3:
                message = f"**⚡ TOP COIN BIẾN ĐỘNG OI 1 PHÚT (>= {MIN_OI_CHANGE_PCT}%):**\n\n"
                for idx, item in enumerate(top_3, start=1):
                    symbol = item['symbol']
                    oi_change = item['oi_change_pct']
                    oi_now = item['oi_now']
                    message += f"**{idx}. {symbol}** 🟢\n• Biến động OI (1m): `{oi_change:+.4f}%`\n• Tổng OI: `{oi_now:,.0f} {symbol.replace('USDT', '')}`\n\n"
                send_discord_raw(message)
                print(f"📨 Đã gửi {len(top_3)} coin lên Discord!", flush=True)
            else:
                print(f"⏳ Không có coin nào đạt ngưỡng >= {MIN_OI_CHANGE_PCT}%.", flush=True)
                
            previous_oi = current_oi

if __name__ == "__main__":
    threading.Thread(target=start_web_server, daemon=True).start()
    run_bot()
