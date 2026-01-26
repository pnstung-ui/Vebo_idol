import requests
import pandas as pd
import os
from datetime import datetime, timedelta

# --- CẤU HÌNH ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"
DATA_FILE = "shark_memory.csv"

def get_now_gmt7():
    return datetime.now() + timedelta(hours=7)

def init_memory():
    if not os.path.exists(DATA_FILE):
        df = pd.DataFrame(columns=['id', 'time', 'match', 'type', 'line', 'odd', 'trap', 'status'])
        df.to_csv(DATA_FILE, index=False)

def learning_engine():
    """Tự học: Nếu lịch sử thua nhiều, siết chặt Odd lại"""
    try:
        df = pd.read_csv(DATA_FILE)
        wins = len(df[df['status'] == 'WIN'])
        losses = len(df[df['status'] == 'LOSS'])
        if losses > wins and losses > 0:
            return 1.70  # Siết chặt (Tiền phải ép cực mạnh)
        return 1.80 # Ngưỡng chuẩn
    except: return 1.80

def shark_scanner():
    init_memory()
    threshold = learning_engine()
    now = get_now_gmt7()
    
    # Danh sách giải
    REGIONS = ['soccer_epl', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 'soccer_spain_la_liga', 'soccer_netherlands_ere_divisie']

    for sport in REGIONS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals,spreads', 'oddsFormat': 'decimal'}
        
        try:
            r = requests.get(url).json()
            for m in r:
                home, away = m['home_team'], m['away_team']
                start_time = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                if now < start_time < now + timedelta(hours=12):
                    diff = start_time - now
                    countdown = f"{int(diff.total_seconds() // 3600)}h {int((diff.total_seconds() % 3600) // 60)}p"
                    
                    analyze_final(m, home, away, start_time, countdown, threshold)
        except: continue

def analyze_final(match, home, away, start_time, countdown, threshold):
    bm = match['bookmakers'][0]
    mkts = {mk['key']: mk for mk in bm['markets']}
    
    # 1. TÀI XỈU BIẾN THIÊN & BẪY H2H
    if 'totals' in mkts:
        line = mkts['totals']['outcomes'][0]['point']
        o_p = mkts['totals']['outcomes'][0]['price']
        u_p = mkts['totals']['outcomes'][1]['price']
        
        # CHÂN KINH: Odd giảm sâu (Tiền ép)
        if o_p < threshold:
            send_final_msg(home, away, "TÀI", line, o_p, "🔥 TIỀN ÉP", start_time, countdown)
        elif u_p < threshold:
            send_final_msg(home, away, "XỈU", line, u_p, "❄️ TIỀN ÉP", start_time, countdown)

    # 2. KÈO CHẤP & BẪY THỨ HẠNG
    if 'spreads' in mkts:
        h_line = mkts['spreads']['outcomes'][0]['point']
        h_p = mkts['spreads']['outcomes'][0]['price']
        
        # BẪY DỤ TRÊN (Theo Chân kinh thứ hạng)
        if h_line >= -0.75 and h_p >= 2.05:
            send_final_msg(home, away, "DƯỚI", h_line, h_p, "💣 BẪY THỨ HẠNG", start_time, countdown)

def send_final_msg(home, away, side, line, odd, tag, start_time, countdown):
    msg = (f"🏪 *SHARK AI RADAR*\n"
           f"🏟️ Trận: {home} vs {away}\n"
           f"🎯 Lệnh: *VẢ {side} {line}*\n"
           f"🚩 Tín hiệu: {tag}\n"
           f"💰 Odd: {odd}\n"
           f"⏰ Đá lúc: {start_time.strftime('%H:%M')} (Sau {countdown})\n"
           f"📢 Múi giờ: GMT+7")
    
    requests.post(f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage", 
                  json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    
    # Lưu vào bộ nhớ để học
    df = pd.DataFrame([[start_time, f"{home}-{away}", side, line, odd, tag, 'WAITING']])
    df.to_csv(DATA_FILE, mode='a', header=False, index=False)

if __name__ == "__main__":
    shark_scanner()
