import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import requests

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"
TIMEFRAME = "5min"        # Khung 5 phút
MIN_OI_CHANGE = 0.001     # Ngưỡng biến động tối thiểu (%)
SCAN_INTERVAL = 300       # Quét mỗi 5 phút (300 giây)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()
    def log_message(self, format, *args):
        pass

def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

def send_discord_raw(payload):
    if not DISCORD_WEBHOOK_URL or "DAN_LINK" in DISCORD_WEBHOOK_URL:
        print("[LOI] Ban chua dan link Webhook Discord!")
        return
    try:
        res = requests.post(DISCORD_WEBHOOK_URL.strip(), json=payload, timeout=15)
        print(f"[Discord Status] Ma phan hoi: {res.status_code}")
    except Exception as e:
        print(f"[Discord Error] {e}")

def get_binance_alpha_tokens():
    """Lấy danh sách token thuộc danh mục Binance Alpha (API này không chặn IP Mỹ)"""
    url = "https://binance.com"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            tokens = res.json().get("data", [])
            alpha_set = {t.get("symbol", "").strip().upper() for t in tokens if t.get("symbol")}
            print(f"[OK] Lay duoc {len(alpha_set)} token thuoc he Binance Alpha.")
            return alpha_set
        print(f"[Loi Alpha API] Status: {res.status_code}")
    except Exception as e:
        print(f"[Loi Alpha API] {e}")
    return set()

def get_bybit_linear_symbols():
    """Lấy danh sách các cặp USDT Perpetual đang giao dịch (Không chặn IP Mỹ)"""
    url = "https://bybit.com"
    params = {"category": "linear", "limit": 1000}
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            items = res.json().get("result", {}).get("list", [])
            symbols_map = {}
            for s in items:
                if s.get("status") == "Trading" and s.get("quoteCoin") == "USDT":
                    base = s.get("baseCoin", "").upper()
                    sym = s.get("symbol")
                    clean_base = base[4:] if base.startswith("1000") else base
                    symbols_map[clean_base] = sym
            return symbols_map
    except Exception as e:
        print(f"[Loi danh sach Futures] {e}")
    return {}

def check_oi_change(symbol):
    """Lấy dữ liệu Open Interest 2 kỳ 5m gần nhất và tính % biến động"""
    url = "https://bybit.com"
    params = {
        "category": "linear",
        "symbol": symbol,
        "intervalTime": TIMEFRAME,
        "limit": 2
    }
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data_list = res.json().get("result", {}).get("list", [])
            if isinstance(data_list, list) and len(data_list) == 2:
                # Bybit trả về phần tử mới nhất trước, cũ hơn sau
                newest, previous = data_list
                curr_oi = float(newest["openInterest"])
                prev_oi = float(previous["openInterest"])
                if prev_oi > 0:
                    change_pct = ((curr_oi - prev_oi) / prev_oi) * 100
                    return {
                        "symbol": symbol,
                        "oi_change_pct": change_pct,
                        "abs_change_pct": abs(change_pct),
                        "current_oi_qty": curr_oi
                    }
    except Exception:
        pass
    return None

def run_scan_cycle():
    print("--- Bat dau quet Binance Alpha OI (5m) ---")
    alpha_tokens = get_binance_alpha_tokens()
    if not alpha_tokens:
        return

    futures_map = get_bybit_linear_symbols()
    if not futures_map:
        print("[Loi] Khong lay duoc danh sach cap Futures.")
        return

    target_symbols = [futures_map[t] for t in alpha_tokens if t in futures_map]
    print(f"[OK] Dang quet {len(target_symbols)} cap Alpha Futures...")

    results = []
    with ThreadPoolExecutor(max_workers=12) as executor:
        for item in executor.map(check_oi_change, target_symbols):
            if item and item["abs_change_pct"] > MIN_OI_CHANGE:
                results.append(item)

    results.sort(key=lambda x: x["abs_change_pct"], reverse=True)
    top_3 = results[:3]

    if not top_3:
        print("[Ket qua] Khong co dong Alpha nao bien dong OI > 0.001%.")
        return

    fields = []
    for idx, coin in enumerate(top_3, start=1):
        sign = "+" if coin["oi_change_pct"] >= 0 else ""
        trend_icon = "🟢" if coin["oi_change_pct"] > 0 else "🔴"
        fields.append({
            "name": f"#{idx} • {coin['symbol']} {trend_icon}",
            "value": (
                f"• **Biến động OI (5m):** `{sign}{coin['oi_change_pct']:.4f}%`\n"
                f"• **Tổng OI hiện tại:** `{coin['current_oi_qty']:,.2f} {coin['symbol'].replace('USDT', '')}`"
            ),
            "inline": False
        })

    payload = {
        "username": "Binance Alpha OI Radar",
        "embeds": [{
            "title": "⚡ TOP 3 BINANCE ALPHA BIẾN ĐỘNG OI MẠNH NHẤT (5M)",
            "description": f"Danh sách token **Binance Alpha** có biến động Open Interest trên `{MIN_OI_CHANGE}%`.",
            "color": 16766720,
            "fields": fields,
            "footer": {"text": "Dữ liệu tự động cập nhật mỗi 5 phút"}
        }]
    }
    send_discord_raw(payload)

if __name__ == "__main__":
    threading.Thread(target=start_dummy_server, daemon=True).start()
    send_discord_raw({"content": "✅ **Bot Binance Alpha OI Radar đã sẵn sàng!**"})
    while True:
        try:
            run_scan_cycle()
        except Exception as e:
            print(f"[Loi he thong] {e}")
        time.sleep(SCAN_INTERVAL)
