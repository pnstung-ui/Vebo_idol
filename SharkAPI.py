import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- CONFIG ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5Ofo7xw"
TELE_CHAT_ID = "957306386"
LOG_FILE = "shark_history_log.csv"

# KHÔI PHỤC FULL 100% NGUỒN DỮ LIỆU ĐỐI ĐẦU & THAM CHIẾU
SOURCES = {
    "ENG_1": "https://www.football-data.co.uk/mmz4281/2526/E0.csv",
    "ENG_2": "https://www.football-data.co.uk/mmz4281/2526/E1.csv",
    "ENG_3": "https://www.football-data.co.uk/mmz4281/2526/E2.csv",
    "GER_1": "https://www.football-data.co.uk/mmz4281/2526/D1.csv",
    "GER_2": "https://www.football-data.co.uk/mmz4281/2526/D2.csv",
    "SPA_1": "https://www.football-data.co.uk/mmz4281/2526/SP1.csv",
    "SPA_2": "https://www.football-data.co.uk/mmz4281/2526/SP2.csv",
    "ITA_1": "https://www.football-data.co.uk/mmz4281/2526/I1.csv",
    "ITA_2": "https://www.football-data.co.uk/mmz4281/2526/I2.csv",
    "FRA_1": "https://www.football-data.co.uk/mmz4281/2526/F1.csv",
    "FRA_2": "https://www.football-data.co.uk/mmz4281/2526/F2.csv",
    "NETH": "https://www.football-data.co.uk/mmz4281/2526/N1.csv",
    "BRAZIL": "https://www.football-data.co.uk/new/BRA.csv",
    "ARGENTINA": "https://www.football-data.co.uk/new/ARG.csv",
    "NORWAY": "https://www.football-data.co.uk/new/NOR.csv",
    "JAPAN": "https://www.football-data.co.uk/new/JPN.csv",
    "GLOBAL": "https://www.football-data.co.uk/new_fixtures.csv"
}

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def verify_results(db):
    if not os.path.exists(LOG_FILE) or db is None: return
    logs = pd.read_csv(LOG_FILE)
    if logs.empty: return
    
    for idx, row in logs[logs['Result'] == 'WAITING'].iterrows():
        match = db[(db['HomeTeam'].str.contains(str(row['Match']).split(' vs ')[0][:4], na=False, case=False))].head(1)
        if not match.empty and not pd.isna(match.iloc[0]['FTHG']):
            hg, ag = int(match.iloc[0]['FTHG']), int(match.iloc[0]['FTAG'])
            total = hg + ag
            status = "⏳"
            
            if "TÀI" in row['Action']: status = "✅ HÚP TÀI" if total > 2.5 else "❌ GÃY TÀI"
            elif "XỈU" in row['Action']: status = "✅ HÚP XỈU" if total < 2.5 else "❌ GÃY XỈU"
            
            if status != "⏳":
                send_tele(f"📊 *XÁC NHẬN KÈO:* {row['Match']}\n🎬 Tỷ số: {hg}-{ag}\n🔔 Trạng thái: *{status}*")
                logs.at[idx, 'Result'] = status
    logs.to_csv(LOG_FILE, index=False)

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    send_tele(f"🚀 *SHARK ULTIMATE V5.2:* Đang quét Full 17 nguồn + H2H + Verify...")

    all_dfs = []
    for name, url in SOURCES.items():
        try:
            r = requests.get(url, timeout=25)
            all_dfs.append(pd.read_csv(io.StringIO(r.text), on_bad_lines='skip', engine='python'))
        except: continue
    full_db = pd.concat(all_dfs, ignore_index=True) if all_dfs else None

    # 1. Kiểm tra kết quả phiên trước
    verify_results(full_db)

    # 2. Quét kèo mới diện rộng
    API_SPORTS = ['soccer_epl', 'soccer_efl_championship', 'soccer_england_league1', 'soccer_germany_bundesliga', 'soccer_germany_bundesliga2', 'soccer_spain_la_liga', 'soccer_spain_segunda_division', 'soccer_italy_serie_a', 'soccer_italy_serie_b', 'soccer_brazil_campeonato', 'soccer_japan_j_league', 'soccer_usa_mls', 'soccer_argentina_primera_division']
    
    new_records = []
    for sport in API_SPORTS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        try:
            data = requests.get(url, params={'apiKey': API_KEY, 'regions': 'eu', 'markets': 'spreads,totals', 'oddsFormat': 'decimal'}, timeout=15).json()
            for m in data:
                home, away = m['home_team'], m['away_team']
                st = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                if now_vn < st < now_vn + timedelta(hours=15):
                    # Tra H2H 4 trận
                    h2h = full_db[((full_db['HomeTeam'].str.contains(home[:4], case=False)) & (full_db['AwayTeam'].str.contains(away[:4], case=False))) | 
                                  ((full_db['HomeTeam'].str.contains(away[:4], case=False)) & (full_db['AwayTeam'].str.contains(home[:4], case=False)))].tail(4)
                    avg_g = h2h['FTHG'].add(h2h['FTAG']).mean() if not h2h.empty else 2.5
                    
                    bm = m['bookmakers'][0]
                    mkts = {mk['key']: mk for mk in bm['markets']}
                    
                    # Logic VẢ MẠNH (Hội tụ Dụ + Ép)
                    if 'totals' in mkts:
                        tx_line, lo_o, lo_u = mkts['totals']['outcomes'][0]['point'], mkts['totals']['outcomes'][0]['price'], mkts['totals']['outcomes'][1]['price']
                        action = "---"
                        if avg_g >= 3.0 and lo_o > 2.15 and lo_u < 1.80: action = "💣 VẢ MẠNH XỈU (Dụ Tài + Ép Xỉu)"
                        elif avg_g <= 2.0 and tx_line >= 2.5 and lo_o < 1.80: action = "💣 VẢ MẠNH TÀI (Dụ Xỉu + Ép Tài)"
                        elif lo_o < 1.75: action = "VẢ TÀI 🔥"
                        elif lo_u < 1.75: action = "VẢ XỈU ❄️"

                        if "VẢ" in action:
                            send_tele(f"💎 *KÈO:* {home} vs {away}\n🎯 Lệnh: *{action}*\n📊 H2H: {avg_g:.1f} | Odd: T{lo_o:.2f}-X{lo_u:.2f}\n⏰ {st.strftime('%H:%M')}")
                            new_records.append({"Date": now_vn, "Match": f"{home} vs {away}", "Action": action, "Result": "WAITING"})
        except: continue

    if new_records:
        pd.DataFrame(new_records).to_csv(LOG_FILE, mode='a', header=not os.path.exists(LOG_FILE), index=False)

if __name__ == "__main__":
    main()
