import requests
import time
import threading
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# ==========================================
# 👉 DÁN LINK WEBHOOK DISCORD CỦA BẠN VÀO ĐÂY:
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"
BOT_NAME = "ENGINE 3"
MIN_OI_CHANGE_PCT = 0.001  # Ngưỡng siêu nhạy > 0.001%
# ==========================================

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
}

# Danh sách dự phòng 100+ dự án Binance Alpha phổ biến (kèm cả biến thể 1000)
RAW_ALPHA_NAMES = [
    "INFINIT", "SWARMS", "VELVET", "COAI", "ICNT", "NAORIS", "XPIN", "BLESS",
    "QUACK", "UNIBASE", "OKZOO", "YOOLDO", "OVERTAKE", "SQD", "ONE", "OLAXBT",
    "B2", "MYX", "MERL", "ZKV", "ANOMA", "BITLIGHT", "GOAT", "HANA", "RIVER",
    "NUMINE", "FROGGIE", "AOP", "DILL", "STBL", "RAVE", "TA", "LYN", "BREV",
    "ZKP", "AKE", "IDOL", "ARIA", "QUQ", "ALCH", "COOKIE", "AIXBT", "CGPT",
    "GRIFFAIN", "ZEREBRO", "AVAAI", "VIRTUAL", "FARTCOIN", "ARC", "PIPPIN",
    "TST", "KAITO", "SHELL", "MUBARAK", "TUT", "BROCCOLI714", "BROCCOLI",
    "BANANAS31", "SIREN", "BID", "IRYS", "BTR", "SOPH", "ZKJ", "BIO", "SOLV",
    "LAYER", "IP", "RED", "GPS", "VINE", "JELLYJELLY", "CHILLGUY", "ACT",
    "PNUT", "MOODENG", "HIPPO", "BAN", "MELANIA", "TRUMP", "KOMA", "THE",
    "WHY", "CHEEMS", "NEIRO", "PENGU", "USUAL", "MOVE", "ME", "VANA", "BERA",
    "ANIME", "PLUME", "SONIC", "ZORA", "INIT", "HYPER", "KERNEL", "BABY",
    "STO", "PARTI", "NIL", "BR", "BMT", "FORM", "GUN", "WAL", "BANK", "EPT"
]

BINANCE_ENDPOINTS = [
    "https://binance.com",
    "https://binance.com",
    "https://binance.com",
    "https://binance.com"
]

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
        self.wfile.write(b"Binance Alpha OI Scanner Active")
    def log_message(self, format, *args):
        pass

def start_web_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# Lấy danh sách symbol Alpha thực tế đang mở giao dịch trên Binance Futures
def get_active_alpha_futures():
    global ACTIVE_BASE_URL
    alpha_candidates = set()
    
    # 1. Thử lấy từ API danh mục Binance Alpha chính thức
    try:
        alpha_url = "https://binance.com"
        res = requests.get(alpha_url, headers=HEADERS, timeout=8)
        if res.status_code == 200:
            for item in res.json().get("data", []):
                sym = item.get("symbol", "").upper().strip()
                if sym:
                    alpha_candidates.add(f"{sym}USDT")
                    alpha_candidates.add(f"1000{sym}USDT")
    except Exception:
        pass

    # 2. Gộp thêm danh sách dự phòng để đảm bảo không thiếu mã nào
    for name in RAW_ALPHA_NAMES:
        alpha_candidates.add(f"{name}USDT")
        alpha_candidates.add(f"1000{name}USDT")

    # 3. Đối chiếu với danh sách đang mở giao dịch thực tế trên Binance Futures (chỉ 1 request)
    for base_url in BINANCE_ENDPOINTS:
        try:
            res = requests.get(f"{base_url}/fapi/v1/ticker/24hr", headers=HEADERS, timeout=10)
            if res.status_code == 200 and res.text.strip():
                ACTIVE_BASE_URL = base_url
                all_tickers = res.json()
                # Lọc đúng các cặp Alpha và ưu tiên sắp xếp theo Volume 24h giảm dần
                matched = [
                    x for x in all_tickers
                    if x["symbol"] in alpha_candidates and float(x.get("quoteVolume", 0)) > 0
                ]
                matched.sort(key=lambda x: float(x["quoteVolume"]), reverse=True)
                # Giới hạn tối đa 25 đồng Alpha thanh khoản cao nhất để quét OI cực nhanh & không bao giờ bị 429
                return [x["symbol"] for x in matched[:25]], None
        except Exception as e:
            err = str(e)
    return [], "Không kết nối được Binance Futures"

