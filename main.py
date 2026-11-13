import os
import time
import requests
from datetime import datetime, timezone

# Dán trực tiếp link Discord Webhook của bạn vào đây:
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"

COIN_FILE = "coin.txt"
DEFAULT_COIN = "BTCUSDT"
MIN_OI_CHANGE = 0.001

BINANCE_ENDPOINTS = [
    "https://www.binance.com/en/futures/BTCUSDT",
]

def get_coin():
    if os.path.exists(COIN_FILE):
        with open(COIN_FILE, "r", encoding="utf-8") as f:
            c = f.read().strip().upper()
            if c:
                return c
    return DEFAULT_COIN

def get_BINANCE_oi(symbol):
    for base_url in BINANCE_ENDPOINTS:
        try:
            res = requests.get(
                f"{base_url}/v5/market/tickers",
                params={"category": "linear", "symbol": symbol},
                timeout=8
            )
            data = res.json()
            if data.get("retCode") == 0:
                items = data.get("result", {}).get("list", [])
                if items and "openInterest" in items:
                    return float(items["openInterest"])
        except Exception as e:
            print(f"Lỗi kết nối {base_url}: {e}")
    return None

def send_discord(symbol, start_oi, end_oi, change_pct):
    if not DISCORD_WEBHOOK_URL or "YOUR_WEBHOOK_ID" in DISCORD_WEBHOOK_URL:
        print("Chưa cấu hình link Discord Webhook!")
        return

    base_asset = symbol.replace("USDT", "")
    diff = end_oi - start_oi
    direction = "TĂNG VƯỢT NGƯỠNG 🟢" if change_pct > 0 else "GIẢM VƯỢT NGƯỠNG 🔴"
    color = 5763719 if change_pct > 0 else 15548997

    payload = {
        "embeds": [{
            "title": f"🚨 BINANCE OI {symbol} ({direction})",
            "color": color,
            "fields": [
                {"name": "Biến động (%)", "value": f"`{change_pct:+.5f}%`", "inline": True},
                {"name": f"Chênh lệch ({base_asset})", "value": f"`{diff:+,.3f} {base_asset}`", "inline": True},
                {"name": "OI Đầu Phút", "value": f"`{start_oi:,.3f} {base_asset}`", "inline": False},
                {"name": "OI Cuối Phút", "value": f"`{end_oi:,.3f} {base_asset}`", "inline": False}
            ],
            "footer": {"text": "Chạy trực tiếp từ GitHub Actions"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }
    requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)

def main():
    symbol = get_coin()
    last_state = None
    print(f"Bắt đầu kiểm tra {symbol} trong phiên GitHub Actions...")

    # Chạy 4 chu kỳ (mỗi chu kỳ 60s = 4 phút)
    for cycle in range(1, 5):
        samples = []
        for step in range(7):  # Lấy 7 mẫu cách nhau 10s (0s -> 60s)
            oi = get_BINANCE_oi(symbol)
            if oi:
                samples.append(oi)
            if step < 6:
                time.sleep(10)

        if len(samples) >= 2 and samples > 0:
            start_oi = samples
            end_oi = samples[-1]
            change_pct = ((end_oi - start_oi) / start_oi) * 100
            print(f"[Phút {cycle}] Đầu: {start_oi} | Cuối: {end_oi} | Biến động: {change_pct:+.5f}%")

            if change_pct > MIN_OI_CHANGE and last_state != "UP":
                send_discord(symbol, start_oi, end_oi, change_pct)
                last_state = "UP"
            elif change_pct < -MIN_OI_CHANGE and last_state != "DOWN":
                send_discord(symbol, start_oi, end_oi, change_pct)
                last_state = "DOWN"

if __name__ == "__main__":
    main()
