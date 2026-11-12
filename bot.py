import concurrent.futures
import json
import os
import threading
import time
from flask import Flask
import requests
import websocket

# Dán link Webhook Discord của bạn vào giữa 2 dấu ngoặc kép bên dưới
WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"

NGUONG_TY_LE_OI = 1.00005
DOMAIN_WEB = "https://www." + "binance.com"
DOMAIN_FAPI = "https://fapi." + "binance.com"
WS_FAPI = "wss://fstream." + "://binance.com"
HEADERS = {"User-Agent": "Mozilla/5.0"}

app = Flask(__name__)


@app.route("/")
def home():
  return "Bot canh OI dang chay!"


def gui_discord(noi_dung):
  try:
    res = requests.post(WEBHOOK_URL, json={"content": noi_dung}, timeout=10)
    print(f"Gửi Discord status: {res.status_code}", flush=True)
  except Exception as e:
    print(f"Lỗi gửi Discord: {e}", flush=True)


def lay_danh_sach_coin_alpha_futures():
  try:
    # 1. Lấy 663 token Alpha từ cổng web
    path_alpha = (
        "/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"
    )
    res_alpha = requests.get(
        DOMAIN_WEB + path_alpha, headers=HEADERS, timeout=15
    ).json()

    alpha_symbols = {
        item.get("symbol", "").upper()
        for item in res_alpha.get("data", [])
        if item.get("symbol")
    }
    print(f"Lấy được {len(alpha_symbols)} token Alpha", flush=True)

    # 2. Hứng 1 nhịp WebSocket trực tiếp từ Futures (0% bị chặn IP) để lấy toàn bộ mã coin
    ws = websocket.create_connection(WS_FAPI, timeout=15)
    raw_msg = ws.recv()
    ws.close()

    tickers = json.loads(raw_msg)
    danh_sach = []
    for item in tickers:
      sym = item.get("s", "")  # Mã cặp giao dịch, ví dụ: AIXBTUSDT
      if sym.endswith("USDT") and sym[:-4] in alpha_symbols:
        danh_sach.append(sym)

    return danh_sach
  except Exception as e:
    print(f"Lỗi lấy danh sách qua WebSocket: {e}", flush=True)
    return []


def lay_oi_1_coin(symbol):
  url = DOMAIN_FAPI + f"/fapi/v1/openInterest?symbol={symbol}"
  try:
    res = requests.get(url, headers=HEADERS, timeout=5)
    if res.status_code == 200:
      data = res.json()
      return symbol, float(data["openInterest"])
    return symbol, None
  except Exception:
    return symbol, None


def quet_toan_bo_oi(danh_sach_coin):
  ket_qua = {}
  with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
    futures = [executor.submit(lay_oi_1_coin, sym) for sym in danh_sach_coin]
    for f in concurrent.futures.as_completed(futures):
      sym, oi = f.result()
      if oi is not None and oi > 0:
        ket_qua[sym] = oi
  return ket_qua


def chay_bot_canh_oi():
  print("Bắt đầu khởi động luồng quét OI...", flush=True)
  danh_sach_alpha = lay_danh_sach_coin_alpha_futures()
  print(f"✅ Đã sẵn sàng quét {len(danh_sach_alpha)} coin Alpha...", flush=True)

  gui_discord(
      f"✅ Bot đã kết nối và đang quét **{len(danh_sach_alpha)}** coin Alpha!"
  )

  if not danh_sach_alpha:
    return

  oi_phut_truoc = quet_toan_bo_oi(danh_sach_alpha)
  coin_dang_theo_doi_giam = set()

  while True:
    time.sleep(60)
    oi_hien_tai = quet_toan_bo_oi(danh_sach_alpha)

    if not oi_hien_tai:
      print("⚠️ IP dùng chung đang tạm bận, đợi chu kỳ sau...", flush=True)
      continue

    coin_tang = []
    coin_giam = []

    for sym, oi_moi in oi_hien_tai.items():
      oi_cu = oi_phut_truoc.get(sym)
      if not oi_cu or oi_cu == 0:
        continue

      if (oi_moi / oi_cu) >= NGUONG_TY_LE_OI:
        coin_dang_theo_doi_giam.add(sym)
        coin_tang.append(sym)
      elif sym in coin_dang_theo_doi_giam and oi_moi < oi_cu:
        coin_giam.append(sym)
        coin_dang_theo_doi_giam.remove(sym)

    dong_bao = []
    if coin_tang:
      dong_bao.append("🟢 **OI TĂNG:** " + ", ".join(coin_tang))
    if coin_giam:
      dong_bao.append("🔴 **OI GIẢM:** " + ", ".join(coin_giam))

    if dong_bao:
      gui_discord("@everyone\n" + "\n".join(dong_bao))

    oi_phut_truoc = oi_hien_tai


if __name__ == "__main__":
  threading.Thread(target=chay_bot_canh_oi, daemon=True).start()
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)
