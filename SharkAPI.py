import requests
import pandas as pd
import io
import os
from datetime import datetime, timedelta

# --- THÔNG TIN ĐỊNH DANH IDOL ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"
MEMORY_FILE = "shark_memory.csv"
HIST_URL = "https://www.football-data.co.uk/new_fixtures.csv"

def send_tele(message):
    """Sử dụng đúng phương thức gửi của bản cũ Idol đã chạy ngon"""
    base_url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    params = {"chat_id": TELE_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    try:
        requests.get(base_url, params=params, timeout=10) # Dùng GET như các bản repo cũ thường dùng
    except:
        pass

def shark_scanner():
    now_vn = datetime.now() + timedelta(hours=7)
    # THÔNG NÒNG: Dòng này phải nổ đầu tiên
    send_tele(f"🚀 *SHARK RADAR 2026: ĐÃ KẾT NỐI!* \n⏰ Giờ: {now_vn.strftime('%H:%M:%S')}")

    if not os.path.exists(MEMORY_FILE):
        pd.DataFrame(columns=['time', 'match', 'side', 'line', 'odd', 'tag', 'status']).to_csv(MEMORY_FILE, index=False)

    # Tải lịch sử 4 trận
    hist_df = None
    try:
        r = requests.get(HIST_URL, timeout=15)
        hist_df = pd.read_csv(io.StringIO(r.text))
    except: pass

    # Quét đa giải (Mở rộng cho Idol)
    REGIONS = ['soccer_epl', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 'soccer_spain_la_liga', 'soccer_brazil_campeonato', 'soccer_usa_mls']

    for sport in REGIONS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals', 'oddsFormat': 'decimal'}
        try:
            data = requests.get(url, params=params).json()
            for m in data:
                home, away = m['home_team'], m['away_team']
                st = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                if now_vn < st < now_vn + timedelta(hours=24):
                    bm = m['bookmakers'][0]
                    mkt = bm['markets'][0]
                    line = mkt['outcomes'][0]['point']
                    o_p, u_p = mkt['outcomes'][0]['price'], mkt['outcomes'][1]['price']
                    
                    # --- CHÂN KINH LOGIC ---
                    tag = ""
                    # 1. Tiền ép (Odd giảm sâu dưới 1.78)
                    if o_p < 1.78: tag = "🔥 TIỀN ÉP TÀI (ODD GIẢM)"
                    elif u_p < 1.78: tag = "❄️ TIỀN ÉP XỈU (ODD GIẢM)"
                    
                    # 2. Bẫy Trap (Dựa trên 1-4 trận lịch sử)
                    if hist_df is not None:
                        combined = pd.concat([hist_df[(hist_df['HomeTeam']==home)|(hist_df['AwayTeam']==home)].tail(4),
                                            hist_df[(hist_df['HomeTeam']==away)|(hist_df['AwayTeam']==away)].tail(4)])
                        if not combined.empty:
                            avg = combined['Avg>2.5'].mean()
                            gap = line - avg
                            if gap < -0.4 and o_p >= 2.05: tag = "💣 BẪY DỤ TÀI (TRAP)"
                            elif gap > 0.4 and u_p >= 2.05: tag = "⚠️ BẪY DỤ XỈU (TRAP)"

                    if tag:
                        side = "TÀI" if "TÀI" in tag else "XỈU"
                        odd = o_p if side == "TÀI" else u_p
                        msg = f"🏪 *SHARK RADAR*\n🏟️ {home} vs {away}\n🎯 Lệnh: *VẢ {side} {line}*\n🚩 {tag}\n💰 Odd: {odd}\n⏰ {st.strftime('%H:%M')}"
                        send_tele(msg)
                        # Ghi nhớ để check HÚP/GÃY
                        pd.DataFrame([[st, f"{home}-{away}", side, line, odd, tag, "WAITING"]]).to_csv(MEMORY_FILE, mode='a', header=False, index=False)
        except: continue

if __name__ == "__main__":
    shark_scanner()
