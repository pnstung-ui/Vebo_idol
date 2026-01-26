import requests
import pandas as pd
import os
from datetime import datetime, timedelta

# --- THÔNG TIN ĐỊNH DANH IDOL ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"
MEMORY_FILE = "shark_memory.csv"

def get_now_gmt7():
    return datetime.now() + timedelta(hours=7)

def shark_scanner():
    # Khởi tạo bộ nhớ nếu chưa có
    if not os.path.exists(MEMORY_FILE):
        pd.DataFrame(columns=['id', 'time', 'match', 'type', 'line', 'odd', 'trap', 'status']).to_csv(MEMORY_FILE, index=False)
    
    now = get_now_gmt7()
    # Quét đa giải: Anh, Đức, Ý, Tây Ban Nha, Hà Lan, Nam Mỹ (Brazil), Mỹ (MLS)
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
                
                if now < start_time < now + timedelta(hours=12):
                    diff = start_time - now
                    countdown = f"{int(diff.total_seconds() // 3600)}h {int((diff.total_seconds() % 3600) // 60)}p"
                    analyze_logic(m, home, away, start_time, countdown)
        except: continue

def analyze_logic(match, home, away, start_time, countdown):
    bm = match['bookmakers'][0]
    mkts = {mk['key']: mk for mk in bm['markets']}
    
    # 1. CHÂN KINH TÀI XỈU (Biến thiên & Tiền ép)
    if 'totals' in mkts:
        line = mkts['totals']['outcomes'][0]['point']
        o_p, u_p = mkts['totals']['outcomes'][0]['price'], mkts['totals']['outcomes'][1]['price']
        
        # Logic Tiền ép (Odd giữ nguyên, tiền tăng -> Odd giảm sâu)
        if o_p < 1.75: 
            send_and_log(home, away, "TÀI", line, o_p, "🔥 TIỀN ÉP TÀI", start_time, countdown)
        elif u_p < 1.75:
            send_and_log(home, away, "XỈU", line, u_p, "❄️ TIỀN ÉP XỈU", start_time, countdown)
            
        # Bẫy tâm lý (Dựa trên Odd nhử > 2.05 cho Line thấp/cao vô lý)
        if o_p >= 2.05 and line <= 2.25:
            send_and_log(home, away, "XỈU", line, u_p, "💣 BẪY DỤ TÀI (H2H ảo)", start_time, countdown)

    # 2. CHÂN KINH KÈO CHẤP (Thứ hạng & Bẫy dụ)
    if 'spreads' in mkts:
        h_line = mkts['spreads']['outcomes'][0]['point']
        h_p = mkts['spreads']['outcomes'][0]['price']
        if h_line >= -0.75 and h_p >= 2.05:
            send_and_log(home, away, "DƯỚI", h_line, mkts['spreads']['outcomes'][1]['price'], "🛡️ BẪY THỨ HẠNG (DỤ TRÊN)", start_time, countdown)

def send_and_log(home, away, side, line, odd, tag, start_time, countdown):
    msg = (f"🏪 *SHARK RADAR GMT+7*\n🏟️ {home} vs {away}\n🎯 Lệnh: *VẢ {side} {line}*\n"
           f"🚩 Tín hiệu: {tag}\n💰 Odd: {odd}\n⏰ Đá lúc: {start_time.strftime('%H:%M')} (Còn {countdown})")
    requests.post(f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage", json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    # Lưu vào CSV để Shark tự học kết quả HÚP/GÃY
    pd.DataFrame([[start_time, f"{home}-{away}", side, line, odd, tag, "WAITING"]]).to_csv(MEMORY_FILE, mode='a', header=False, index=False)

if __name__ == "__main__":
    shark_scanner()
