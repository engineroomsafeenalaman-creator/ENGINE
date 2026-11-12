import concurrent.futures
import os
import threading
import time
from flask import Flask
import requests

# Dán link Webhook Discord của bạn vào giữa 2 dấu ngoặc kép bên dưới
WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"

NGUONG_TY_LE_OI = 1.12
TEN_SAN = "binance" + ".com"
DOMAIN_WEB = "https://www." + TEN_SAN
DOMAIN_FAPI = "https://fapi." + TEN_SAN
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Danh sách dự phòng các coin tag Alpha phổ biến trên Futures (phòng khi API lấy danh sách bị chặn)
DANH_SACH_DU_PHONG = [
    "AIXBTUSDT",
    "ZKJUSDT",
    "ARCUSDT",
    "GRIFFAINUSDT",
    "SWARMSUSDT",
    "ALCHUSDT",
    "FARTCOINUSDT",
    "PENGUUSDT",
    "VIRTUALUSDT",
    "VANAUSDT",
    "VELODROMEUSDT",
    "MOVEUSDT",
    "MEUSDT",
    "MORPHOUSDT",
    "CHILLGUYUSDT",
    "THEUSDT",
    "ACTUSDT",
    "PNUTUSDT",
    "HIPPOUSDT",
    "DEGENUSDT",
    "BANUSDT",
    "SLERFUSDT",
    "SCRTUSDT",
    "1000000MOGUSDT",
    "CETUSUSDT",
    "COWUSDT",
    "DRIFTUSDT",
    "GRASSUSDT",
    "GOATUSDT",
    "MOODENGUSDT",
    "DIAUSDT",
    "EIGENUSDT",
    "HMSTRUSDT",
    "CATIUSDT",
    "NEIROUSDT",
    "1MBABYDOGEUSDT",
    "POLUSDT",
    "FLUXUSDT",
    "POPCATUSDT",
    "SUNUSDT",
    "VIDTUSDT",
    "NULSUSDT",
    "DOGSUSDT",
    "ALPACAUSDT",
    "VOXELUSDT",
    "BRETTUSDT",
    "BIOUSDT",
    "COOKIEUSDT",
    "CGPTUSDT",
    "SOLVUSDT",
    "TRUMPUSDT",
    "MELANIAUSDT",
    "ANIMEUSDT",
    "VINEUSDT",
    "PIPPINUSDT",
    "VVVUSDT",
    "BERAUSDT",
    "TSTUSDT",
    "LAYERUSDT",
    "HEIUSDT",
    "B3USDT",
    "IPUSDT",
    "GPSUSDT",
    "SHELLUSDT",
    "KAITOUSDT",
    "REDUSDT",
    "VICUSDT",
    "EPICUSDT",
    "BMTUSDT",
    "MUBARAKUSDT",
    "FORMUSDT",
    "TUTUSDT",
    "BROCCOLI714USDT",
    "BANANAS31USDT",
    "SIRENUSDT",
    "PLUMEUSDT",
    "NILUSDT",
    "PARTIUSDT",
    "JELLYJELLYUSDT",
    "MAVIAUSDT",
    "WALUSDT",
    "FUNUSDT",
    "MLNUSDT",
    "GUNUSDT",
    "ATHUSDT",
    "BABYUSDT",
    "FORTHUSDT",
    "PROMPTUSDT",
    "XCNUSDT",
    "STOUSDT",
    "FHEUSDT",
    "KERNELUSDT",
    "WCTUSDT",
    "INITUSDT",
    "AERGOUSDT",
    "BANKUSDT",
    "EPTUSDT",
    "DEEPUSDT",
    "HYPERUSDT",
    "MEMEFIUSDT",
    "FISUSDT",
    "JSTUSDT",
    "SIGNUSDT",
    "PUNDIXUSDT",
    "CTKUSDT",
    "AIOTUSDT",
    "DOLOUSDT",
    "HAEDALUSDT",
    "SXTUSDT",
    "ASRUSDT",
    "ALPINEUSDT",
    "B2USDT",
    "MILKUSDT",
    "SYRUPUSDT",
    "OBOLUSDT",
    "DOODUSDT",
    "OGUSDT",
    "ZKJUSDT",
    "SKYAIUSDT",
    "NXPCUSDT",
    "CVCUSDT",
    "AGTUSDT",
    "AWEUSDT",
    "BUSDT",
    "SOONUSDT",
    "HUMAUSDT",
    "AUSDT",
    "SOPHUSDT",
    "MERLUSDT",
    "HYPEUSDT",
    "BDXNUSDT",
    "PUFFERUSDT",
    "PORT3USDT",
    "SKATEUSDT",
    "LAUSDT",
    "HOMEUSDT",
    "RESOLVUSDT",
    "TAIKOUSDT",
    "SQDUSDT",
    "PUMPBTCUSDT",
    "SPKUSDT",
    "MYXUSDT",
    "FUSDT",
    "NEWTUSDT",
    "DMCUSDT",
    "HUSDT",
    "OLUSDT",
    "SAHARAUSDT",
    "ICNTUSDT",
    "BULLAUSDT",
    "IDOLUSDT",
    "MUSDT",
    "TANSSIUSDT",
    "PUMPUSDT",
    "CROSSUSDT",
    "AINUSDT",
    "CUSDT",
    "VELVETUSDT",
    "TACUSDT",
    "ERAUSDT",
    "TAUSDT",
    "CVXUSDT",
    "SLPUSDT",
    "ZORAUSDT",
    "TAGUSDT",
    "ZRCUSDT",
    "ESPORTSUSDT",
    "TREEUSDT",
    "A2ZUSDT",
    "PLAYUSDT",
    "NAORISUSDT",
    "TOWNSUSDT",
    "PROVEUSDT",
    "ALLUSDT",
    "INUSDT",
    "CARVUSDT",
    "AIOUSDT",
    "XNYUSDT",
    "USELESSUSDT",
    "DAMUSDT",
    "CUDISUSDT",
    "SAPIENUSDT",
    "XPLUSDT",
    "WLFIUSDT",
    "SOMIUSDT",
    "BASUSDT",
    "BTRUSDT",
    "MITOUSDT",
    "HEMIUSDT",
    "LINEAUSDT",
    "QUSDT",
    "ARIAUSDT",
    "TAKEUSDT",
    "PTBUSDT",
    "OPENUSDT",
    "FLOCKUSDT",
    "SKYUSDT",
    "AVNTUSDT",
    "HOLOUSDT",
    "XPINUSDT",
    "UBUSDT",
    "ZKCUSDT",
    "TOSHIUSDT",
    "STBLUSDT",
    "0GUSDT",
    "AIAUSDT",
    "BARDUSDT",
    "ASTERUSDT",
    "TRADOORUSDT",
    "BLESSUSDT",
    "FLUIDUSDT",
    "COAIUSDT",
    "HANAUSDT",
    "MIRAUSDT",
    "AKEUSDT",
    "ORDERUSDT",
    "LIGHTUSDT",
    "XANUSDT",
    "FFUSDT",
    "VFYUSDT",
    "EDENUSDT",
    "NOMUSDT",
    "TRUTHUSDT",
    "2ZUSDT",
    "EVAAUSDT",
    "LYNUSDT",
    "KGENUSDT",
    "4USDT",
    "GIGGLEUSDT",
    "MONUSDT",
    "YBUSDT",
    "LABUSDT",
    "CLOUSDT",
    "RECALLUSDT",
    "ENSOUSDT",
    "EULUSDT",
    "FLKUSDT",
    "RVVUSDT",
    "ZBTUSDT",
    "RIVERUSDT",
    "BLUAIUSDT",
    "TURTLEUSDT",
    "APRUSDT",
    "ONUSDT",
    "ATUSDT",
    "COMMONUSDT",
    "PIEVERSEUSDT",
    "42USDT",
    "PIGGYUSDT",
    "KITEUSDT",
    "CCUSDT",
    "BOSUSDT",
    "MMTUSDT",
    "TRUSTUSDT",
    "UAIUSDT",
    "FOLKSUSDT",
    "STABLEUSDT",
    "JCTUSDT",
    "ALLOUSDT",
    "CLANKERUSDT",
    "BEATUSDT",
    "SENTUSDT",
    "CROSSUSDT",
    "PLAYSOLANAUSDT",
    "METUSDT",
    "BANKUSDT",
    "BOBUSDT",
]

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

    # Thử lấy danh sách từ Futures API
    res_prices = requests.get(
        DOMAIN_FAPI + "/fapi/v1/ticker/price", headers=HEADERS, timeout=10
    ).json()
    if isinstance(res_prices, list) and len(res_prices) > 0:
      danh_sach = [
          item["symbol"]
          for item in res_prices
          if item.get("symbol", "").endswith("USDT")
          and item["symbol"][:-4] in alpha_symbols
      ]
      if danh_sach:
        return danh_sach
  except Exception as e:
    print(f"Chuyển sang dùng danh sách dự phòng do: {e}", flush=True)

  # Nếu API bị chặn tạm thời thì dùng ngay danh sách cố định hơn 220 coin Alpha ở trên
  return list(set(DANH_SACH_DU_PHONG))


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
  with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
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

  oi_phut_truoc = quet_toan_bo_oi(danh_sach_alpha)
  print(
      f"Lần quét đầu tiên lấy được OI của {len(oi_phut_truoc)} coin.", flush=True
  )
  coin_dang_theo_doi_giam = set()

  while True:
    time.sleep(30)
    oi_hien_tai = quet_toan_bo_oi(danh_sach_alpha)

    if not oi_hien_tai:
      print("⚠️ IP dùng chung trên Render đang tạm giới hạn, đợi chu kỳ sau...", flush=True)
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
