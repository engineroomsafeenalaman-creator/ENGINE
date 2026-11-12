from concurrent.futures import ThreadPoolExecutor, as_completed
import os
import threading
import time
from flask import Flask
import requests
from requests.adapters import HTTPAdapter

# ==========================================
# 1. CAU HINH BOT (DAN LINK DISCORD O DONG DUOI)
# ==========================================
WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"

NGUONG_TY_LE_OI = 1.0001
CHU_KY_QUET_GIAY = 30
SO_COIN_TOI_DA = 5
SO_LUONG_SONG_SONG = 10

BINANCE_ENDPOINTS = [
    "https://binance.com",
    "https://binance.com",
    "https://binance.com",
    "https://binance.com",
]
current_ep_idx = 0

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
adapter = HTTPAdapter(pool_connections=SO_LUONG_SONG_SONG + 5, pool_maxsize=SO_LUONG_SONG_SONG + 5)
session.mount("https://", adapter)
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
})

executor = ThreadPoolExecutor(max_workers=SO_LUONG_SONG_SONG)
rate_limit_event = threading.Event()
_bot_started = False
_start_lock = threading.Lock()


def get_base_url():
    return BINANCE_ENDPOINTS[current_ep_idx % len(BINANCE_ENDPOINTS)]


def switch_base_url():
    global current_ep_idx
    current_ep_idx += 1
    return get_base_url()


def format_usd(value):
    if value >= 1_000_000:
        return f"${value / 1_000_000:.2f}M"
    if value >= 1_000:
        return f"${value / 1_000:.1f}K"
    return f"${value:.0f}"


def gui_discord(noi_dung):
    url = os.environ.get("WEBHOOK_URL", "") or WEBHOOK_URL
    if not url or "://discord.com" not in url:
        print(f"[CONSOLE]:\n{noi_dung}\n", flush=True)
        return
    try:
        for i in range(0, len(noi_dung), 1900):
            doan_tin = noi_dung[i : i + 1900]
            res = session.post(url, json={"content": doan_tin}, timeout=10)
            if res.status_code == 429:
                retry_after = float(res.json().get("retry_after", 2))
                time.sleep(retry_after)
                session.post(url, json={"content": doan_tin}, timeout=10)
            time.sleep(0.3)
    except Exception as e:
        print(f"Loi gui Discord: {e}", flush=True)


def kiem_tra_ket_noi_binance():
    chi_tiet_loi = []
    for _ in range(len(BINANCE_ENDPOINTS)):
        ep = get_base_url()
        try:
            r = session.get(f"{ep}/fapi/v1/ticker/price?symbol=BTCUSDT", timeout=5)
            if r.status_code == 200:
                return True, f"Ket noi thanh cong toi `{ep}`"
            chi_tiet_loi.append(f"`{ep}` -> HTTP **{r.status_code}**")
        except Exception as e:
            chi_tiet_loi.append(f"`{ep}` -> Loi: {str(e)[:40]}")
        switch_base_url()
    return False, "\n".join(chi_tiet_loi)


def lay_1_oi_binance(sym, base_url):
    if rate_limit_event.is_set():
        return sym, 0.0
    url = f"{base_url}/fapi/v1/openInterest?symbol={sym}"
    try:
        res = session.get(url, timeout=4)
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
    base_url = get_base_url()

    try:
        res_gia = session.get(f"{base_url}/fapi/v1/ticker/price", timeout=6)
        if res_gia.status_code == 200:
            for item in res_gia.json():
                sym = item.get("symbol", "")
                if sym in danh_sach_hop_le:
                    gia_map[sym] = float(item.get("price", 0))
        elif res_gia.status_code in (418, 429):
            rate_limit_event.set()
            return ket_qua
    except Exception as e:
        print(f"Loi lay gia ({base_url}): {e}", flush=True)
        switch_base_url()
        return ket_qua

    futures = [executor.submit(lay_1_oi_binance, sym, base_url) for sym in gia_map]
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
            f"**BINANCE TU CHOI KET NOI:**\n{thong_bao}\n\n"
            "*IP Server Render dang bi Binance chan (451). Hay doi Region sang Singapore!*"
        )
        return

    t0 = time.time()
    du_lieu_truoc = lay_toan_bo_du_lieu_binance(DANH_SACH_ALPHA)
    toc_do = time.time() - t0
    danh_sach_ton_tai = set(du_lieu_truoc.keys())

    gui_discord(
        f"**Bot Canh OI Khoi Dong Thanh Cong!**\n"
        f"- Endpoint: `{get_base_url()}`\n"
        f"- Theo doi: **{len(danh_sach_ton_tai)}/{len(DANH_SACH_ALPHA)}** coin\n"
        f"- Toc do quet: **{toc_do:.2f}s**"
    )

    while True:
        thoi_gian_cho = max(1.0, CHU_KY_QUET_GIAY - (time.time() - t0))
        time.sleep(thoi_gian_cho)

        t0 = time.time()
        du_lieu_moi = lay_toan_bo_du_lieu_binance(danh_sach_ton_tai)

        if rate_limit_event.is_set():
            new_ep = switch_base_url()
            print(f"Dinh Rate Limit! Chuyen sang {new_ep} va nghi 60s...", flush=True)
            time.sleep(60)
            continue

        if not du_lieu_moi:
            continue

        bien_dong = []
        for sym, moi in du_lieu_moi.items():
            truoc = du_lieu_truoc.get(sym)
            if not truoc or truoc["oi"] <= 0:
                continue

            ty_le_oi = moi["oi"] / truoc["oi"]
            if ty_le_oi >= NGUONG_TY_LE_OI:
                phan_tram_oi = (ty_le_oi - 1) * 100
                phan_tram_gia = ((moi["gia"] / truoc["gia"]) - 1) * 100
                chenh_lech_usd = moi["oi_usd"] - truoc["oi_usd"]
                bien_dong.append({
                    "sym": sym,
                    "phan_tram_oi": phan_tram_oi,
                    "phan_tram_gia": phan_tram_gia,
                    "oi_usd": moi["oi_usd"],
                    "chenh_lech_usd": chenh_lech_usd,
                    "gia": moi["gia"],
                })

        if bien_dong:
            bien_dong.sort(key=lambda x: x["phan_tram_oi"], reverse=True)
            top_coins = bien_dong[:SO_COIN_TOI_DA]
            dong_tin = [f"**BIEN DONG OI ({CHU_KY_QUET_GIAY}s)** | Quet mat `{time.time() - t0:.2f}s`"]
            for idx, c in enumerate(top_coins, 1):
