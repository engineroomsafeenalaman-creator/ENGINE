import concurrent.futures
import os
import socket
import threading
import time
from flask import Flask
import requests

# ==========================================
# 1. CẤU HÌNH BOT
# ==========================================
WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"

NGUONG_TY_LE_OI = 1.00001  # 1.00001 = 0.001% | 1.005 = 0.5% | 1.01 = 1%
CHU_KY_QUET_GIAY = 30  # Thời gian nghỉ giữa các lần quét (giây)
SO_COIN_TOI_DA = 10  # Lấy Top 10 coin tăng mạnh nhất

TEN_SAN = "binance" + ".com"
DOMAIN_WEB = "https://www." + TEN_SAN
DOMAIN_FAPI = "https://fapi." + TEN_SAN
HEADERS = {"User-Agent": "Mozilla/5.0"}

DANH_SACH_DU_PHONG = sorted(
    list(
        set([
            "AIXBTUSDT", "ZKJUSDT", "ARCUSDT", "GRIFFAINUSDT", "SWARMSUSDT",
            "ALCHUSDT", "FARTCOINUSDT", "PENGUUSDT", "VIRTUALUSDT", "VANAUSDT",
            "VELODROMEUSDT", "MOVEUSDT", "MEUSDT", "MORPHOUSDT", "CHILLGUYUSDT",
            "THEUSDT", "ACTUSDT", "PNUTUSDT", "HIPPOUSDT", "DEGENUSDT",
            "BANUSDT", "SLERFUSDT", "SCRTUSDT", "1000000MOGUSDT", "CETUSUSDT",
            "COWUSDT", "DRIFTUSDT", "GRASSUSDT", "GOATUSDT", "MOODENGUSDT",
            "DIAUSDT", "EIGENUSDT", "HMSTRUSDT", "CATIUSDT", "NEIROUSDT",
            "1MBABYDOGEUSDT", "POLUSDT", "FLUXUSDT", "POPCATUSDT", "SUNUSDT",
            "VIDTUSDT", "NULSUSDT", "DOGSUSDT", "ALPACAUSDT", "VOXELUSDT",
            "BRETTUSDT", "BIOUSDT", "COOKIEUSDT", "CGPTUSDT", "SOLVUSDT",
            "TRUMPUSDT", "MELANIAUSDT", "ANIMEUSDT", "VINEUSDT", "PIPPINUSDT",
            "VVVUSDT", "BERAUSDT", "TSTUSDT", "LAYERUSDT", "HEIUSDT",
            "B3USDT", "IPUSDT", "GPSUSDT", "SHELLUSDT", "KAITOUSDT",
            "REDUSDT", "VICUSDT", "EPICUSDT", "BMTUSDT", "MUBARAKUSDT",
            "FORMUSDT", "TUTUSDT", "BROCCOLI714USDT", "BANANAS31USDT", "SIRENUSDT",
            "PLUMEUSDT", "NILUSDT", "PARTIUSDT", "JELLYJELLYUSDT", "MAVIAUSDT",
            "WALUSDT", "FUNUSDT", "MLNUSDT", "GUNUSDT", "ATHUSDT",
            "BABYUSDT", "FORTHUSDT", "PROMPTUSDT", "XCNUSDT", "STOUSDT",
            "FHEUSDT", "KERNELUSDT", "WCTUSDT", "INITUSDT", "AERGOUSDT",
            "BANKUSDT", "EPTUSDT", "DEEPUSDT", "HYPERUSDT", "MEMEFIUSDT",
            "FISUSDT", "JSTUSDT", "SIGNUSDT", "PUNDIXUSDT", "CTKUSDT",
            "AIOTUSDT", "DOLOUSDT", "HAEDALUSDT", "SXTUSDT", "ASRUSDT",
            "ALPINEUSDT", "B2USDT", "MILKUSDT", "SYRUPUSDT", "OBOLUSDT",
            "DOODUSDT", "OGUSDT", "SKYAIUSDT", "NXPCUSDT", "CVCUSDT",
            "AGTUSDT", "AWEUSDT", "BUSDT", "SOONUSDT", "HUMAUSDT",
            "AUSDT", "SOPHUSDT", "MERLUSDT", "HYPEUSDT", "BDXNUSDT",
            "PUFFERUSDT", "PORT3USDT", "SKATEUSDT", "LAUSDT", "HOMEUSDT",
            "RESOLVUSDT", "TAIKOUSDT", "SQDUSDT", "PUMPBTCUSDT", "SPKUSDT",
            "MYXUSDT", "FUSDT", "NEWTUSDT", "DMCUSDT", "HUSDT",
            "OLUSDT", "SAHARAUSDT", "ICNTUSDT", "BULLAUSDT", "IDOLUSDT",
            "MUSDT", "TANSSIUSDT", "PUMPUSDT", "CROSSUSDT", "AINUSDT",
            "CUSDT", "VELVETUSDT", "TACUSDT", "ERAUSDT", "TAUSDT",
            "CVXUSDT", "SLPUSDT", "ZORAUSDT", "TAGUSDT", "ZRCUSDT",
            "ESPORTSUSDT", "TREEUSDT", "A2ZUSDT", "PLAYUSDT", "NAORISUSDT",
            "TOWNSUSDT", "PROVEUSDT", "ALLUSDT", "INUSDT", "CARVUSDT",
            "AIOUSDT", "XNYUSDT", "USELESSUSDT", "DAMUSDT", "CUDISUSDT",
            "SAPIENUSDT", "XPLUSDT", "WLFIUSDT", "SOMIUSDT", "BASUSDT",
            "BTRUSDT", "MITOUSDT", "HEMIUSDT", "LINEAUSDT", "QUSDT",
            "ARIAUSDT", "TAKEUSDT", "PTBUSDT", "OPENUSDT", "FLOCKUSDT",
            "SKYUSDT", "AVNTUSDT", "HOLOUSDT", "XPINUSDT", "UBUSDT",
            "ZKCUSDT", "TOSHIUSDT", "STBLUSDT", "0GUSDT", "AIAUSDT",
            "BARDUSDT", "ASTERUSDT", "TRADOORUSDT", "BLESSUSDT", "FLUIDUSDT",
            "COAIUSDT", "HANAUSDT", "MIRAUSDT", "AKEUSDT", "ORDERUSDT",
            "LIGHTUSDT", "XANUSDT", "FFUSDT", "VFYUSDT", "EDENUSDT",
            "NOMUSDT", "TRUTHUSDT", "2ZUSDT", "EVAAUSDT", "LYNUSDT",
            "KGENUSDT", "4USDT", "GIGGLEUSDT", "MONUSDT", "YBUSDT",
            "LABUSDT", "CLOUSDT", "RECALLUSDT", "ENSOUSDT", "EULUSDT",
            "FLKUSDT", "RVVUSDT", "ZBTUSDT", "RIVERUSDT", "BLUAIUSDT",
            "TURTLEUSDT", "APRUSDT", "ONUSDT", "ATUSDT", "COMMONUSDT",
            "PIEVERSEUSDT", "42USDT", "PIGGYUSDT", "KITEUSDT", "CCUSDT",
            "BOSUSDT", "MMTUSDT", "TRUSTUSDT", "UAIUSDT", "FOLKSUSDT",
            "STABLEUSDT", "JCTUSDT", "ALLOUSDT", "CLANKERUSDT", "BEATUSDT",
            "SENTUSDT", "PLAYSOLANAUSDT", "METUSDT", "BOBUSDT",
        ])
    )
)

