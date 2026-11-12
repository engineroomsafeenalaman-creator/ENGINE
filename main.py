import os
import time
import random
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

FAPI_BASE = "https://binance.com"

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
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL.strip(), json=payload, timeout=15)
    except Exception as e:
        print(f"[Discord Error] {e}")

def get_working_proxy():
    """Tự động tìm proxy sạch (ngoài Mỹ/Singapore bị chặn) để truy cập Binance Futures"""
    # 1. Thử kết nối trực tiếp trước
    try:
        res = requests.get(f"{FAPI_BASE}/fapi/v1/ping", headers=HEADERS, timeout=5)
        if res.status_code == 200:
            print("[OK] Kết nối trực tiếp thành công!")
            return None
    except Exception:
        pass

    # 2. Nếu bị chặn IP (451), tự động tải danh sách proxy công khai và lọc proxy sống
    print("[Info] IP trực tiếp bị chặn, đang tìm Proxy sạch...")
    proxy_sources = [
        "https://proxyscrape.com",
        "https://githubusercontent.com"
    ]
    candidates = []
    for src in proxy_sources:
        try:
            r = requests.get(src, timeout=10)
            if r.status_code == 200:
                lines = [line.strip() for line in r.text.splitlines() if ":" in line]
                candidates.extend(lines[:80])
        except Exception:
            continue

    random.shuffle(candidates)

    def test_proxy(proxy_ip):
        proxies = {"http": f"http://{proxy_ip}", "https": f"http://{proxy_ip}"}
        try:
            r = requests.get(f"{FAPI_BASE}/fapi/v1/ping", headers=HEADERS, proxies=proxies, timeout=4)
            if r.status_code == 200:
                return proxies
        except Exception:
            pass
        return None

    with ThreadPoolExecutor(max_workers=20) as executor:
        for valid_proxy in executor.map(test_proxy, candidates[:100]):
            if valid_proxy:
                print(f"[OK] Đã tìm thấy Proxy sạch: {valid_proxy['http']}")
                return valid_proxy

    return "FAILED"

def get_binance_alpha_tokens(proxies):
    url = "https://binance.com"
    try:
        res = requests.get(url, headers=HEADERS, proxies=proxies, timeout=15)
        if res.status_code == 200:
            tokens = res.json().get("data", [])
            return {t.get("symbol", "").strip().upper() for t in tokens if t.get("symbol")}
    except Exception as e:
        print(f"[Loi Alpha API] {e}")
    return set()

def check_oi_change(args):
    symbol, proxies = args
    url = f"{FAPI_BASE}/futures/data/openInterestHist"
    params = {"symbol": symbol, "period": TIMEFRAME, "limit": 2}
    try:
        res = requests.get(url, params=params, headers=HEADERS, proxies=proxies, timeout=8)
        if res.status_code == 200:
            data = res.json()
            if isinstance(data, list) and len(data) == 2:
                prev_oi = float(data[0])
                curr_oi = float(data[1])
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
    print("--- Bắt đầu quét Binance Alpha OI (5m) ---")
    proxies = get_working_proxy()
    if proxies == "FAILED":
        print("[Cảnh báo] Chưa tìm được proxy phù hợp ở chu kỳ này, sẽ thử lại sau 5 phút.")
        return

    try:
        res = requests.get(f"{FAPI_BASE}/fapi/v1/exchangeInfo", headers=HEADERS, proxies=proxies, timeout=12)
        if res.status_code != 200:
            return
        exchange_data = res.json()
    except Exception as e:
        print(f"[Loi ExchangeInfo] {e}")
        return

    alpha_tokens = get_binance_alpha_tokens(proxies)
    if not alpha_tokens:
        return

    futures_map = {}
    for s in exchange_data.get("symbols", []):
        if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT":
            base = s.get("baseAsset", "").upper()
            symbol = s.get("symbol")
            clean_base = base[4:] if base.startswith("1000") else base
            futures_map[clean_base] = symbol

    target_symbols = [(futures_map[t], proxies) for t in alpha_tokens if t in futures_map]
    print(f"Đang quét {len(target_symbols)} cặp Alpha Futures...")

    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        for item in executor.map(check_oi_change, target_symbols):
            if item and item["abs_change_pct"] > MIN_OI_CHANGE:
                results.append(item)

    results.sort(key=lambda x: x["abs_change_pct"], reverse=True)
    top_3 = results[:3]

    if not top_3:
        print("Không có đồng Alpha nào biến động OI > 0.001%.")
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
