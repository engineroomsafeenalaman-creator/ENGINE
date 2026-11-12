import concurrent.futures
import os
import threading
import time
from flask import Flask
import requests

# ⚠️ NHỚ TẠO LẠI LINK WEBHOOK MỚI TRÊN DISCORD VÀ DÁN VÀO ĐÂY
WEBHOOK_URL = "https://discord.com/api/webhooks/1570320464172285962/PT-xnCZ00dB024QmxRcWVxcoVBOA8FgqG-X74ZOdAz9imXFaycr69FFmZxrqHqNfz3jN"

# Ngưỡng tăng OI trong 1 phút (1.115 = tăng 11.5% trở lên)
NGUONG_TY_LE_OI = 1.115

TEN_SAN = "binance" + ".com"
DOMAIN_WEB = "https://www." + TEN_SAN
DOMAIN_FAPI = "https://fapi." + TEN_SAN
HEADERS = {"User-Agent": "Mozilla/5.0"}

# Dùng chung 1 Session giúp tiết kiệm RAM và tránh nghẽn kết nối trên Render
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

DANH_SACH_DU_PHONG = [
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
]

app = Flask(__name__)


@app.route("/")
def home():
    return "Bot canh OI 1 phut dang hoat dong binh thuong!"


def gui_discord(noi_dung):
    try:
        res = requests.post(WEBHOOK_URL, json={"content": noi_dung}, timeout=10)
        print(f"Gửi Discord status: {res.status_code}", flush=True)
    except Exception as e:
        print(f"Lỗi gửi Discord: {e}", flush=True)


def lay_danh_sach_coin_alpha_futures():
    try:
        path_alpha = "/bapi/defi/v1/public/wallet-direct/buw/wallet/cex/alpha/all/token/list"
        res_alpha = SESSION.get(DOMAIN_WEB + path_alpha, timeout=15).json()

        alpha_symbols = {
            item.get("symbol", "").upper()
            for item in res_alpha.get("data", [])
            if item.get("symbol")
        }
        print(f"Lấy được {len(alpha_symbols)} token Alpha", flush=True)

        res_prices = SESSION.get(DOMAIN_FAPI + "/fapi/v1/ticker/price", timeout=10).json()
        if isinstance(res_prices, list) and len(res_prices) > 0:
            danh_sach = list({
                item["symbol"]
                for item in res_prices
                if item.get("symbol", "").endswith("USDT")
                and item["symbol"][:-4] in alpha_symbols
            })
            if danh_sach:
                return danh_sach
    except Exception as e:
        print(f"Chuyển sang dùng danh sách dự phòng do: {e}", flush=True)

    return list(set(DANH_SACH_DU_PHONG))


def lay_oi_1_coin(symbol):
    # Nghỉ cực ngắn 0.08s để dàn đều request, tránh bị Binance chặn IP Render
    time.sleep(0.08)
    url = DOMAIN_FAPI + f"/fapi/v1/openInterest?symbol={symbol}"
    try:
        res = SESSION.get(url, timeout=5)
        if res.status_code == 200:
            data = res.json()
            return symbol, float(data["openInterest"])
        elif res.status_code in (418, 429):
            # Nếu bị Binance cảnh báo quá tải, nghỉ nhẹ 2 giây
            time.sleep(2)
        return symbol, None
    except Exception:
        return symbol, None


def quet_toan_bo_oi(danh_sach_coin):
    ket_qua = {}
    # Giảm xuống 4 luồng để gọi êm ái, không làm nghẽn IP dùng chung
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
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
        f"✅ Bot đã kết nối và đang quét **{len(danh_sach_alpha)}** coin Alpha (Ngưỡng 1p: **+{(NGUONG_TY_LE_OI - 1)*100:.1f}%**)!"
    )

    oi_phut_truoc = quet_toan_bo_oi(danh_sach_alpha)
    print(f"Lần quét đầu tiên lấy được OI của {len(oi_phut_truoc)} coin.", flush=True)
    coin_dang_theo_doi_giam = set()

    while True:
        # Đợi đúng 60 giây cho khung 1 phút chuẩn
        time.sleep(60)
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

            ty_le = oi_moi / oi_cu
            phan_tram = (ty_le - 1) * 100

            # Kiểm tra điều kiện tăng >= 11.5% (1.115)
            if ty_le >= NGUONG_TY_LE_OI:
                coin_dang_theo_doi_giam.add(sym)
                coin_tang.append(f"🚀 **{sym}**: tăng **+{phan_tram:.2f}%** (x{ty_le:.3f})")
            elif sym in coin_dang_theo_doi_giam and oi_moi < oi_cu:
                coin_dang_theo_doi_giam.remove(sym)
                coin_giam.append(f"🔻 **{sym}**: bắt đầu giảm OI (**{phan_tram:.2f}%**)")

        # Gửi thông báo gộp 1 tin nhắn duy nhất mỗi phút (chống spam Discord)
        tin_nhan_tong = []
        if coin_tang:
            tin_nhan_tong.append("🔥 **PHÁT HIỆN OI TĂNG ĐỘT BIẾN (1P):**\n" + "\n".join(coin_tang))
        if coin_giam:
            tin_nhan_tong.append("📉 **CẬP NHẬT XẢ OI SAU SÓNG:**\n" + "\n".join(coin_giam))

        if tin_nhan_tong:
            gui_discord("\n\n".join(tin_nhan_tong))

        # Cập nhật dữ liệu mới đè lên dữ liệu cũ (chống tràn RAM tuyệt đối)
        oi_phut_truoc = oi_hien_tai


# Chạy luồng quét OI song song với Web Server của Render
threading.Thread(target=chay_bot_canh_oi, daemon=True).start()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
