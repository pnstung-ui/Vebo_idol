import requests
import pandas as pd
import io
import os
from datetime import datetime, timedelta

# --- THÔNG TIN ĐỊNH DANH ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"
MEMORY_FILE = "shark_memory.csv"
HIST_URL = "https://www.football-data.co.uk/new_fixtures.csv"

def get_now_gmt7():
    return datetime.now() + timedelta(hours=7)

def shark_scanner():
    if not os.path.exists(MEMORY_FILE):
        pd.DataFrame(columns=['time', 'match', 'side', 'line', 'odd', 'tag', 'status']).to_csv(MEMORY_FILE, index=False)
    
    # Tải dữ liệu lịch sử (Football-Data)
    hist_df = None
    try:
        r = requests.get(HIST_URL, timeout=15)
        hist_df = pd.read_csv(io.StringIO(r.text))
    except: pass

    now = get_now_gmt7()
    # Danh sách giải bao gồm cả Nam Mỹ và các giải đang diễn ra
    REGIONS = ['soccer_epl', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 'soccer_spain_la_liga', 
               'soccer_netherlands_ere_divisie', 'soccer_brazil_campeonato', 'soccer_usa_mls', 'soccer_portugal_primeira_liga']

    for sport in REGIONS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals,spreads', 'oddsFormat': 'decimal'}
        try:
            data = requests.get(url, params=params).json()
            for m in data:
                home, away = m['home_team'], m['away_team']
                start_time = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                if now < start_time < now + timedelta(hours=18):
                    diff = start_time - now
                    countdown = f"{int(diff.total_seconds() // 3600)}h {int((diff.total_seconds() % 3600) // 60)}p"
                    
                    # --- LOGIC LINH HOẠT 1-4 TRẬN ---
                    match_avg = None
                    sample_size = 0
                    if hist_df is not None:
                        h_data = hist_df[(hist_df['HomeTeam'] == home) | (hist_df['AwayTeam'] == home)].tail(4)
                        a_data = hist_df[(hist_df['HomeTeam'] == away) | (hist_df['AwayTeam'] == away)].tail(4)
                        
                        combined = pd.concat([h_data, a_data])
                        if not combined.empty:
                            sample_size = len(combined)
                            # Tính trung bình từ số trận thực tế có được (1, 2, 3 hoặc 4)
                            match_avg = combined['Avg>2.5'].mean()

                    # Phân tích dựa trên dữ liệu có sẵn
                    analyze_flexible(m, home, away, start_time, countdown, match_avg, sample_size)
        except: continue

def analyze_flexible(match, home, away, start_time, countdown, match_avg, sample_size):
    bm = match['bookmakers'][0]
    mkts = {mk['key']: mk for mk in bm['markets']}
    
    if 'totals' in mkts:
        line = mkts['totals']['outcomes'][0]['point']
        o_p, u_p = mkts['totals']['outcomes'][0]['price'], mkts['totals']['outcomes'][1]['price']
        
        # 1. TRƯỜNG HỢP CÓ LỊCH SỬ (DÙ CHỈ 1 TRẬN)
        if match_avg is not None:
            gap = line - match_avg
            # Bẫy dụ Tài (Lịch sử nổ nhưng Odd nhử ăn cao)
            if gap < -0.4 and o_p >= 2.05:
                fire_msg(home, away, "XỈU", line, u_p, f"💣 BẪY TÀI (Dựa trên {sample_size} trận)", start_time, countdown)
            # Bẫy dụ Xỉu
            elif gap > 0.4 and u_p >= 2.05:
                fire_msg(home, away, "TÀI", line, o_p, f"⚠️ BẪY XỈU (Dựa trên {sample_size} trận)", start_time, countdown)

        # 2. TRƯỜNG HỢP ĐỘI MỚI/KHÔNG LỊCH SỬ HOẶC TIỀN ÉP MẠNH (Luôn ưu tiên biến động tiền)
        # Odd giữ nguyên/tăng mà tiền giảm (Tiền ép) -> Vả theo hướng tiền sập
        if o_p < 1.78:
            fire_msg(home, away, "TÀI", line, o_p, "🔥 TIỀN ÉP TÀI (SẬP ODD)", start_time, countdown)
        elif u_p < 1.78:
            fire_msg(home, away, "XỈU", line, u_p, "❄️ TIỀN ÉP XỈU (SẬP ODD)", start_time, countdown)

def fire_msg(home, away, side, line, odd, tag, start_time, countdown):
    msg = (f"🏪 *SHARK RADAR LINH HOẠT*\n"
           f"🏟️ {home} vs {away}\n"
           f"🎯 Lệnh: *VẢ {side} {line}*\n"
           f"🚩 Tín hiệu: {tag}\n"
           f"💰 Odd: {odd}\n"
           f"⏰ {start_time.strftime('%H:%M')} (Còn {countdown})\n"
           f"📢 Múi giờ: GMT+7")
    requests.post(f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage", json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    pd.DataFrame([[start_time, f"{home}-{away}", side, line, odd, tag, "WAITING"]]).to_csv(MEMORY_FILE, mode='a', header=False, index=False)

if __name__ == "__main__":
    shark_scanner()
