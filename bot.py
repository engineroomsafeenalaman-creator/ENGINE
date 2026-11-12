import requests
import time
from concurrent.futures import ThreadPoolExecutor

# Cấu hình Webhook từ dữ liệu của bạn
WEBHOOK_CONFIG = {
    "id": "1570320464172285962",
    "name": "ENGINE 3",
    "token": "PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN",
    "url": "https://discord.com"
}

# Ngưỡng lọc biến động OI tối thiểu trong 1 phút (%)
MIN_OI_CHANGE_PCT = 0.01

# Lấy danh sách Top 50 cặp USDT có Volume lớn nhất để quét OI nhanh và không bị lỗi Rate Limit
def get_top_liquid_symbols(limit=50):
    url = "https://binance.com"
    res = requests.get(url, timeout=10).json()
    usdt_pairs = [
        x for x in res 
        if x['symbol'].endswith('USDT') and '_' not in x['symbol']
    ]
    sorted_pairs = sorted(usdt_pairs, key=lambda x: float(x['quoteVolume']), reverse=True)
    return [x['symbol'] for x in sorted_pairs[:limit]]

# Lấy Open Interest (OI) hiện tại của 1 cặp coin
def fetch_oi(symbol):
    url = f"https://binance.com{symbol}"
    try:
        res = requests.get(url, timeout=5).json()
        return symbol, float(res['openInterest'])
    except Exception:
        return symbol, None

# Quét đa luồng toàn bộ danh sách coin trong 1-2 giây
def get_all_oi(symbols):
    oi_map = {}
    with ThreadPoolExecutor(max_workers=15) as executor:
        results = executor.map(fetch_oi, symbols)
        for symbol, oi in results:
            if oi is not None:
                oi_map[symbol] = oi
    return oi_map

# Gửi kết quả lên Discord
def send_discord_alert(top_3):
    message = f"**⚡ TOP COIN BIẾN ĐỘNG OI 1 PHÚT (>= {MIN_OI_CHANGE_PCT}%):**\n\n"
    for idx, item in enumerate(top_3, start=1):
        symbol = item['symbol']
        oi_change = item['oi_change_pct']
        oi_now = item['oi_now']
        icon = "🟢" if oi_change >= 0 else "🔴"
        
        message += f"**{idx}. {symbol}** {icon}\n"
        message += f"• Biến động OI (1m): `{oi_change:+.4f}%`\n"
        message += f"• Tổng OI hiện tại: `{oi_now:,.0f} {symbol.replace('USDT', '')}`\n\n"

    payload = {
        "username": WEBHOOK_CONFIG["name"],
        "content": message
    }
    requests.post(WEBHOOK_CONFIG["url"], json=payload)

# --- CHƯƠNG TRÌNH CHÍNH ---
if __name__ == "__main__":
    print(f"Đang khởi động bot quét OI 1 phút (Ngưỡng lọc >= {MIN_OI_CHANGE_PCT}%)...")
    symbols = get_top_liquid_symbols(limit=50)
    
    # Lấy mốc OI ban đầu
    previous_oi = get_all_oi(symbols)
    print(f"Đã ghi nhận mốc OI ban đầu cho {len(previous_oi)} cặp coin. Đợi 60 giây...")

    while True:
        time.sleep(60) # Chờ đúng 1 phút
        current_oi = get_all_oi(symbols)
        
        changes = []
        for sym, oi_now in current_oi.items():
            oi_prev = previous_oi.get(sym)
            if oi_prev and oi_prev > 0:
                pct_change = ((oi_now - oi_prev) / oi_prev) * 100
                
                # Chỉ lấy các coin có mức tăng OI >= 0.01%
                if pct_change >= MIN_OI_CHANGE_PCT:
                    changes.append({
                        "symbol": sym,
                        "oi_change_pct": pct_change,
                        "oi_now": oi_now
                    })
        
        # Sắp xếp giảm dần và lấy tối đa Top 3 coin đạt ngưỡng
        top_3 = sorted(changes, key=lambda x: x['oi_change_pct'], reverse=True)[:3]
        
        if top_3:
            send_discord_alert(top_3)
            print(f"Đã gửi {len(top_3)} coin đạt ngưỡng OI >= {MIN_OI_CHANGE_PCT}% lên Discord!")
        else:
            print(f"Phút vừa qua không có coin nào đạt ngưỡng >= {MIN_OI_CHANGE_PCT}%.")
            
        # Cập nhật mốc OI mới cho chu kỳ 1 phút tiếp theo
        previous_oi = current_oi
