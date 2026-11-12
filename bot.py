import requests
import time
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor

# Cấu hình Webhook từ dữ liệu của bạn
WEBHOOK_CONFIG = {
    "name": "ENGINE 3",
    "url": "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"
}

MIN_OI_CHANGE_PCT = 0.01

# Danh sách các cụm máy chủ API của Binance Futures
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

# Giả lập Web Server để Render Free Web Service không báo lỗi Deploy Failed
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ENGINE 3 Bot is running!")
    def log_message(self, format, *args):
        pass

def start_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    print(f"🌐 Web server đang lắng nghe tại port {port}")
    server.serve_forever()

def get_top_liquid_symbols(limit=40):
    global ACTIVE_BASE_URL
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
                print(f"✅ Kết nối thành công tới {base_url}")
                return [x['symbol'] for x in sorted_pairs[:limit]]
            else:
                print(f"⚠️ {base_url} trả về mã {res.status_code}: {res.text[:150]}")
        except Exception as e:
            print(f"⚠️ Lỗi kết nối {base_url}: {e}")
    return []

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

def send_discord_alert(top_3):
    message = f"**⚡ TOP COIN BIẾN ĐỘNG OI 1 PHÚT (>= {MIN_OI_CHANGE_PCT}%):**\n\n"
    for idx, item in enumerate(top_3, start=1):
        symbol = item['symbol']
        oi_change = item['oi_change_pct']
        oi_now = item['oi_now']
        icon = "🟢" if oi_change >= 0 else "🔴"
        
        message += f"**{idx}. {symbol}** {icon}\n"
        message += f"• Biến động OI (1m): `{oi_change:+.4f}%`\n"
        message += f"• Tổng OI hiện tại: `{oi_now:,.0f} {symbol.replace('USDT', '')}`\n\n"

    payload = {
        "username": WEBHOOK_CONFIG["name"],
        "content": message
    }
    res = requests.post(WEBHOOK_CONFIG["url"], json=payload)
    if res.status_code != 204:
        print(f"❌ Lỗi gửi Discord (Mã {res.status_code}): {res.text}")

def run_bot():
    print(f"🚀 Đang khởi động bot quét OI 1 phút (Ngưỡng >= {MIN_OI_CHANGE_PCT}%)...")
    while True:
        symbols = get_top_liquid_symbols(limit=40)
        if not symbols:
            print("⏳ Tất cả endpoint đều bị từ chối. Thử lại sau 30 giây...")
            time.sleep(30)
            continue

        previous_oi = get_all_oi(symbols)
        print(f"✅ Đã lấy mốc OI ban đầu của {len(previous_oi)}/{len(symbols)} coin. Chờ 60 giây...")

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
                send_discord_alert(top_3)
                print(f"📨 Đã gửi {len(top_3)} coin đạt ngưỡng lên Discord!")
            else:
                print(f"⏳ Không có coin nào đạt ngưỡng >= {MIN_OI_CHANGE_PCT}% trong phút qua.")
                
            previous_oi = current_oi

if __name__ == "__main__":
    # Mở port trước để Render nhận diện dịch vụ Live ngay lập tức
    threading.Thread(target=start_web_server, daemon=True).start()
    run_bot()
