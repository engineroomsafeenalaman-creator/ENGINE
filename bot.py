from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import threading
import time
from flask import Flask
import requests
from requests.adapters import HTTPAdapter

# ==========================================
# 1. CẤU HÌNH BOT
# ==========================================
WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"

NGUONG_TY_LE_OI = 1.0001  # Tăng > 0.01%
CHU_KY_QUET_GIAY = 30
SO_COIN_TOI_DA = 5
SO_LUONG_SONG_SONG = 15

# Endpoint chính thức và dự phòng của Binance Futures
BINANCE_ENDPOINTS = [
    "https://fapi.binance.com",
    "https://fapi1.binance.com",
    "https://fapi2.binance.com",
    "https://fapi3.binance.com",
]
ACTIVE_BASE_URL = BINANCE_ENDPOINTS[0]

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

# Khởi tạo Session và Pool tái sử dụng xuyên suốt vòng đời app
session = requests.Session()
adapter = HTTPAdapter(
    pool_connections=SO_LUONG_SONG_SONG + 5,
    pool_maxsize=SO_LUONG_SONG_SONG + 5,
)
session.mount("https://", adapter)
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
})

# Tạo sẵn ThreadPoolExecutor dùng chung
executor = ThreadPoolExecutor(max_workers=SO_LUONG_SONG_SONG)
rate_limit_event = threading.Event()


@app.route("/")
def home():
    return "Bot canh OI Binance Futures (30s) dang chay!"


def format_usd(value):
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.0f}"


def gui_discord(noi_dung):
    if not WEBHOOK_URL or "://discord.com" not in WEBHOOK_URL:
        print(f"[CONSOLE]:\n{noi_dung}\n", flush=True)
        return
    try:
        for i in range(0, len(noi_dung), 1900):
            doan_tin = noi_dung[i : i + 1900]
            res = session.post(WEBHOOK_URL, json={"content": doan_tin}, timeout=10)
            if res.status_code == 429:
                retry_after = float(res.json().get("retry_after", 2))
                time.sleep(retry_after)
                session.post(WEBHOOK_URL, json={"content": doan_tin}, timeout=10)
            time.sleep(0.3)
    except Exception as e:
        print(f"Loi gui Discord: {e}", flush=True)


def kiem_tra_ket_noi_binance():
    global ACTIVE_BASE_URL
    chi_tiet_loi = []
    for ep in BINANCE_ENDPOINTS:
        try:
            r = session.get(f"{ep}/fapi/v1/ticker/price?symbol=BTCUSDT", timeout=6)
            if r.status_code == 200:
                ACTIVE_BASE_URL = ep
                return True, f"Kết nối thành công tới `{ep}`"
            chi_tiet_loi.append(f"`{ep}` -> HTTP **{r.status_code}**")
        except Exception as e:
            chi_tiet_loi.append(f"`{ep}` -> Lỗi: {str(e)[:40]}")
    return False, "\n".join(chi_tiet_loi)


def lay_1_oi_binance(sym):
    # Nếu đang bị dính Rate Limit thì bỏ qua ngay các luồng còn lại
    if rate_limit_event.is_set():
        return sym, 0.0

    url = f"{ACTIVE_BASE_URL}/fapi/v1/openInterest?symbol={sym}"
    try:
        res = session.get(url, timeout=5)
        if res.status_code == 200:
            return sym, float(res.json().get("openInterest", 0))
        if res.status_code in (418, 429):
            rate_limit_event.set()
    except Exception:
        pass
    return sym, 0.0


def lay_toan_bo_du_lieu_binance(danh_sach_hop_le):
    ket_qua = {}
    gia_map = {}
    rate_limit_event.clear()

    try:
        res_gia = session.get(f"{ACTIVE_BASE_URL}/fapi/v1/ticker/price", timeout=8)
        if res_gia.status_code == 200:
            for item in res_gia.json():
                sym = item.get("symbol", "")
                if sym in danh_sach_hop_le:
                    gia_map[sym] = float(item.get("price", 0))
        elif res_gia.status_code in (418, 429):
            rate_limit_event.set()
            return ket_qua
    except Exception as e:
        print(f"Loi lay gia: {e}", flush=True)
        return ket_qua

    futures = {executor.submit(lay_1_oi_binance, sym): sym for sym in gia_map}
    for future in as_completed(futures):
        sym, oi = future.result()
        gia = gia_map.get(sym, 0)
        if oi > 0 and gia > 0:
            ket_qua[sym] = {"oi": oi, "gia": gia, "oi_usd": oi * gia}

    return ket_qua


def chay_bot_canh_oi():
    ok, thong_bao = kiem_tra_ket_noi_binance()
    if not ok:
        gui_discord(
            f"🚨 **BINANCE TỪ CHỐI KẾT NỐI:**\n{thong_bao}\n\n"
            "👉 *IP Server có thể đang bị Binance chặn vùng (US/Cloud).*"
        )
        return

    t0 = time.time()
    du_lieu_truoc = lay_toan_bo_du_lieu_binance(DANH_SACH_ALPHA)
    toc_do = time.time() - t0

    danh_sach_ton_tai = set(du_lieu_truoc.keys()) if du_lieu_truoc else DANH_SACH_ALPHA
    nguong_pt = (NGUONG_TY_LE_OI - 1) * 100

    gui_discord(
        f"✅ **Bot Binance Futures đã kết nối!** ({thong_bao})\n"
        f"📊 Tìm thấy **{len(du_lieu_truoc)}/{len(DANH_SACH_ALPHA)}** coin Alpha trong **{toc_do:.2f}s**\n"
        f"⏱️ Chu kỳ: **{CHU_KY_QUET_GIAY}s** | 🎯 Ngưỡng cảnh báo: **+{nguong_pt:.3f}%**"
    )

    while True:
        thoi_gian_ngu = max(1.0, CHU_KY_QUET_GIAY - toc_do)
        time.sleep(thoi_gian_ngu)

        t_quet = time.time()
        du_lieu_moi = lay_toan_bo_du_lieu_binance(danh_sach_ton_tai)
        toc_do = time.time() - t_quet

        # Xử lý khi bị Rate Limit
        if rate_limit_event.is_set():
            print("⚠️ Dinh Rate Limit Binance, nghi 60s...", flush=True)
            time.sleep(60)
            continue

        if not du_lieu_moi or not du_lieu_truoc:
            if du_lieu_moi:
                du_lieu_truoc = du_lieu_moi
            continue

        danh_sach_tang = []
        for sym, info_moi in du_lieu_moi.items():
            info_cu = du_lieu_truoc.get(sym)
            if not info_cu or info_cu["oi"] <= 0:
                continue

            ty_le_oi = info_moi["oi"] / info_cu["oi"]
            if ty_le_oi >= NGUONG_TY_LE_OI:
                pt_oi = (ty_le_oi - 1) * 100
                pt_gia = ((info_moi["gia"] / info_cu["gia"]) - 1) * 100
                chenh_usd = info_moi["oi_usd"] - info_cu["oi_usd"]

                danh_sach_tang.append({
                    "sym": sym,
                    "pt_oi": pt_oi,
                    "pt_gia": pt_gia,
                    "gia": info_moi["gia"],
                    "oi_usd": info_moi["oi_usd"],
                    "chenh_usd": chenh_usd,
                })
