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
NGHI_SAU_MOI_VONG_GIAY = 30  # Thời gian nghỉ sau khi quét xong 100% danh sách
SO_COIN_TOI_DA = 5  # Lấy Top 5 coin tăng mạnh nhất

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


def lay_danh_sach_coin_chuan():
  # Bước 1: Chỉ tốn 1 request duy nhất để lấy toàn bộ coin ĐANG MỞ GIAO DỊCH trên Binance Futures
  coin_dang_mo_futures = set()
  try:
    res_info = requests.get(
        DOMAIN_FAPI + "/fapi/v1/exchangeInfo", headers=HEADERS, timeout=15
    ).json()
    for s in res_info.get("symbols", []):
      if s.get("status") == "TRADING" and s.get("quoteAsset") == "USDT":
        coin_dang_mo_futures.add(s["symbol"])
  except Exception as e:
    print(f"Khong lay duoc exchangeInfo: {e}", flush=True)

  # Bước 2: Lấy danh sách token Alpha từ Binance
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
    if alpha_symbols and coin_dang_mo_futures:
      ds = sorted(
          [sym for sym in coin_dang_mo_futures if sym[:-4] in alpha_symbols]
      )
      if ds:
        return ds
  except Exception:
    pass

  # Nếu API Alpha bị chặn thì lọc danh sách 264 coin dự phòng qua những mã thực sự đang TRADING
  if coin_dang_mo_futures:
    return sorted([c for c in DANH_SACH_DU_PHONG if c in coin_dang_mo_futures])

  return DANH_SACH_DU_PHONG


def quet_du_100_phan_tram_oi(danh_sach_coin):
  ket_qua = {}
  idx = 0
  tong = len(danh_sach_coin)

  while idx < tong:
    sym = danh_sach_coin[idx]
    url = DOMAIN_FAPI + f"/fapi/v1/openInterest?symbol={sym}"
    try:
      res = requests.get(url, headers=HEADERS, timeout=8)
      if res.status_code == 200:
        data = res.json()
        oi = float(data["openInterest"])
        if oi > 0:
          ket_qua[sym] = oi
        idx += 1
        time.sleep(0.35)  # Nhịp độ đều đặn ~3 request/giây
      elif res.status_code in (418, 429):
        # Bị giới hạn tốc độ -> đọc thời gian phạt của Binance và chờ hết phạt rồi quét tiếp đúng mã này
        cho_giay = int(res.headers.get("Retry-After", 15))
        print(
            f"Tam nghi {cho_giay}s do gioi han toc do tai coin thu"
            f" {idx}/{tong}...",
            flush=True,
        )
        time.sleep(cho_giay + 1)
      else:
        # Lỗi khác (ví dụ mã không hỗ trợ OI) -> bỏ qua sang mã tiếp theo
        idx += 1
    except Exception:
      time.sleep(2)
      idx += 1

  return ket_qua


def chay_bot_canh_oi():
  print("Dang khoi dong Bot quet 100% danh sach...", flush=True)
  danh_sach_alpha = lay_danh_sach_coin_chuan()

  gui_discord(
      f"⏳ Đang khởi tạo dữ liệu lần đầu cho **{len(danh_sach_alpha)}** coin"
      " hợp lệ trên Futures (vui lòng đợi khoảng 1–2 phút)..."
  )

  oi_vong_truoc = quet_du_100_phan_tram_oi(danh_sach_alpha)

  nguong_pt = (NGUONG_TY_LE_OI - 1) * 100
  ds_ten = ", ".join(sorted(oi_vong_truoc.keys()))
  gui_discord(
      f"✅ **Hoàn tất khởi tạo!** Đã quét đủ"
      f" **{len(oi_vong_truoc)}/{len(danh_sach_alpha)}** coin | Ngưỡng"
      f" **+{nguong_pt:.4f}%**\n📋 **Danh sách đầy đủ:** {ds_ten}"
  )

  while True:
    time.sleep(NGHI_SAU_MOI_VONG_GIAY)
    oi_hien_tai = quet_du_100_phan_tram_oi(danh_sach_alpha)

    if not oi_hien_tai:
      continue

    danh_sach_tang = []
    for sym, oi_moi in oi_hien_tai.items():
      oi_cu = oi_vong_truoc.get(sym)
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
          f"⏱️ **Top tăng OI** (Quét đủ {len(oi_hien_tai)} coin | Tổng"
          f" {len(danh_sach_tang)} mã vượt ngưỡng):\n"
          + ", ".join(noi_dung_bao)
      )

    oi_vong_truoc = oi_hien_tai


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
