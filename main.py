import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import requests

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"
MIN_OI_CHANGE = 0.001
SCAN_INTERVAL = 300

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
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

def send_discord(payload):
    try:
        res = requests.post(DISCORD_WEBHOOK_URL.strip(), json=payload, timeout=15)
        print(f"[Discord] Status: {res.status_code}")
    except Exception as e:
        print(f"[Discord Error] {e}")

def get_alpha_tokens():
    url = "https://coingecko.com"
    params = {
        "vs_currency": "usd",
        "category": "binance-alpha-spotlight",
        "order": "market_cap_desc",
        "per_page": 250,
        "page": 1
    }
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            return {c.get("symbol", "").strip().upper() for c in res.json() if c.get("symbol")}
    except Exception as e:
        print(f"[Loi Alpha] {e}")
    return set()

def get_okx_coins():
    url = "https://okx.com"
    try:
        res = requests.get(url, params={"instType": "SWAP"}, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            coins = set()
            for s in res.json().get("data", []):
                if s.get("state") == "live" and s.get("settleCcy") == "USDT":
                    inst_id = s.get("instId", "")
                    base = inst_id.split("-").pop(0).upper()
                    clean_base = base[4:] if base.startswith("1000") else base
                    coins.add(clean_base)
            return coins
    except Exception as e:
        print(f"[Loi OKX List] {e}")
    return set()

def check_oi(ccy):
    url = "https://okx.com"
    try:
        res = requests.get(url, params={"ccy": ccy, "period": "5m"}, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            items = res.json().get("data", [])
            if len(items) >= 2:
                iter_items = iter(items)
                newest_row = next(iter_items)
                prev_row = next(iter_items)
                
                _, curr_oi_str, _ = newest_row
                _, prev_oi_str, _ = prev_row
                
                curr_oi = float(curr_oi_str)
                prev_oi = float(prev_oi_str)
                if prev_oi > 0:
                    change_pct = ((curr_oi - prev_oi) / prev_oi) * 100
                    return {
                        "symbol": f"{ccy}USDT",
                        "oi_change_pct": change_pct,
                        "abs_change_pct": abs(change_pct),
                        "current_oi_usd": curr_oi
                    }
    except Exception:
        pass
    return None

def run_scan():
    print("--- Dang quet du lieu ---")
    alpha_set = get_alpha_tokens()
    okx_set = get_okx_coins()
    targets = list(alpha_set.intersection(okx_set))
    print(f"[OK] Tim thay {len(targets)} dong Binance Alpha co Futures.")

    if not targets:
        return

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        for item in executor.map(check_oi, targets):
            if item and item["abs_change_pct"] > MIN_OI_CHANGE:
                results.append(item)

    results.sort(key=lambda x: x["abs_change_pct"], reverse=True)
    top_3 = results[:3]

    if not top_3:
        print("Khong co dong nao bien dong > 0.001%.")
        return

    fields = []
    for idx, coin in enumerate(top_3, start=1):
        sign = "+" if coin["oi_change_pct"] >= 0 else ""
        icon = "🟢" if coin["oi_change_pct"] > 0 else "🔴"
        fields.append({
            "name": f"#{idx} • {coin['symbol']} {icon}",
            "value": f"• **Biến động OI (5m):** `{sign}{coin['oi_change_pct']:.4f}%`\n• **Tổng OI:** `${coin['current_oi_usd']:,.2f}`",
            "inline": False
        })

    send_discord({
        "username": "Binance Alpha OI Radar",
        "embeds": [{
            "title": "⚡ TOP 3 BINANCE ALPHA BIẾN ĐỘNG OI MẠNH NHẤT (5M)",
            "color": 16766720,
            "fields": fields
        }]
    })

if __name__ == "__main__":
    threading.Thread(target=start_dummy_server, daemon=True).start()
    while True:
        try:
            run_scan()
        except Exception as e:
            print(f"[Loi] {e}")
        time.sleep(SCAN_INTERVAL)
