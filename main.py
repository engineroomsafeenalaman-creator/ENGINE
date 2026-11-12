import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import requests

DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
TIMEFRAME = "5m"
MIN_OI_CHANGE = 0.001
SCAN_INTERVAL = 300

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

FAPI_ENDPOINTS = [
    "https://binance.com",
    "https://binance.com",
    "https://binance.com",
    "https://binance.com"
]

class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    def log_message(self, format, *args):
        pass

def start_dummy_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

def send_discord_raw(payload):
    if not DISCORD_WEBHOOK_URL:
        print("[Loi] Chua co DISCORD_WEBHOOK_URL")
        return
    try:
        res = requests.post(DISCORD_WEBHOOK_URL.strip(), json=payload, timeout=15)
        print(f"[Discord] Status: {res.status_code}")
    except Exception as e:
        print(f"[Discord] Error: {e}")

def get_working_fapi_base():
    for base_url in FAPI_ENDPOINTS:
        try:
            res = requests.get(f"{base_url}/fapi/v1/exchangeInfo", headers=HEADERS, timeout=8)
            if res.status_code == 200:
                print(f"[OK] Ket noi thanh cong: {base_url}")
                return base_url, res.json()
            else:
                print(f"[Chan IP] {base_url} -> {res.status_code}")
        except Exception as e:
            print(f"[Loi mang] {base_url}: {e}")
    return None, None

def get_binance_alpha_tokens():
    url = "https://binance.com"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            tokens = res.json().get("data", [])
            return {t.get("symbol", "").strip().upper() for t in tokens if t.get("symbol")}
    except Exception as e:
        print(f"[Loi Alpha API] {e}")
    return set()

def check_oi_change(args):
    symbol, fapi_base = args
    url = f"{fapi_base}/futures/data/openInterestHist"
    params = {"symbol": symbol, "period": TIMEFRAME, "limit": 2}
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) == 2:
                prev_oi = float(data["sumOpenInterestValue"])
                curr_oi = float(data["sumOpenInterestValue"])
                if prev_oi > 0:
                    change_pct = ((curr_oi - prev_oi) / prev_oi) * 100
                    return {
                        "symbol": symbol,
                        "oi_change_pct": change_pct,
                        "abs_change_pct": abs(change_pct),
                        "current_oi_usd": curr_oi
                    }
    except Exception:
        pass
    return None

def run_scan_cycle():
    print("--- Bat dau quet Binance Alpha OI (5m) ---")
    fapi_base, exchange_data = get_working_fapi_base()
    if not fapi_base or not exchange_data:
        msg = "⚠️ **Render bị Binance chặn IP (Lỗi 451):** Cần chuyển Region của Render sang **Singapore**."
        print(msg)
        send_discord_raw({"content": msg})
        return

    alpha_tokens = get_binance_alpha_tokens()
    if not alpha_tokens:
        print("[Loi] Khong lay duoc danh sach Alpha")
        return

    futures_map = {}
    for s in exchange_data.get("symbols", []):
        if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT":
            base = s.get("baseAsset", "").upper()
            symbol = s.get("symbol")
            clean_base = base[4:] if base.startswith("1000") else base
            futures_map[clean_base] = symbol

    target_symbols = [(futures_map[t], fapi_base) for t in alpha_tokens if t in futures_map]
    print(f"Dang quet {len(target_symbols)} cap Alpha Futures...")

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for item in executor.map(check_oi_change, target_symbols):
            if item and item["abs_change_pct"] > MIN_OI_CHANGE:
                results.append(item)

    results.sort(key=lambda x: x["abs_change_pct"], reverse=True)
    top_3 = results[:3]

    if not top_3:
        print("Khong co dong Alpha nao bien dong OI > 0.001%.")
        return

    fields = []
    for idx, coin in enumerate(top_3, start=1):
        sign = "+" if coin["oi_change_pct"] >= 0 else ""
        trend_icon = "🟢" if coin["oi_change_pct"] > 0 else "🔴"
        fields.append({
            "name": f"#{idx} • {coin['symbol']} {trend_icon}",
            "value": (
                f"• **Biến động OI (5m):** `{sign}{coin['oi_change_pct']:.4f}%`\n"
                f"• **Tổng OI hiện tại:** `${coin['current_oi_usd']:,.2f}`"
            ),
            "inline": False
        })

    payload = {
        "username": "Binance Alpha OI Radar",
        "embeds": [{
            "title": "⚡ TOP 3 BINANCE ALPHA BIẾN ĐỘNG OI MẠNH NHẤT (5M)",
            "description": f"Biến động Open Interest lớn hơn `{MIN_OI_CHANGE}%`.",
            "color": 16766720,
            "fields": fields,
            "footer": {"text": "Dữ liệu tự động từ Binance Futures & Alpha"}
        }]
    }
    send_discord_raw(payload)

if __name__ == "__main__":
    threading.Thread(target=start_dummy_server, daemon=True).start()
    while True:
        try:
            run_scan_cycle()
        except Exception as e:
            print(f"[Loi he thong] {e}")
        time.sleep(SCAN_INTERVAL)
