import os
import time
import requests
from concurrent.futures import ThreadPoolExecutor

# Cấu hình biến môi trường (Lấy từ GitHub Secrets)
DISCORD_WEBHOOK_URL = os.environ.get("https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN")
TIMEFRAME = "5m"          # Khung thời gian 5 phút
MIN_OI_CHANGE = 0.001     # Ngưỡng biến động tối thiểu (%)

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

def send_discord_raw(payload):
    """Hàm gửi dữ liệu trực tiếp tới Discord Webhook"""
    if not DISCORD_WEBHOOK_URL:
        print("[LỖI NGHIÊM TRỌNG] Chưa tìm thấy DISCORD_WEBHOOK_URL trong GitHub Secrets!")
        return
    try:
        res = requests.post(DISCORD_WEBHOOK_URL.strip(), json=payload, timeout=15)
        print(f"[Discord Status] Mã phản hồi: {res.status_code}")
        if res.status_code not in (200, 204):
            print(f"[Discord Error] Nội dung lỗi: {res.text}")
    except Exception as e:
        print(f"[Discord Exception] Lỗi kết nối Discord: {e}")

def get_working_fapi_base():
    """Kiểm tra server Binance Futures nào cho phép truy cập từ IP hiện tại"""
    for base_url in FAPI_ENDPOINTS:
        try:
            res = requests.get(f"{base_url}/fapi/v1/exchangeInfo", headers=HEADERS, timeout=8)
            if res.status_code == 200:
                print(f"[OK] Kết nối thành công tới: {base_url}")
                return base_url, res.json()
            else:
                print(f"[Bị chặn] {base_url} trả về mã: {res.status_code}")
        except Exception as e:
            print(f"[Lỗi mạng] {base_url}: {e}")
    return None, None

def get_binance_alpha_tokens():
    """Lấy danh sách token thuộc hệ Binance Alpha"""
    url = "https://binance.com"
    try:
        res = requests.get(url, headers=HEADERS, timeout=15)
        if res.status_code == 200:
            tokens = res.json().get("data", [])
            alpha_set = {t.get("symbol", "").strip().upper() for t in tokens if t.get("symbol")}
            print(f"[OK] Lấy được {len(alpha_set)} token từ danh sách Binance Alpha.")
            return alpha_set
        else:
            print(f"[Lỗi Alpha API] Mã trạng thái: {res.status_code}")
    except Exception as e:
        print(f"[Lỗi Alpha API] {e}")
    return set()

def check_oi_change(args):
    """Lấy dữ liệu Open Interest 2 nến 5m gần nhất và tính % biến động"""
    symbol, fapi_base = args
    url = f"{fapi_base}/futures/data/openInterestHist"
    params = {
        "symbol": symbol,
        "period": TIMEFRAME,
        "limit": 2
    }
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

def main():
    print("=== BẮT ĐẦU CHU KỲ QUÉT BINANCE ALPHA OI ===")
    
    # 1. Kiểm tra kết nối Binance Futures
    fapi_base, exchange_data = get_working_fapi_base()
    if not fapi_base or not exchange_data:
        msg = "⚠️ **Lỗi kết nối Binance Futures:** Máy chủ GitHub (IP Mỹ) đang bị Binance chặn (Lỗi 451). Cần chạy qua VPS châu Á hoặc Proxy."
        print(msg)
        send_discord_raw({"content": msg})
        return

    # 2. Lấy danh sách Binance Alpha
    alpha_tokens = get_binance_alpha_tokens()
    if not alpha_tokens:
        msg = "⚠️ **Lỗi kết nối Binance Alpha:** Không tải được danh sách token Alpha."
        print(msg)
        send_discord_raw({"content": msg})
        return

    # 3. Đối chiếu các cặp USDT Futures
    futures_map = {}
    for s in exchange_data.get("symbols", []):
        if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT":
            base = s.get("baseAsset", "").upper()
            symbol = s.get("symbol")
            clean_base = base[4:] if base.startswith("1000") else base
            futures_map[clean_base] = symbol

    target_symbols = [(futures_map[t], fapi_base) for t in alpha_tokens if t in futures_map]
    print(f"[OK] Có {len(target_symbols)} cặp Alpha đang giao dịch Futures.")

    # 4. Quét OI khung 5 phút
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures_data = executor.map(check_oi_change, target_symbols)
        for item in futures_data:
            if item and item["abs_change_pct"] > MIN_OI_CHANGE:
                results.append(item)

    results.sort(key=lambda x: x["abs_change_pct"], reverse=True)
    top_3 = results[:3]

    if not top_3:
        print("[Kết quả] Không có đồng Alpha nào biến động OI > 0.001% trong 5 phút qua.")
        send_discord_raw({
            "content": f"ℹ️ **Radar 5m:** Đã quét {len(target_symbols)} cặp Alpha nhưng chưa có đồng nào biến động OI trên `{MIN_OI_CHANGE}%`."
        })
        return

    # 5. Đóng gói tin nhắn Top 3 gửi Discord
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
        "embeds": [
            {
                "title": "⚡ TOP 3 BINANCE ALPHA BIẾN ĐỘNG OI MẠNH NHẤT (5M)",
                "description": f"Các đồng coin thuộc danh mục **Binance Alpha** có biến động Open Interest trên `{MIN_OI_CHANGE}%`.",
                "color": 16766720,
                "fields": fields,
                "footer": {
                    "text": "Dữ liệu tự động từ Binance Futures & Alpha"
                }
            }
        ]
    }
    send_discord_raw(payload)

if __name__ == "__main__":
    main()
