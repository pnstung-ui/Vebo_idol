import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- CẤU HÌNH ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c" # API lấy Odd Real-time
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5Ofo7xw"
TELE_CHAT_ID = "957306386"
HIST_URL = "https://www.football-data.co.uk/new_fixtures.csv"

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except: pass

def main():
    now_gmt7 = datetime.now() + timedelta(hours=7)
    send_tele(f"🚀 *VEBO HYBRID:* Đang kết hợp API & Lịch sử...")

    # 1. Tải lịch sử 4 trận từ CSV (Để soi Bẫy)
    hist_df = None
    try:
        r = requests.get(HIST_URL, timeout=15)
        hist_df = pd.read_csv(io.StringIO(r.text))
    except: pass

    # 2. Lấy Odd biến động Real-time từ API
    # Quét các giải hot đang diễn ra hoặc sắp đá
    REGIONS = ['soccer_epl', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 'soccer_spain_la_liga', 'soccer_brazil_campeonato', 'soccer_usa_mls']
    
    for sport in REGIONS:
        api_url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals', 'oddsFormat': 'decimal'}
        try:
            odds_data = requests.get(api_url, params=params).json()
            for m in odds_data:
                home, away = m['home_team'], m['away_team']
                st = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                # Soi trong vòng 12 tiếng tới
                if now_gmt7 < st < now_gmt7 + timedelta(hours=12):
                    bm = m['bookmakers'][0] # Lấy nhà cái đầu tiên (thường là Pinnacle/Bet365)
                    mkt = bm['markets'][0]
                    line = mkt['outcomes'][0]['point']
                    o_p, u_p = mkt['outcomes'][0]['price'], mkt['outcomes'][1]['price']
                    
                    # --- LOGIC CHÂN KINH KẾT HỢP ---
                    action, trap = "---", "---"
                    
                    # Lấy trung bình bàn thắng từ lịch sử (CSV)
                    match_avg = 2.5
                    if hist_df is not None:
                        combined = pd.concat([hist_df[(hist_df['HomeTeam']==home)|(hist_df['AwayTeam']==home)].tail(4),
                                            hist_df[(hist_df['HomeTeam']==away)|(hist_df['AwayTeam']==away)].tail(4)])
                        if not combined.empty: match_avg = combined['Avg>2.5'].mean()

                    # BẮT BẪY (TRAP)
                    gap = line - match_avg
                    if gap < -0.4 and o_p >= 2.0: trap = "⚠️ DỤ TÀI (Sàn thấp hơn lịch sử)"
                    elif gap > 0.4 and u_p >= 2.0: trap = "⚠️ DỤ XỈU (Sàn cao hơn lịch sử)"

                    # BẮT BIẾN ĐỘNG (REAL-TIME API)
                    # Theo nguyên tắc Idol: Odd tăng -> Tài, Tiền giảm (Odd thấp) -> Xỉu
                    if o_p < 1.75: 
                        action = "VẢ TÀI 🔥 (Tiền ép mạnh)"
                    elif u_p < 1.75: 
                        action = "VẢ XỈU ❄️ (Tiền ép mạnh)"
                        if "DỤ TÀI" in trap: action = "💣 VẢ XỈU (Bẻ bẫy Dụ Tài)"
                    
                    # Thêm điều kiện Odd tăng
                    if o_p > 2.15: action = "VẢ TÀI 🔥 (Odd tăng)"

                    if action != "---":
                        diff = int((st - now_gmt7).total_seconds() / 60)
                        msg = (f"🏟️ *{home} vs {away}*\n"
                               f"🎯 Lệnh: *{action}*\n"
                               f"🚩 Bẫy: {trap}\n"
                               f"📊 Odd {line}: T{o_p:.2f} | X{u_p:.2f}\n"
                               f"📈 H2H Avg: {match_avg:.2f}\n"
                               f"⏰ Còn {diff}p")
                        send_tele(msg)
        except: continue

if __name__ == "__main__":
    main()
