import requests
import pandas as pd
import io
import os
from datetime import datetime, timedelta

# --- THÔNG TIN CỦA IDOL ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"
MEMORY_FILE = "shark_memory.csv"
HIST_URL = "https://www.football-data.co.uk/new_fixtures.csv"

def get_now_gmt7():
    return datetime.now() + timedelta(hours=7)

def get_h2h_data():
    try:
        r = requests.get(HIST_URL, timeout=15)
        return pd.read_csv(io.StringIO(r.text))
    except: return None

def shark_scanner():
    # Khởi tạo file nhớ nếu chưa có
    if not os.path.exists(MEMORY_FILE):
        pd.DataFrame(columns=['time', 'match', 'side', 'line', 'odd', 'tag', 'status']).to_csv(MEMORY_FILE, index=False)
    
    hist_df = get_h2h_data()
    now = get_now_gmt7()
    
    # Danh sách giải (Full Châu Âu + Brazil + MLS)
    REGIONS = ['soccer_epl', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 'soccer_spain_la_liga', 
               'soccer_netherlands_ere_divisie', 'soccer_brazil_campeonato', 'soccer_usa_mls']

    for sport in REGIONS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals,spreads', 'oddsFormat': 'decimal'}
        try:
            r = requests.get(url, params=params).json()
            for m in r:
                home, away = m['home_team'], m['away_team']
                start_time = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                # Quét trận sắp đá (trong 12h tới)
                if now < start_time < now + timedelta(hours=12):
                    diff = start_time - now
                    countdown = f"{int(diff.total_seconds() // 3600)}h {int((diff.total_seconds() % 3600) // 60)}p"
                    
                    # --- LẤY DỮ LIỆU LỊCH SỬ 4 TRẬN (CHÂN KINH) ---
                    match_avg = 2.5
                    if hist_df is not None:
                        h_matches = hist_df[(hist_df['HomeTeam'] == home) | (hist_df['AwayTeam'] == home)].tail(4)
                        a_matches = hist_df[(hist_df['HomeTeam'] == away) | (hist_df['AwayTeam'] == away)].tail(4)
                        if len(h_matches) >= 2: 
                            match_avg = (h_matches['Avg>2.5'].mean() + a_matches['Avg>2.5'].mean()) / 2

                    analyze_logic(m, home, away, start_time, countdown, match_avg)
        except: continue

def analyze_logic(match, home, away, start_time, countdown, match_avg):
    bm = match['bookmakers'][0]
    mkts = {mk['key']: mk for mk in bm['markets']}
    
    # 1. TÀI XỈU: TIỀN ÉP & BẪY H2H
    if 'totals' in mkts:
        line = mkts['totals']['outcomes'][0]['point']
        o_p, u_p = mkts['totals']['outcomes'][0]['price'], mkts['totals']['outcomes'][1]['price']
        
        # BẪY DỤ TÀI: H2H nổ to nhưng Line thấp + Odd Tài nhử cao (>2.05)
        if match_avg > 2.8 and line <= 2.5 and o_p >= 2.05:
            send_msg(home, away, "XỈU", line, u_p, "💣 BẪY DỤ TÀI (H2H nổ - Odd nhử)", start_time, countdown)
        # TIỀN ÉP: Odd giảm sâu dưới 1.78
        elif o_p < 10:
            send_msg(home, away, "TÀI", line, o_p, "🔥 TIỀN ÉP TÀI", start_time, countdown)
        elif u_p < 10:
            send_msg(home, away, "XỈU", line, u_p, "❄️ TIỀN ÉP XỈU", start_time, countdown)

    # 2. KÈO CHẤP: BẪY THỨ HẠNG
    if 'spreads' in mkts:
        h_line = mkts['spreads']['outcomes'][0]['point']
        h_p, a_p = mkts['spreads']['outcomes'][0]['price'], mkts['spreads']['outcomes'][1]['price']
        # Bẫy Dụ Trên: Đội hạng cao chấp thấp + Odd nhử cao
        if h_line >= -0.75 and h_p >= 2.05:
            send_msg(home, away, "DƯỚI", h_line, a_p, "🛡️ BẪY THỨ HẠNG (DỤ TRÊN)", start_time, countdown)

def send_msg(home, away, side, line, odd, tag, start_time, countdown):
    msg = (f"🏪 *SHARK RADAR GMT+7*\n"
           f"🏟️ Trận: {home} vs {away}\n"
           f"🎯 Lệnh: *VẢ {side} {line}*\n"
           f"🚩 Tín hiệu: {tag}\n"
           f"💰 Odd: {odd}\n"
           f"⏰ Đá: {start_time.strftime('%H:%M')} (Còn {countdown})")
    
    url = f"https://api.the-odds-api.com/v4/sports/soccer/scores/?apiKey={API_KEY}" # Dùng check kết quả sau
    requests.post(f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage", 
                  json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    
    # Lưu để Shark_Checker báo HÚP/GÃY
    pd.DataFrame([[start_time, f"{home}-{away}", side, line, odd, tag, "WAITING"]]).to_csv(MEMORY_FILE, mode='a', header=False, index=False)

if __name__ == "__main__":
    shark_scanner()
