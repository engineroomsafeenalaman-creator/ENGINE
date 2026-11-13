import os
import time
import requests
from datetime import datetime, timezone

# 1. THÔNG TIN CẤU HÌNH CỦA BẠN:
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1570759626285125753/VTk9ScV2fGroZbp8MZMogLsoK0i8oq62oasdm8I22D8g0QLLXx2icna-M9xuuvZ6fhTl"
DISCORD_BOT_TOKEN = "MTU3MDc4NDk5NzgxMDUxMTk2Mg.GHNpFa.dDMokpqRM0RKi5HY6rNf5P3agixVDT3nSKBfwc"
DISCORD_CHANNEL_ID = "1570759584119914558"

COIN_FILE = "coin.txt"
DEFAULT_COIN = "BTCUSDT"
MIN_OI_CHANGE = 0.001

BINANCE_ENDPOINTS = [
    "https://binance.com"
]

def check_discord_coin_command():
    """Đọc 5 tin nhắn gần nhất trên kênh Discord xem có lệnh !coin không"""
    if not DISCORD_BOT_TOKEN or not DISCORD_CHANNEL_ID or "DÁN_" in DISCORD_BOT_TOKEN:
        return

    api_path = "/api/v10/channels/"
    url = f"https://discord.com{api_path}{DISCORD_CHANNEL_ID}/messages?limit=5"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}

    try:
        res = requests.get(url, headers=headers, timeout=8)
        if res.status_code == 200:
            messages = res.json()
            for msg in messages:
                content = msg.get("content", "").strip()
                if content.lower().startswith("!coin "):
                    parts = content.split(" ", 1)
                    if len(parts) > 1:
                        new_coin = parts.strip().upper()
                        if not new_coin.endswith("USDT"):
                            new_coin += "USDT"

                        current_coin = ""
                        if os.path.exists(COIN_FILE):
                            with open(COIN_FILE, "r", encoding="utf-8") as f:
                                current_coin = f.read().strip().upper()

                        if new_coin and new_coin != current_coin:
                            with open(COIN_FILE, "w", encoding="utf-8") as f:
                                f.write(new_coin)
                            print(f"🔄 Đã nhận lệnh từ Discord: Đổi coin sang {new_coin}")
                            requests.post(
                                DISCORD_WEBHOOK_URL,
                                json={"content": f"✅ Đã nhận lệnh! Chuyển sang theo dõi **{new_coin}**."},
                                timeout=8
                            )
                        break
        else:
            print(f"⚠️ Discord API trả về mã {res.status_code}: {res.text}")
    except Exception as e:
        print(f"Lỗi đọc lệnh Discord: {e}")

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

def get_binance_vol(symbol):
    for base_url in BINANCE_ENDPOINTS:
        try:
            res = requests.get(
                f"{base_url}/fapi/v1/ticker/24hr",
                params={"symbol": symbol},
                headers={"User-Agent": "Mozilla/5.0"},
                timeout=8
            )
            if res.status_code == 200:
                data = res.json()
                if "volume" in data:
                    return float(data["volume"])
        except Exception as e:
            print(f"Lỗi kết nối Vol {base_url}: {e}")
    return None

def send_discord(symbol, start_oi, end_oi, change_pct, start_vol, end_vol, source):
    if not DISCORD_WEBHOOK_URL or "YOUR_WEBHOOK_ID" in DISCORD_WEBHOOK_URL:
        print("❌ LỖI: Bạn chưa dán link Discord Webhook!")
        return False

    base_asset = symbol.replace("USDT", "")
    diff = end_oi - start_oi
    direction = "TĂNG VƯỢT NGƯỠNG 🟢" if change_pct > 0 else "GIẢM VƯỢT NGƯỠNG 🔴"
    color = 5763719 if change_pct > 0 else 15548997

    if start_vol is not None and end_vol is not None and start_vol > 0:
        vol_diff = end_vol - start_vol
        vol_change_pct = (vol_diff / start_vol) * 100
        vol_pct_text = f"`{vol_change_pct:+.5f}%`"
        vol_diff_text = f"`{vol_diff:+,.3f} {base_asset}`"
    else:
        vol_pct_text = "`N/A`"
        vol_diff_text = "`N/A`"

    payload = {
        "embeds": [{
            "title": f"🚨 BINANCE OI {symbol} ({direction})",
            "color": color,
            "fields": [
                {"name": "Biến động OI (%)", "value": f"`{change_pct:+.5f}%`", "inline": True},
                {"name": f"Chênh lệch OI ({base_asset})", "value": f"`{diff:+,.3f} {base_asset}`", "inline": True},
                {"name": "Biến động Vol (%)", "value": vol_pct_text, "inline": True},
                {"name": f"Chênh lệch Vol ({base_asset})", "value": vol_diff_text, "inline": True}
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
    check_discord_coin_command()
    symbol = get_coin()
    last_state = None
    print(f"🚀 Bắt đầu chạy Binance OI Radar cho {symbol}...")

    for cycle in range(1, 55):
        check_discord_coin_command()
        new_symbol = get_coin()
        if new_symbol != symbol:
            symbol = new_symbol
            last_state = None
            print(f"🔄 Đã chuyển sang theo dõi đồng mới: {symbol}")

        samples = []
        vol_samples = []
        used_source = ""

        for step in range(7):
            oi, src = get_binance_oi(symbol)
            if oi is not None:
                samples.append(oi)
                used_source = src
                if step == 0 or step == 6:
                    vol = get_binance_vol(symbol)
                    vol_samples.append(vol)
                print(f"  [Phút {cycle} - Mẫu {step+1}/7] OI: {oi:,.3f}")
            else:
                print(f"  [Phút {cycle} - Mẫu {step+1}/7] Không lấy được dữ liệu!")

            if step < 6:
                time.sleep(10)

        if len(samples) >= 2:
            start_oi = samples
            end_oi = samples[-1]
            start_vol = vol_samples if len(vol_samples) >= 1 else None
            end_vol = vol_samples[-1] if len(vol_samples) >= 2 else None

            if start_oi > 0:
                change_pct = ((end_oi - start_oi) / start_oi) * 100
                print(f"📊 [Chốt Phút {cycle}] Đầu: {start_oi:,.3f} | Cuối: {end_oi:,.3f} | Biến động: {change_pct:+.5f}%")

                if change_pct > MIN_OI_CHANGE and last_state != "UP":
                    if send_discord(symbol, start_oi, end_oi, change_pct, start_vol, end_vol, used_source):
                        last_state = "UP"
                elif change_pct < -MIN_OI_CHANGE and last_state != "DOWN":
                    if send_discord(symbol, start_oi, end_oi, change_pct, start_vol, end_vol, used_source):
                        last_state = "DOWN"

        samples.clear()
        vol_samples.clear()

if __name__ == "__main__":
    main()
