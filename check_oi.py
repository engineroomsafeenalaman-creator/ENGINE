import os
import time
import requests
from datetime import datetime, timezone

# 1. DÁN LINK DISCORD WEBHOOK CỦA BẠN VÀO DÒNG DƯỚI ĐÂY:
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570759626285125753/VTk9ScV2fGroZbp8MZMogLsoK0i8oq62oasdm8I22D8g0QLLXx2icna-M9xuuvZ6fhTl"

COIN_FILE = "coin.txt"
DEFAULT_COIN = "BTCUSDT"
MIN_OI_CHANGE = 0.01

BINANCE_ENDPOINTS = [
    "https://www.binance.com/en/futures/OUSDT"
]

def get_coin():
    if os.path.exists(COIN_FILE):
        with open(COIN_FILE, "r", encoding="utf-8") as f:
            c = f.read().strip().upper()
            if c:
                return c
    return DEFAULT_COIN

def get_binance_oi(symbol):
    for base_url in BINANCE_ENDPOINTS:
        try:
            res = requests.get(
                f"{base_url}/fapi/v1/openInterest",
                params={"symbol": symbol},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8
            )
            if res.status_code == 200:
                data = res.json()
                if "openInterest" in data:
                    return float(data["openInterest"]), base_url
        except Exception as e:
            print(f"Lỗi kết nối {base_url}: {e}")
    return None, None

def send_discord(symbol, start_oi, end_oi, change_pct, source):
    if not DISCORD_WEBHOOK_URL or "YOUR_WEBHOOK_ID" in DISCORD_WEBHOOK_URL:
        print("❌ LỖI: Bạn chưa dán link Discord Webhook vào dòng số 7!")
        return False

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
            "footer": {"text": f"Nguồn: {source} | GitHub Actions"},
            "timestamp": datetime.now(timezone.utc).isoformat()
        }]
    }
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        r.raise_for_status()
        print("✅ Đã gửi thông báo Discord thành công!")
        return True
    except Exception as e:
        print(f"❌ Lỗi gửi Discord: {e}")
        return False

def main():
    symbol = get_coin()
    last_state = None
    print(f"🚀 Bắt đầu chạy Binance OI Radar cho {symbol}...")

    for cycle in range(1, 5):
        samples = []
        used_source = ""

        for step in range(7):
            oi, src = get_binance_oi(symbol)
            if oi is not None:
                samples.append(oi)
                used_source = src
                print(f"  [Phút {cycle} - Mẫu {step+1}/7] OI: {oi:,.3f}")
            else:
                print(f"  [Phút {cycle} - Mẫu {step+1}/7] Không lấy được dữ liệu!")

            if step < 6:
                time.sleep(10)

        # Kiểm tra đã lấy đủ dữ liệu chưa
        if len(samples) >= 2:
            start_oi = samples[0]   # Mẫu đầu tiên của phút
            end_oi = samples[-1]    # Mẫu cuối cùng của phút

            if start_oi > 0:
                change_pct = ((end_oi - start_oi) / start_oi) * 100
                print(f"📊 [Chốt Phút {cycle}] Đầu: {start_oi:,.3f} | Cuối: {end_oi:,.3f} | Biến động: {change_pct:+.5f}%")

                if change_pct > MIN_OI_CHANGE and last_state != "UP":
                    if send_discord(symbol, start_oi, end_oi, change_pct, used_source):
                        last_state = "UP"
                elif change_pct < -MIN_OI_CHANGE and last_state != "DOWN":
                    if send_discord(symbol, start_oi, end_oi, change_pct, used_source):
                        last_state = "DOWN"

        samples.clear()

if __name__ == "__main__":
    main()
