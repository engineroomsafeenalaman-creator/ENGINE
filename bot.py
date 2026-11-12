from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import socket
import threading
import time
from flask import Flask
import requests

# ==========================================
# 1. CẤU HÌNH BOT
# ==========================================
WEBHOOK_URL = os.environ.get(
    "WEBHOOK_URL", "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"
)

NGUONG_TY_LE_OI = 1.0001  # 1.0001 = 0.01% (Mức test độ mượt)
CHU_KY_QUET_GIAY = 30  # Quét chuẩn mỗi 30 giây
SO_COIN_TOI_DA = 5  # In ra Top 5 coin tăng mạnh nhất
SO_LUONG_SONG_SONG = 15  # Số luồng quét song song an toàn cho chu kỳ 30s

# Danh sách 264 coin Alpha của bạn
DANH_SACH_ALPHA = {
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
}

app = Flask(__name__)

session = requests.Session()
adapter = requests.adapters.HTTPAdapter(
    pool_connections=SO_LUONG_SONG_SONG, pool_maxsize=SO_LUONG_SONG_SONG
)
session.mount("https://", adapter)
session.headers.update({"User-Agent": "Mozilla/5.0"})


@app.route("/")
def home():
  return "Bot canh OI Binance Futures (30s) dang chay!"


def gui_discord(noi_dung):
  if not WEBHOOK_URL or "://discord.com" not in WEBHOOK_URL:
    print(f"[CHUA CO WEBHOOK - CONSOLE]:\n{noi_dung}\n", flush=True)
    return

  try:
    for i in range(0, len(noi_dung), 1900):
      doan_tin = noi_dung[i : i + 1900]
      res = session.post(WEBHOOK_URL, json={"content": doan_tin}, timeout=10)
      if res.status_code == 429:
        retry_after = res.json().get("retry_after", 2)
        time.sleep(retry_after)
        session.post(WEBHOOK_URL, json={"content": doan_tin}, timeout=10)
      time.sleep(0.3)
  except Exception as e:
    print(f"Loi gui Discord: {e}", flush=True)


def lay_1_oi_binance(sym):
  """Lấy OI của 1 coin trên Binance Futures."""
  url = f"https://binance.com{sym}"
  try:
    res = session.get(url, timeout=5)
    if res.status_code == 200:
      data = res.json()
      return sym, float(data.get("openInterest", 0))
  except Exception:
    pass
  return sym, 0.0


def lay_toan_bo_du_lieu_binance(danh_sach_hop_le):
  """Lấy toàn bộ Giá (1 request) + OI (đa luồng siêu tốc) trên Binance Futures."""
  ket_qua = {}

  gia_map = {}
  try:
    res_gia = session.get(
        "https://binance.com", timeout=8
    )
    if res_gia.status_code == 200:
      for item in res_gia.json():
        sym = item.get("symbol", "")
        if sym in danh_sach_hop_le:
          gia_map[sym] = float(item.get("price", 0))
  except Exception as e:
    print(f"Loi lay gia Binance: {e}", flush=True)
    return ket_qua

  cac_ma_can_quet = list(gia_map.keys())
  with ThreadPoolExecutor(max_workers=SO_LUONG_SONG_SONG) as executor:
    futures = [executor.submit(lay_1_oi_binance, sym) for sym in cac_ma_can_quet]
    for future in as_completed(futures):
      sym, oi = future.result()
      gia = gia_map.get(sym, 0)
      if oi > 0 and gia > 0:
        ket_qua[sym] = {"oi": oi, "gia": gia, "oi_usd": oi * gia}

  return ket_qua


def chay_bot_canh_oi():
  print("Khoi dong bot quet Binance Futures (30s)...", flush=True)
  t0 = time.time()
  du_lieu_truoc = lay_toan_bo_du_lieu_binance(DANH_SACH_ALPHA)
  toc_do = time.time() - t0

  danh_sach_ton_tai = (
      set(du_lieu_truoc.keys()) if du_lieu_truoc else DANH_SACH_ALPHA
  )

  nguong_pt = (NGUONG_TY_LE_OI - 1) * 100
  gui_discord(
      f"✅ **Bot Binance Futures đã kết nối!**\n📊 Tìm thấy"
      f" **{len(du_lieu_truoc)}/{len(DANH_SACH_ALPHA)}** coin Alpha trên"
      f" Binance trong **{toc_do:.2f}s**\n⏱️ Chu kỳ: **{CHU_KY_QUET_GIAY}s** |"
      f" 🎯 Ngưỡng test: **+{nguong_pt:.3f}%**"
  )

  while True:
    # Tính thời gian ngủ bù trừ để luôn giữ chuẩn nhịp 30s
    thoi_gian_ngu = max(1.0, CHU_KY_QUET_GIAY - toc_do)
    time.sleep(thoi_gian_ngu)

    t_quet = time.time()
    du_lieu_moi = lay_toan_bo_du_lieu_binance(danh_sach_ton_tai)
    toc_do = time.time() - t_quet

    if not du_lieu_moi:
      continue

    if not du_lieu_truoc:
      du_lieu_truoc = du_lieu_moi
      continue

    danh_sach_tang = []
    for sym, info_moi in du_lieu_moi.items():
      info_cu = du_lieu_truoc.get(sym)
      if not info_cu or info_cu["oi"] == 0:
        continue

      ty_le_oi = info_moi["oi"] / info_cu["oi"]
      if ty_le_oi >= NGUONG_TY_LE_OI:
        pt_oi = (ty_le_oi - 1) * 100
        pt_gia = (
            ((info_moi["gia"] / info_cu["gia"]) - 1) * 100
            if info_cu["gia"] > 0
            else 0
        )
        oi_usd_m = info_moi["oi_usd"] / 1_000_000
        danh_sach_tang.append((pt_oi, pt_gia, oi_usd_m, sym))

    danh_sach_tang.sort(key=lambda x: x[0], reverse=True)
    top_5 = danh_sach_tang[:SO_COIN_TOI_DA]

    if top_5:
      dong_tin = [
          f"• **{sym}**: OI `+{pt_oi:.3f}%` | Giá `{pt_gia:+.2f}%` | Tổng OI:"
          f" `${oi_usd_m:.2f}M`"
          for pt_oi, pt_gia, oi_usd_m, sym in top_5
      ]
      gui_discord(
          f"🟡 **BINANCE TOP {len(top_5)} TĂNG OI ({CHU_KY_QUET_GIAY}s)** — Tổng"
          f" {len(danh_sach_tang)} mã vượt ngưỡng *(Quét {toc_do:.2f}s)*:\n"
          + "\n".join(dong_tin)
      )

    du_lieu_truoc = du_lieu_moi


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
