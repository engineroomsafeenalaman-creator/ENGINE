import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import requests

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"
PROXY_URL = "http://cpethehk:viqqd5yyfxwr@45.38.107.97:6014"
TIMEFRAME = "5m"
MIN_OI_CHANGE = 0.001
SCAN_INTERVAL = 300

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "application/json"
}

PROXIES = {"http": PROXY_URL.strip(), "https": PROXY_URL.strip()} if PROXY_URL else None
FAPI_BASE = "https://binance.com"

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
        print("[LOI] Ban chua dan link Webhook Discord vao bien DISCORD_WEBHOOK_URL!")
        return
    try:
        res = requests.post(DISCORD_WEBHOOK_URL.strip(), json=payload, timeout=15)
        print(f"[Discord Status] Ma phan hoi: {res.status_code}")
    except Exception as e:
        print(f"[Discord Error] {e}")

def get_binance_alpha_tokens():
    url = "https://binance.com"
    try:
        res = requests.get(url, headers=HEADERS, proxies=PROXIES, timeout=15)
        if res.status_code == 200:
            tokens = res.json().get("data", [])
            return {t.get("symbol", "").strip().upper() for t in tokens if t.get("symbol")}
    except Exception as e:
        print(f"[Loi Alpha API] {e}")
    return set()

def check_oi_change(symbol):
    url = f"{FAPI_BASE}/futures/data/openInterestHist"
    params = {"symbol": symbol, "period": TIMEFRAME, "limit": 2}
    try:
        res = requests.get(url, params=params, headers=HEADERS, proxies=PROXIES, timeout=10)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) == 2:
                first_candle, second_candle = data
                prev_oi = float(first_candle["sumOpenInterestValue"])
                curr_oi = float(second_candle["sumOpenInterestValue"])
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
    print("--- Bat dau quet Binance Alpha OI (5m) qua Proxy ---")
    try:
        res = requests.get(f"{FAPI_BASE}/fapi/v1/exchangeInfo", headers=HEADERS, proxies=PROXIES, timeout=12)
        if res.status_code != 200:
            print(f"[Loi Binance Futures] Ma loi: {res.status_code} (Proxy nay dang o My, hay doi sang Proxy chau Au)")
            return
        exchange_data = res.json()
    except Exception as e:
        print(f"[Loi ket noi Proxy] {e}")
        return

    alpha_tokens = get_binance_alpha_tokens()
    if not alpha_tokens:
        return

    futures_map = {}
    for s in exchange_data.get("symbols", []):
        if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT":
            base = s.get("baseAsset", "").upper()
            symbol = s.get("symbol")
            clean_base = base[4:] if base.startswith("1000") else base
            futures_map[clean_base] = symbol

    target_symbols = [futures_map[t] for t in alpha_tokens if t in futures_map]
    print(f"[OK] Dang quet {len(target_symbols)} cap Alpha Futures...")

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
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
    send_discord_raw({"content": "✅ **Bot Binance Alpha OI Radar đã kết nối thành công với Discord!**"})
    while True:
        try:
            run_scan_cycle()
        except Exception as e:
            print(f"[Loi he thong] {e}")
        time.sleep(SCAN_INTERVAL)
