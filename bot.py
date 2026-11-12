import os
import time
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from concurrent.futures import ThreadPoolExecutor

# Cấu hình biến môi trường (Lấy tự động từ GitHub Secrets)
DISCORD_WEBHOOK_URL = os.environ.get("https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN")
TIMEFRAME = "5m"          # Khung thời gian 5 phút
MIN_OI_CHANGE = 0.001     # Ngưỡng biến động tối thiểu (%)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def create_session():
    """Tạo session có cơ chế tự động thử lại nếu API phản hồi chậm hoặc lỗi tạm thời"""
    session = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504]
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.headers.update(HEADERS)
    return session

session = create_session()

def get_binance_alpha_tokens():
    """Lấy danh sách toàn bộ token thuộc hệ Binance Alpha"""
    url = "https://binance.com"
    try:
        res = session.get(url, timeout=15)
        res.raise_for_status()
        data = res.json()
        tokens = data.get("data", [])
        return {t.get("symbol", "").strip().upper() for t in tokens if t.get("symbol")}
    except Exception as e:
        print(f"[Lỗi] Không lấy được danh sách Binance Alpha: {e}")
        return set()

def get_active_futures_symbols():
    """Lấy danh sách các cặp USDT Futures đang mở giao dịch"""
    url = "https://binance.com"
    try:
        res = session.get(url, timeout=15)
        res.raise_for_status()
        data = res.json()
        futures_map = {}
        for s in data.get("symbols", []):
            if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT":
                base = s.get("baseAsset", "").upper()
                symbol = s.get("symbol")
                # Xử lý các mã có tiền tố 1000 (VD: 1000PEPE -> PEPE)
                clean_base = base[4:] if base.startswith("1000") else base
                futures_map[clean_base] = symbol
        return futures_map
    except Exception as e:
        print(f"[Lỗi] Không lấy được danh sách Futures: {e}")
        return {}

def check_oi_change(symbol):
    """Lấy dữ liệu Open Interest 2 nến 5m gần nhất và tính % biến động"""
    url = "https://binance.com"
    params = {
        "symbol": symbol,
        "period": TIMEFRAME,
        "limit": 2
    }
    try:
        res = session.get(url, params=params, timeout=10)
        if res.status_code != 200:
            return None
        data = res.json()
        if isinstance(data, list) and len(data) == 2:
            prev_oi = float(data[0]["sumOpenInterestValue"])
            curr_oi = float(data[1]["sumOpenInterestValue"])
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
    """Gửi bảng xếp hạng Top 3 về kênh Discord"""
    if not DISCORD_WEBHOOK_URL:
        print("[Cảnh báo] Chưa cài đặt biến DISCORD_WEBHOOK_URL trong GitHub Secrets!")
        return

    if not top_coins:
        print("[Thông báo] Không có đồng Alpha nào biến động OI > 0.001% trong 5 phút vừa qua.")
        return

    fields = []
    for idx, coin in enumerate(top_coins, start=1):
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

    try:
        res = session.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        if res.status_code in (200, 204):
            print("[Thành công] Đã bắn thông báo về Discord!")
        else:
            print(f"[Lỗi] Discord từ chối nhận tin: {res.status_code} - {res.text}")
    except Exception as e:
        print(f"[Lỗi] Không thể kết nối tới Discord: {e}")

def main():
    start_time = time.time()
    print("1. Đang tải danh sách token Binance Alpha...")
    alpha_tokens = get_binance_alpha_tokens()
    if not alpha_tokens:
        return

    print("2. Đang đối chiếu với thị trường Binance Futures...")
    futures_map = get_active_futures_symbols()
    target_symbols = [futures_map[t] for t in alpha_tokens if t in futures_map]
    print(f"-> Tìm thấy {len(target_symbols)} cặp Alpha đang mở Futures.")

    if not target_symbols:
        return

    print("3. Đang quét dữ liệu OI khung 5 phút...")
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures_data = executor.map(check_oi_change, target_symbols)
        for item in futures_data:
            if item and item["abs_change_pct"] > MIN_OI_CHANGE:
                results.append(item)

    # Sắp xếp giảm dần theo mức độ biến động và lấy Top 3
    results.sort(key=lambda x: x["abs_change_pct"], reverse=True)
    top_3 = results[:3]

    for c in top_3:
        print(f"Top: {c['symbol']} | Biến động: {c['oi_change_pct']:.4f}% | OI: ${c['current_oi_usd']:,.2f}")

    send_discord_notification(top_3)
    print(f"Hoàn tất chu kỳ quét trong {time.time() - start_time:.2f} giây.")

if __name__ == "__main__":
    main()
name: Scan Binance Alpha OI 5m

on:
  schedule:
    # Tự động chạy mỗi 5 phút một lần
    - cron: '*/5 * * * *'
  workflow_dispatch:

jobs:
  run-script:
    runs-on: ubuntu-latest

    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: pip install requests

      - name: Run Alpha OI 5m Scanner
        env:
          DISCORD_WEBHOOK_URL: ${{ secrets.DISCORD_WEBHOOK_URL }}
        run: python main.py