app = Flask(__name__)


@app.route("/")
def home():
  return "Bot canh OI Alpha dang chay!"


def gui_discord(noi_dung):
  if not WEBHOOK_URL or "://discord.com" not in WEBHOOK_URL:
    return
  try:
    for i in range(0, len(noi_dung), 1900):
      doan_tin = noi_dung[i : i + 1900]
      requests.post(WEBHOOK_URL, json={"content": doan_tin}, timeout=10)
      time.sleep(0.5)
  except Exception as e:
    print(f"Loi gui Discord: {e}", flush=True)


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
    print(f"Dung danh sach du phong do loi API: {e}", flush=True)

  return DANH_SACH_DU_PHONG


def lay_oi_1_coin(symbol):
  url = DOMAIN_FAPI + f"/fapi/v1/openInterest?symbol={symbol}"
  try:
    # Nghỉ nhẹ 0.25s mỗi request để tránh vượt Rate Limit của Binance
    time.sleep(0.25)
    res = requests.get(url, headers=HEADERS, timeout=6)
    if res.status_code == 200:
      data = res.json()
      return symbol, float(data["openInterest"]), 200
    return symbol, None, res.status_code
  except Exception:
    return symbol, None, 0


def quet_toan_bo_oi(danh_sach_coin):
  ket_qua = {}
  ma_loi_gap = set()
  coin_loi_symbol = set()

  # Dùng 2 luồng + nghỉ 0.25s = ~8 request/giây (an toàn tuyệt đối với Binance)
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
    futures = [executor.submit(lay_oi_1_coin, sym) for sym in danh_sach_coin]
    for f in concurrent.futures.as_completed(futures):
      sym, oi, status = f.result()
      if status == 200 and oi is not None and oi > 0:
        ket_qua[sym] = oi
      elif status == 400:
        # Coin không tồn tại hoặc đã hủy niêm yết trên Futures
        coin_loi_symbol.add(sym)
      elif status != 200:
        ma_loi_gap.add(status)

  return ket_qua, ma_loi_gap, coin_loi_symbol


