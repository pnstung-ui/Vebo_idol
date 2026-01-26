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

def send_tele_msg(text):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except Exception as e:
        print(f"Lỗi gửi Tele: {e}")

def test_connection():
    """Gửi tin nhắn kiểm tra ngay khi Bot bắt đầu chạy"""
    now_str = (datetime.now() + timedelta(hours=7)).strftime('%H:%M:%S')
    test_msg = f"🚀 *SHARK RADAR: ĐÃ THÔNG NÒNG!*\n⏰ Thời gian: {now_str}\n📡 Trạng thái: Đang quét kèo..."
    send_tele_msg(test_msg)

def shark_scanner():
    # 1. Phát đạn thông nòng
    test_connection()
    
    if not os.path.exists(MEMORY_FILE):
        pd.DataFrame(columns=['time', 'match', 'side', 'line', 'odd', 'tag', 'status']).to_csv(MEMORY_FILE, index=False)
    
    # 2. Tải dữ liệu lịch sử
    hist_df = None
    try:
        r = requests.get(HIST_URL, timeout=15)
        hist_df = pd.read_csv(io.StringIO(r.text))
    except: pass

    now = datetime.now() + timedelta(hours=7)
    # Mở rộng full các giải Idol cần
    REGIONS = ['soccer_epl', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 'soccer_spain_la_liga', 
               'soccer_netherlands_ere_divisie', 'soccer_brazil_campeonato', 'soccer_usa_mls', 
               'soccer_portugal_primeira_liga', 'soccer_argentina_j_p']

    for sport in REGIONS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals,spreads', 'oddsFormat': 'decimal'}
        try:
            data = requests.get(url, params=params).json()
            for m in data:
                home, away = m['home_team'], m['away_team']
                start_time = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                if now < start_time < now + timedelta(hours=24):
                    diff = start_time - now
                    countdown = f"{int(diff.total_seconds() // 3600)}h {int((diff.total_seconds() % 3600) // 60)}p"
                    
                    # Logic lấy mẫu linh hoạt 1-4 trận
                    match_avg = None
                    sample_size = 0
                    if hist_df is not None:
                        h_data = hist_df[(hist_df['HomeTeam'] == home) | (hist_df['AwayTeam'] == home)].tail(4)
                        a_data = hist_df[(hist_df['HomeTeam'] == away) | (hist_df['AwayTeam'] == away)].tail(4)
                        combined = pd.concat([h_data, a_data])
                        if not combined.empty:
                            sample_size = len(combined)
                            match_avg = combined['Avg>2.5'].mean()

                    analyze_flexible(m, home, away, start_time, countdown, match_avg, sample_size)
        except: continue

def analyze_flexible(match, home, away, start_time, countdown, match_avg, sample_size):
    bm = match['bookmakers'][0]
    mkts = {mk['key']: mk for mk in bm['markets']}
    
    if 'totals' in mkts:
        line = mkts['totals']['outcomes'][0]['point']
        o_p, u_p = mkts['totals']['outcomes'][0]['price'], mkts['totals']['outcomes'][1]['price']
        
        # CHÂN KINH 1: SOI BẪY (CÓ LỊCH SỬ)
        if match_avg is not None:
            gap = line - match_avg
            if gap < -0.4 and o_p >= 2.05:
                fire_msg(home, away, "XỈU", line, u_p, f"💣 BẪY TÀI ({sample_size} trận)", start_time, countdown)
            elif gap > 0.4 and u_p >= 2.05:
                fire_msg(home, away, "TÀI", line, o_p, f"⚠️ BẪY XỈU ({sample_size} trận)", start_time, countdown)

        # CHÂN KINH 2: TIỀN ÉP (LUÔN QUÉT - ƯU TIÊN CAO)
        if o_p < 1.78:
            fire_msg(home, away, "TÀI", line, o_p, "🔥 TIỀN ÉP TÀI (SẬP ODD)", start_time, countdown)
        elif u_p < 1.78:
            fire_msg(home, away, "XỈU", line, u_p, "❄️ TIỀN ÉP XỈU (SẬP ODD)", start_time, countdown)

def fire_msg(home, away, side, line, odd, tag, start_time, countdown):
    msg = (f"🏪 *SHARK RADAR*\n🏟️ {home} vs {away}\n🎯 Lệnh: *VẢ {side} {line}*\n"
           f"🚩 Tín hiệu: {tag}\n💰 Odd: {odd}\n⏰ {start_time.strftime('%H:%M')} (Còn {countdown})")
    send_tele_msg(msg)
    pd.DataFrame([[start_time, f"{home}-{away}", side, line, odd, tag, "WAITING"]]).to_csv(MEMORY_FILE, mode='a', header=False, index=False)

if __name__ == "__main__":
    shark_scanner()
