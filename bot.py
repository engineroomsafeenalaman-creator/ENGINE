import os
import requests
from concurrent.futures import ThreadPoolExecutor

# Cấu hình biến môi trường (Lấy từ GitHub Secrets)
DISCORD_WEBHOOK_URL = os.environ.get("https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN")
TIMEFRAME = "5m"          # Khung thời gian 5 phút
MIN_OI_CHANGE = 0.001     # Ngưỡng biến động tối thiểu (%)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def get_binance_alpha_tokens():
    """Lấy danh sách symbol các token thuộc danh mục Binance Alpha"""
    url = "https://binance.com"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        data = res.json()
        tokens = data.get("data", [])
        return {t.get("symbol", "").upper() for t in tokens if t.get("symbol")}
    except Exception as e:
        print(f"Lỗi khi lấy danh sách Binance Alpha: {e}")
        return set()

def get_active_futures_symbols():
    """Lấy danh sách các cặp USDT Futures đang giao dịch trên Binance"""
    url = "https://binance.com"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        data = res.json()
        futures_map = {}
        for s in data.get("symbols", []):
            if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT":
                base = s.get("baseAsset", "").upper()
                symbol = s.get("symbol")
                clean_base = base.replace("1000", "") if base.startswith("1000") else base
                futures_map[clean_base] = symbol
        return futures_map
    except Exception as e:
        print(f"Lỗi khi lấy danh sách Futures: {e}")
        return {}

def check_oi_change(symbol):
    """Lấy dữ liệu Open Interest 2 kỳ 5m gần nhất để tính % biến động"""
    url = "https://binance.com"
    params = {
        "symbol": symbol,
        "period": TIMEFRAME,
        "limit": 2
    }
    try:
        res = requests.get(url, params=params, headers=HEADERS, timeout=10)
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

def send_discord_notification(top_coins):
    """Gửi kết quả qua Discord Webhook"""
    if not DISCORD_WEBHOOK_URL:
        print("Chưa cấu hình DISCORD_WEBHOOK_URL!")
        return

    if not top_coins:
        print("Không có đồng Alpha nào biến động OI > 0.001% trong 5 phút qua.")
        return

    fields = []
    for idx, coin in enumerate(top_coins, start=1):
        sign = "+" if coin["oi_change_pct"] >= 0 else ""
        trend_icon = "🟢" if coin["oi_change_pct"] > 0 else "🔴"
        fields.append({
            "name": f"#{idx} {coin['symbol']} {trend_icon}",
            "value": (
                f"• **Biến động OI (5m):** `{sign}{coin['oi_change_pct']:.4f}%`\n"
                f"• **Tổng OI hiện tại:** `${coin['current_oi_usd']:,.2f}`"
            ),
            "inline": False
        })

    payload = {
        "username": "Binance Alpha OI Radar (5m)",
        "embeds": [
            {
                "title": "⚡ TOP 3 BINANCE ALPHA BIẾN ĐỘNG OI KHUNG 5 PHÚT",
                "description": f"Các token thuộc hệ **Binance Alpha** có biến động Open Interest lớn hơn `{MIN_OI_CHANGE}%`.",
                "color": 16766720,
                "fields": fields,
                "footer": {
                    "text": "Dữ liệu từ Binance Futures & Alpha API"
                }
            }
        ]
    }

    res = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
    if res.status_code in (200, 204):
        print("Đã gửi tin nhắn thành công về Discord!")
    else:
        print(f"Gửi Discord thất bại: {res.status_code} - {res.text}")

def main():
    alpha_tokens = get_binance_alpha_tokens()
    futures_map = get_active_futures_symbols()
    target_symbols = [futures_map[t] for t in alpha_tokens if t in futures_map]

    if not target_symbols:
        print("Không tìm thấy cặp Futures nào thuộc hệ Alpha.")
        return

    print(f"Đang quét {len(target_symbols)} cặp Alpha Futures khung 5m...")

    results = []
    with ThreadPoolExecutor(max_workers=12) as executor:
        futures_data = executor.map(check_oi_change, target_symbols)
        for item in futures_data:
            # Lọc mức biến động > 0.001% (Lấy theo trị tuyệt đối)
            if item and item["abs_change_pct"] > MIN_OI_CHANGE:
                results.append(item)

    # Sắp xếp lấy Top 3 biến động cao nhất
    results.sort(key=lambda x: x["abs_change_pct"], reverse=True)
    top_3 = results[:3]

    for c in top_3:
        print(c)

    send_discord_notification(top_3)

if __name__ == "__main__":
    main()
