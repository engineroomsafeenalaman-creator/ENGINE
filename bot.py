import concurrent.futures
import os
import threading
import time
from flask import Flask
import requests

# ==========================================
# 1. CẤU HÌNH BOT (CHỈ CẦN CHỈNH Ở ĐÂY)
# ==========================================
# 👉 Dán link Webhook Discord mới của bạn vào giữa 2 dấu ngoặc kép bên dưới:
WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"

NGUONG_TY_LE_OI = 1.00001  # 1.00001 = tăng 0.001% | 1.005 = 0.5% | 1.01 = 1%
CHU_KY_QUET_GIAY = 60  # Quét chuẩn theo khung 1 phút (60 giây)
SO_COIN_TOI_DA = 10  # Chỉ lấy Top 10 coin tăng mạnh nhất mỗi phút
BAO_NHIP_TIM = False  # Đổi thành True nếu muốn mỗi phút đều báo dù không có coin vượt ngưỡng

# ==========================================
# 2. HỆ THỐNG & DANH SÁCH DỰ PHÒNG
# ==========================================
TEN_SAN = "binance" + ".com"
DOMAIN_WEB = "https://www." + TEN_SAN
DOMAIN_FAPI = "https://fapi." + TEN_SAN
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Dùng Session để tái sử dụng kết nối, tăng tốc độ và giảm nguy cơ bị chặn IP
session = requests.Session()
session.headers.update(HEADERS)

DANH_SACH_DU_PHONG = list(
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

app = Flask(__name__)


@app.route("/")
def home():
  return "Bot canh OI Alpha dang hoat dong!"


# ==========================================
# 3. CÁC HÀM XỬ LÝ CHÍNH
# ==========================================
def gui_discord(noi_dung):
  if not WEBHOOK_URL or "://discord.com" not in WEBHOOK_URL:
    print("❌ Lỗi: Link WEBHOOK_URL không hợp lệ!", flush=True)
    return

  try:
    for i in range(0, len(noi_dung), 1900):
      doan_tin = noi_dung[i : i + 1900]
      res = requests.post(WEBHOOK_URL, json={"content": doan_tin}, timeout=10)
      if res.status_code not in (200, 204):
        print(
            f"⚠️ Discord từ chối tin nhắn! Mã lỗi: {res.status_code} - {res.text}",
            flush=True,
        )
      time.sleep(0.5)
  except Exception as e:
    print(f"❌ Lỗi kết nối Discord: {e}", flush=True)


def lay_danh_sach_coin_alpha_futures():
  try:
    path_alpha = (
        "/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"
    )
    res_alpha = session.get(DOMAIN_WEB + path_alpha, timeout=15).json()

    alpha_symbols = {
        item.get("symbol", "").upper()
        for item in res_alpha.get("data", [])
        if item.get("symbol")
    }

    res_prices = session.get(
        DOMAIN_FAPI + "/fapi/v1/ticker/price", timeout=10
    ).json()

    if isinstance(res_prices, list) and len(res_prices) > 0:
      danh_sach = [
          item["symbol"]
          for item in res_prices
          if item.get("symbol", "").endswith("USDT")
          and item["symbol"][:-4] in alpha_symbols
      ]
      if danh_sach:
        print(
            f"✅ Lấy tự động được {len(danh_sach)} coin Alpha từ API.",
            flush=True,
        )
        return danh_sach
  except Exception as e:
    print(f"⚠️ Dùng danh sách dự phòng do lỗi API: {e}", flush=True)

  return DANH_SACH_DU_PHONG


def lay_oi_1_coin(symbol):
  url = DOMAIN_FAPI + f"/fapi/v1/openInterest?symbol={symbol}"
  try:
    res = session.get(url, timeout=5)
    if res.status_code == 200:
      data = res.json()
      return symbol, float(data["openInterest"]), 200
    return symbol, None, res.status_code
  except Exception:
    return symbol, None, 0


def quet_toan_bo_oi(danh_sach_coin):
  ket_qua = {}
  ma_loi_gap = set()

  # Giảm xuống 4 luồng để tránh bị Binance khóa IP trên Render
  with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
    futures = [executor.submit(lay_oi_1_coin, sym) for sym in danh_sach_coin]
    for f in concurrent.futures.as_completed(futures):
      sym, oi, status = f.result()
      if status == 200 and oi is not None and oi > 0:
        ket_qua[sym] = oi
      elif status != 200:
        ma_loi_gap.add(status)

  return ket_qua, ma_loi_gap


def chay_bot_canh_oi():
  print("🚀 Đang khởi động Bot canh OI...", flush=True)
  danh_sach_alpha = lay_danh_sach_coin_alpha_futures()

  oi_phut_truoc, ma_loi = quet_toan_bo_oi(danh_sach_alpha)

  if not oi_phut_truoc:
    gui_discord(
        f"⚠️ **Cảnh báo:** Bot đã bật nhưng KHÔNG lấy được dữ liệu từ Binance"
        f" (Mã lỗi: {ma_loi}). IP Render có thể đang bị chặn!"
    )
  else:
    nguong_phan_tram = (NGUONG_TY_LE_OI - 1) * 100
    gui_discord(
        f"✅ **Bot đã kết nối thành công!**\n"
        f"- Đang quét: **{len(oi_phut_truoc)}/{len(danh_sach_alpha)}** coin"
        f" Alpha\n"
        f"- Chu kỳ: **{CHU_KY_QUET_GIAY}s** | Ngưỡng lọc:"
        f" **+{nguong_phan_tram:.4f}%**"
    )

  da_bao_loi_ip = False

  while True:
    time.sleep(CHU_KY_QUET_GIAY)
    oi_hien_tai, ma_loi = quet_toan_bo_oi(danh_sach_alpha)

    # Xử lý khi bị Binance chặn IP hoặc mất kết nối
    if not oi_hien_tai:
      print(f"⚠️ Không lấy được dữ liệu OI. Mã lỗi: {ma_loi}", flush=True)
      if not da_bao_loi_ip:
        gui_discord(
            f"🚫 **Lỗi lấy dữ liệu Binance** (Mã lỗi: `{ma_loi}`). Server"
            " đang tạm bị giới hạn IP, bot sẽ tự thử lại..."
        )
        da_bao_loi_ip = True
      continue

    da_bao_loi_ip = False

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

    # Sắp xếp giảm dần theo % tăng và lấy Top coin mạnh nhất
    danh_sach_tang.sort(reverse=True)
    top_coin = danh_sach_tang[:SO_COIN_TOI_DA]

    if top_coin:
      noi_dung_bao = [f"**{sym}** (+{pt:.4f}%)" for pt, sym in top_coin]
      tong_so = len(danh_sach_tang)
      gui_discord(
          f"⏱️ **Top tăng OI trong {CHU_KY_QUET_GIAY}s qua** (Tổng {tong_so}"
          " coin vượt ngưỡng):\n"
          + ", ".join(noi_dung_bao)
      )
    elif BAO_NHIP_TIM:
      gui_discord(
          f"🔄 Đã quét {len(oi_hien_tai)} coin — Chưa có mã nào vượt ngưỡng."
      )

    oi_phut_truoc = oi_hien_tai


# ==========================================
# 4. KHỞI CHẠY AN TOÀN (CHỐNG TRÙNG LUỒNG)
# ==========================================
