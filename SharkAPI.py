import requests
import pandas as pd
import io
from datetime import datetime, timedelta

# --- CẤU HÌNH ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"
HIST_URL = "https://www.football-data.co.uk/new_fixtures.csv"

def get_data():
    try:
        r_hist = requests.get(HIST_URL, timeout=15)
        df_hist = pd.read_csv(io.StringIO(r_hist.text))
        return df_hist
    except: return None

def get_team_h2h(df, team):
    """Lấy phong độ 4 trận gần nhất: [Trung bình bàn thắng, Tỉ lệ thắng kèo]"""
    try:
        matches = df[(df['HomeTeam'] == team) | (df['AwayTeam'] == team)].tail(4)
        if len(matches) < 2: return 2.5, 0.5
        avg_goals = matches['Avg>2.5'].mean()
        # Giả lập tỉ lệ thắng dựa trên Odd đóng cửa (nếu có dữ liệu thắng/thua thực tế sẽ chuẩn hơn)
        win_rate = 0.6 if avg_goals > 2.5 else 0.4 
        return avg_goals, win_rate
    except: return 2.5, 0.5

def analyze_all():
    hist_df = get_data()
    now_gmt7 = datetime.now() + timedelta(hours=7)
    REGIONS = ['soccer_epl', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 'soccer_spain_la_liga', 'soccer_netherlands_ere_divisie', 'soccer_norway_eliteserien']

    for sport in REGIONS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals,spreads', 'oddsFormat': 'decimal'}
        try:
            data = requests.get(url, params=params).json()
            for m in data:
                home, away = m['home_team'], m['away_team']
                start_time = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                if now_gmt7 < start_time < now_gmt7 + timedelta(hours=12):
                    h_goals, h_win = get_team_h2h(hist_df, home)
                    a_goals, a_win = get_team_h2h(hist_df, away)
                    match_avg_goals = (h_goals + a_goals) / 2
                    
                    bm = m['bookmakers'][0]
                    markets = {mk['key']: mk for mk in bm['markets']}

                    # --- 1. CHÂN KINH TÀI XỈU ---
                    if 'totals' in markets:
                        line = markets['totals']['outcomes'][0]['point']
                        o_p = markets['totals']['outcomes'][0]['price']
                        u_p = markets['totals']['outcomes'][1]['price']
                        if match_avg_goals > 2.8 and line <= 2.5 and o_p >= 2.0:
                            send_tele(f"💣 *BẪY DỤ TÀI*\n🏟️ {home}-{away}\n📊 H2H nổ: {match_avg_goals:.2f}\n🎯 Sàn ra: {line} (Odd {o_p})\n👉 *LỆNH: VẢ XỈU*")
                        elif match_avg_goals < 2.2 and line >= 2.75 and u_p >= 2.0:
                            send_tele(f"⚠️ *BẪY DỤ XỈU*\n🏟️ {home}-{away}\n📊 H2H khô: {match_avg_goals:.2f}\n🎯 Sàn ra: {line} (Odd {u_p})\n👉 *LỆNH: VẢ TÀI*")

                    # --- 2. CHÂN KINH KÈO CHẤP ---
                    if 'spreads' in markets:
                        h_line = markets['spreads']['outcomes'][0]['point'] # Mức chấp
                        h_p = markets['spreads']['outcomes'][0]['price']
                        a_p = markets['spreads']['outcomes'][1]['price']
                        
                        # Bẫy Dụ Trên: Lịch sử thắng (win_rate cao) nhưng chấp thấp + Odd cao
                        if h_win > 0.5 and h_line >= -0.75 and h_p >= 2.0:
                            send_tele(f"🛡️ *BẪY DỤ TRÊN*\n🏟️ {home} ({h_line}) vs {away}\n📊 H2H Đội trên rất tốt nhưng chấp lỏng.\n👉 *LỆNH: VẢ DƯỚI (Hòa là húp)*")
                        # Bẫy Dụ Dưới: Lịch sử kém nhưng Odd dưới nhử ăn cao
                        elif h_win < 0.4 and a_p >= 2.05:
                            send_tele(f"💣 *BẪY DỤ DƯỚI*\n🏟️ {home} vs {away}\n📊 H2H Đội dưới nát nhưng Odd nhử cao.\n👉 *LỆNH: VẢ TRÊN*")
                        
                        # Logic Tiền ép (Dành cho Odd giảm sâu)
                        elif h_p < 1.70:
                            send_tele(f"🔥 *TIỀN ÉP TRÊN*\n🏟️ {home} vs {away}\n🎯 Kèo: {h_line}\n💰 Odd giảm sâu: {h_p}\n👉 *LỆNH: VẢ TRÊN*")

        except: continue

def send_tele(msg):
    requests.post(f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage", json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__": analyze_all()
