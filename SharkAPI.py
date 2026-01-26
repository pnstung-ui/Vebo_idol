import requests
import pandas as pd
import io
import os
from datetime import datetime, timedelta

# --- THÔNG TIN ĐỊNH DANH CỦA IDOL ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"
MEMORY_FILE = "shark_memory.csv"
HIST_URL = "https://www.football-data.co.uk/new_fixtures.csv"

def send_tele_msg(text):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    payload = {"chat_id": TELE_CHAT_ID, "text": text, "parse_mode": "Markdown"}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def shark_scanner():
    # PHÁT SÚNG THÔNG NÒNG (Để Idol biết Bot đang chạy)
    now_vn = datetime.now() + timedelta(hours=7)
    send_tele_msg(f"🚀 *SHARK RADAR:* Đã khởi động lúc {now_vn.strftime('%H:%M:%S')}\n📡 Đang quét các giải: Anh, Đức, Ý, Tây Ban Nha, Brazil, Mỹ...")

    # Khởi tạo bộ nhớ
    if not os.path.exists(MEMORY_FILE):
        pd.DataFrame(columns=['time', 'match', 'side', 'line', 'odd', 'tag', 'status']).to_csv(MEMORY_FILE, index=False)
    
    # Tải dữ liệu lịch sử (Linh hoạt 1-4 trận)
    hist_df = None
    try:
        r = requests.get(HIST_URL, timeout=15)
        hist_df = pd.read_csv(io.StringIO(r.text))
    except: pass

    # Danh sách các giải đấu
    REGIONS = ['soccer_epl', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 'soccer_spain_la_liga', 
               'soccer_netherlands_ere_divisie', 'soccer_brazil_campeonato', 'soccer_usa_mls', 'soccer_portugal_primeira_liga']

    for sport in REGIONS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals,spreads', 'oddsFormat': 'decimal'}
        try:
            r = requests.get(url, params=params).json()
            for m in r:
                home, away = m['home_team'], m['away_team']
                start_time = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                # Soi trận trong vòng 18 tiếng tới
                if now_vn < start_time < now_vn + timedelta(hours=18):
                    diff = start_time - now_vn
                    countdown = f"{int(diff.total_seconds() // 3600)}h {int((diff.total_seconds() % 3600) // 60)}p"
                    
                    # Tính toán H2H linh hoạt (1-4 trận)
                    match_avg = None
                    sample_size = 0
                    if hist_df is not None:
                        h_data = hist_df[(hist_df['HomeTeam'] == home) | (hist_df['AwayTeam'] == home)].tail(4)
                        a_data = hist_df[(hist_df['HomeTeam'] == away) | (hist_df['AwayTeam'] == away)].tail(4)
                        combined = pd.concat([h_data, a_data])
                        if not combined.empty:
                            sample_size = len(combined)
                            match_avg = combined['Avg>2.5'].mean()

                    analyze_logic(m, home, away, start_time, countdown, match_avg, sample_size)
        except: continue

def analyze_logic(match, home, away, start_time, countdown, match_avg, sample_size):
    bm = match['bookmakers'][0]
    mkts = {mk['key']: mk for mk in bm['markets']}
    
    if 'totals' in mkts:
        line = mkts['totals']['outcomes'][0]['point']
        o_p, u_p = mkts['totals']['outcomes'][0]['price'], mkts['totals']['outcomes'][1]['price']
        
        # 1. TIỀN ÉP (Ưu tiên số 1 - Odd sập dưới 1.78)
        if o_p < 1.78:
            fire(home, away, "TÀI", line, o_p, "🔥 TIỀN ÉP TÀI (SẬP ODD)", start_time, countdown)
        elif u_p < 1.78:
            fire(home, away, "XỈU", line, u_p, "❄️ TIỀN ÉP XỈU (SẬP ODD)", start_time, countdown)
            
        # 2. BẪY DỤ (Nếu có lịch sử)
        if match_avg is not None:
            gap = line - match_avg
            if gap < -0.4 and o_p >= 2.05:
                fire(home, away, "XỈU", line, u_p, f"💣 BẪY TÀI ({sample_size} trận)", start_time, countdown)
            elif gap > 0.4 and u_p >= 2.05:
                fire(home, away, "TÀI", line, o_p, f"⚠️ BẪY XỈU ({sample_size} trận)", start_time, countdown)

def fire(home, away, side, line, odd, tag, start_time, countdown):
    msg = (f"🏪 *SHARK RADAR*\n🏟️ {home} vs {away}\n🎯 Lệnh: *VẢ {side} {line}*\n"
           f"🚩 Tín hiệu: {tag}\n💰 Odd: {odd}\n⏰ {start_time.strftime('%H:%M')} (Còn {countdown})")
    send_tele_msg(msg)
    # Lưu vào CSV để Shark_Checker báo HÚP/GÃY
    pd.DataFrame([[start_time, f"{home}-{away}", side, line, odd, tag, "WAITING"]]).to_csv(MEMORY_FILE, mode='a', header=False, index=False)

if __name__ == "__main__":
    shark_scanner()