def chay_bot_canh_oi():
  print("Dang khoi dong Bot canh OI...", flush=True)
  danh_sach_alpha = lay_danh_sach_coin_alpha_futures()

  oi_phut_truoc, ma_loi, coin_loi = quet_toan_bo_oi(danh_sach_alpha)

  # Tự động loại bỏ các coin đã bị hủy niêm yết để lần sau quét nhanh hơn
  if coin_loi:
    danh_sach_alpha = [c for c in danh_sach_alpha if c not in coin_loi]

  if not oi_phut_truoc:
    gui_discord(
        f"⚠️ **Canh bao:** Bot da bat nhung KHONG lay duoc du lieu Binance (Ma"
        f" loi: {ma_loi})."
    )
  else:
    nguong_pt = (NGUONG_TY_LE_OI - 1) * 100
    gui_discord(
        f"✅ **Bot da ket noi!** Quet"
        f" **{len(oi_phut_truoc)}/{len(danh_sach_alpha)}** coin hop le | Chu"
        f" ky **{CHU_KY_QUET_GIAY}s** | Nguong **+{nguong_pt:.4f}%**"
    )

  da_bao_loi = False

  while True:
    time.sleep(CHU_KY_QUET_GIAY)
    oi_hien_tai, ma_loi, _ = quet_toan_bo_oi(danh_sach_alpha)

    if not oi_hien_tai:
      print(f"Khong lay duoc OI. Ma loi: {ma_loi}", flush=True)
      if not da_bao_loi:
        gui_discord(
            f"🚫 **Loi lay du lieu Binance** (Ma loi: `{ma_loi}`). Dang thu lai..."
        )
        da_bao_loi = True
      continue

    da_bao_loi = False

    if not oi_phut_truoc:
      oi_phut_truoc = oi_hien_tai
      continue

    danh_sach_tang = []
    for sym, oi_moi in oi_hien_tai.items():
      oi_cu = oi_phut_truoc.get(sym)
      if not oi_cu or oi_cu == 0:
        continue

      ty_le = oi_moi / oi_cu
      if ty_le >= NGUONG_TY_LE_OI:
        phan_tram = (ty_le - 1) * 100
        danh_sach_tang.append((phan_tram, sym))

    danh_sach_tang.sort(reverse=True)
    top_coin = danh_sach_tang[:SO_COIN_TOI_DA]

    if top_coin:
      noi_dung_bao = [f"**{sym}** (+{pt:.4f}%)" for pt, sym in top_coin]
      gui_discord(
          f"⏱️ **Top tang OI ({CHU_KY_QUET_GIAY}s)** (Tong {len(danh_sach_tang)}"
          " coin):\n"
          + ", ".join(noi_dung_bao)
      )

    oi_phut_truoc = oi_hien_tai


def khoi_dong_an_toan():
  try:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 47291))
    app.config["BOT_LOCK_SOCKET"] = s
    threading.Thread(target=chay_bot_canh_oi, daemon=True).start()
  except socket.error:
    pass


khoi_dong_an_toan()

if __name__ == "__main__":
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)
