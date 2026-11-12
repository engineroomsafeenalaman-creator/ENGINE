import os
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from concurrent.futures import ThreadPoolExecutor
import requests

DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"
TIMEFRAME = "5m"          # Khung 5 phút
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
    """Lấy danh sách token thuộc danh mục Binance Alpha qua CoinGecko (Không bao giờ bị lỗi 429 trên Render)"""
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
            coins = res.json()
            alpha_set = {c.get("symbol", "").strip().upper() for c in coins if c.get("symbol")}
            print(f"[OK] Lay duoc {len(alpha_set)} token thuoc he Binance Alpha.")
            return alpha_set
        print(f"[Loi CoinGecko Alpha] Status: {res.status_code}")
    except Exception as e:
        print(f"[Loi CoinGecko Alpha] {e}")
    return set()

def get_okx_swap_symbols():
    """Lấy danh sách các cặp USDT Perpetual trên OKX (Mở 100% cho IP Mỹ của Render)"""
    url = "https://okx.com"
    params = {"instType": "SWAP"}
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            items = res.json().get("data", [])
            symbols_map = {}
            for s in items:
                if s.get("state") == "live" and s.get("settleCcy") == "USDT":
                    inst_id = s.get("instId", "")  # VD: GRIFFAIN-USDT-SWAP
                    base = inst_id.split("-")[0].upper()
                    clean_base = base[4:] if base.startswith("1000") else base
                    symbols_map[clean_base] = inst_id
            return symbols_map
    except Exception as e:
        print(f"[Loi danh sach OKX] {e}")
    return {}

def check_oi_change(inst_id):
    """Lấy dữ liệu Open Interest 2 kỳ 5m gần nhất trên OKX và tính % biến động"""
    url = "https://okx.com"
    # Lấy dữ liệu theo đồng cơ sở (ccy)
    ccy = inst_id.split("-")[0]
    params = {
        "ccy": ccy,
        "period": "5m"
    }
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if res.status_code == 200:
            data_list = res.json().get("data", [])
            if isinstance(data_list, list) and len(data_list) >= 2:
                # OKX trả về mảng: [timestamp, oi_usd, vol_usd], mới nhất ở vị trí 0
                newest = data_list[0]
                previous = data_list[1]
                curr_oi = float(newest[1])
                prev_oi = float(previous[1])
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

def run_scan_cycle():
    print("--- Bat dau quet Binance Alpha OI (5m) ---")
    alpha_tokens = get_binance_alpha_tokens()
    if not alpha_tokens:
        return

    futures_map = get_okx_swap_symbols()
    if not futures_map:
        print("[Loi] Khong lay duoc danh sach Futures.")
        return

    target_symbols = [futures_map[t] for t in alpha_tokens if t in futures_map]
    print(f"[OK] Dang quet {len(target_symbols)} cap Alpha Futures...")

    results = []
    with ThreadPoolExecutor(max_workers=8) as executor:
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
            "description": f"Danh sách token **Binance Alpha** có biến động Open Interest trên `{MIN_OI_CHANGE}%`.",
            "color": 16766720,
            "fields": fields,
            "footer": {"text": "Dữ liệu tự động cập nhật mỗi 5 phút"}
        }]
    }
    send_discord_raw(payload)

if __name__ == "__main__":
    threading.Thread(target=start_dummy_server, daemon=True).start()
    send_discord_raw({"content": "✅ **Bot Binance Alpha OI Radar đã khởi động mượt mà!**"})
    while True:
        try:
            run_scan_cycle()
        except Exception as e:
            print(f"[Loi he thong] {e}")
        time.sleep(SCAN_INTERVAL)
