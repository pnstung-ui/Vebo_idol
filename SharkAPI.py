import requests
import pandas as pd
import io
import os
from datetime import datetime, timedelta

# --- CẤU HÌNH ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"
HIST_URL = "https://www.football-data.co.uk/new_fixtures.csv"

def send_tele(text):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def shark_scanner():
    now_vn = datetime.now() + timedelta(hours=7)
    # PHÁT SÚNG THÔNG NÒNG: Nếu dòng này không nổ Tele, nghĩa là Chat ID/Token sai
    send_tele(f"🚀 *SHARK RADAR 2026 GỌI IDOL!*\n⏰ Khởi động: {now_vn.strftime('%H:%M:%S')}\n📡 Trạng thái: Đang quét Chân Kinh...")

    # Tải lịch sử linh hoạt
    hist_df = None
    try:
        r = requests.get(HIST_URL, timeout=10)
        hist_df = pd.read_csv(io.StringIO(r.text))
    except: pass

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
                    
                    # Logic 1-4 trận
                    match_avg = None
                    if hist_df is not None:
                        combined = pd.concat([hist_df[(hist_df['HomeTeam']==home)|(hist_df['AwayTeam']==home)].tail(4),
                                            hist_df[(hist_df['HomeTeam']==away)|(hist_df['AwayTeam']==away)].tail(4)])
                        if not combined.empty: match_avg = combined['Avg>2.5'].mean()

                    # --- CHÂN KINH SO KÈO ---
                    # 1. TIỀN ÉP (Ưu tiên)
                    if o_p < 1.78:
                        fire(home, away, "TÀI", line, o_p, "🔥 TIỀN ÉP TÀI", st)
                    elif u_p < 1.78:
                        fire(home, away, "XỈU", line, u_p, "❄️ TIỀN ÉP XỈU", st)
                    
                    # 2. BẪY (Nếu có H2H)
                    if match_avg:
                        gap = line - match_avg
                        if gap < -0.4 and o_p >= 2.05:
                            fire(home, away, "XỈU", line, u_p, "💣 BẪY DỤ TÀI", st)
                        elif gap > 0.4 and u_p >= 2.05:
                            fire(home, away, "TÀI", line, o_p, "⚠️ BẪY DỤ XỈU", st)
        except: continue

def fire(home, away, side, line, odd, tag, st):
    msg = f"🏪 *SHARK RADAR*\n🏟️ {home} vs {away}\n🎯 Lệnh: *VẢ {side} {line}*\n🚩 {tag}\n💰 Odd: {odd}\n⏰ {st.strftime('%H:%M')}"
    send_tele(msg)

if __name__ == "__main__":
    shark_scanner()