# Lấy OI theo thời gian thực của từng đồng Alpha (cập nhật từng giây trên Binance)
def fetch_binance_oi_batch(symbols):
    oi_map = {}
    for sym in symbols:
        url = f"{ACTIVE_BASE_URL}/fapi/v1/openInterest?symbol={sym}"
        try:
            res = requests.get(url, headers=HEADERS, timeout=5)
            if res.status_code == 200:
                oi_map[sym] = float(res.json()["openInterest"])
            elif res.status_code == 429:
                return None # Báo hiệu chạm ngưỡng 429
        except Exception:
            pass
        # Giãn cách 1.2 giây mỗi request -> 25 coin mất đúng 30 giây, dùng chưa tới 2% giới hạn IP của Binance!
        time.sleep(1.2)
    return oi_map

def run_bot():
    print("🚀 Đang khởi động bot quét Binance Alpha OI (Real-time Tick)...", flush=True)
    
    while True:
        symbols, err = get_active_alpha_futures()
        if not symbols:
            print(f"⚠️ {err}. Đợi 60 giây thử lại...", flush=True)
            time.sleep(60)
            continue

        send_discord_raw(
            f"✅ **Bot {BOT_NAME} đã kết nối trực tiếp Binance Futures!**\n"
            f"• Đang theo dõi **Top {len(symbols)} đồng Binance Alpha** thanh khoản cao nhất: `{', '.join(symbols[:10])}...`\n"
            f"• Điều kiện báo kèo: Biến động OI 1 phút `> {MIN_OI_CHANGE_PCT}%`"
        )

        previous_oi = fetch_binance_oi_batch(symbols)
        if not previous_oi:
            time.sleep(60)
            continue

        while True:
            # Quét 25 coin mất ~30s, nghỉ thêm 30s để tròn đúng chu kỳ 60 giây (1 phút)
            time.sleep(30)
            current_oi = fetch_binance_oi_batch(symbols)
            if current_oi is None:
                print("⚠️ Chạm ngưỡng 429 tạm thời, nghỉ 2 phút...", flush=True)
                time.sleep(120)
                break

            changes = []
            for sym, oi_now in current_oi.items():
                oi_prev = previous_oi.get(sym)
                if oi_prev and oi_prev > 0:
                    pct_change = ((oi_now - oi_prev) / oi_prev) * 100
                    if pct_change > MIN_OI_CHANGE_PCT:
                        changes.append({
                            "symbol": sym,
                            "oi_pct": pct_change,
                            "oi_now": oi_now
                        })

            top_3 = sorted(changes, key=lambda x: x["oi_pct"], reverse=True)[:3]

            if top_3:
                message = f"**🔥 TOP 3 BINANCE ALPHA BIẾN ĐỘNG OI 1 PHÚT (> {MIN_OI_CHANGE_PCT}%):**\n\n"
                for idx, item in enumerate(top_3, start=1):
                    sym = item["symbol"]
                    binance_link = f"https://binance.com{sym}"
                    message += f"**{idx}. [{sym}]({binance_link})** 🟢\n"
                    message += f"• Biến động OI (1m): `{item['oi_pct']:+.4f}%`\n"
                    message += f"• Tổng OI: `{item['oi_now']:,.0f}`\n\n"
                send_discord_raw(message)
                print(f"📨 Đã bắn Top {len(top_3)} kèo Alpha OI lên Discord!", flush=True)
            else:
                print(f"⏳ Không có đồng Alpha nào tăng OI > {MIN_OI_CHANGE_PCT}% trong phút qua.", flush=True)

            previous_oi = current_oi

if __name__ == "__main__":
    threading.Thread(target=start_web_server, daemon=True).start()
    run_bot()
