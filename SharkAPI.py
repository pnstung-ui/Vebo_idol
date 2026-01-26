import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- CONFIG ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"
LOG_FILE = "shark_history_log.csv"

# FULL 25+ NGUỒN DỮ LIỆU TỪ HẠNG 1 ĐẾN HẠNG 3 & GIẢI CỎ TOÀN CẦU
SOURCES = {
    "ENG": ["E0", "E1", "E2", "E3"], # Ngoại hạng, Hạng nhất, Hạng 2, Hạng 3 Anh
    "GER": ["D1", "D2"],             # Đức 1, Đức 2
    "SPA": ["SP1", "SP2"],           # TBN 1, TBN 2
    "ITA": ["I1", "I2"],             # Ý 1, Ý 2
    "FRA": ["F1", "F2"],             # Pháp 1, Pháp 2
    "SCO": ["SC0", "SC1"],           # Scotland 1, 2
    "EURO": ["N1", "B1", "P1", "T1", "G1"], # Hà Lan, Bỉ, Bồ Đào Nha, Thổ Nhĩ Kỳ, Hy Lạp
    "AMERICA": ["BRA.csv", "ARG.csv", "MEX.csv", "USA.csv"], # Nam Mỹ & Mỹ
    "ASIA": ["JPN.csv", "CHN.csv"]    # Nhật, Trung Quốc
}

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def get_full_db():
    all_dfs = []
    base_url = "https://www.football-data.co.uk/mmz4281/2526/"
    new_url = "https://www.football-data.co.uk/new/"
    
    for country, files in SOURCES.items():
        for f in files:
            url = f"{base_url}{f}.csv" if len(f) <= 3 else f"{new_url}{f}"
            try:
                r = requests.get(url, timeout=15)
                if r.status_code == 200:
                    all_dfs.append(pd.read_csv(io.StringIO(r.text), on_bad_lines='skip', engine='python'))
            except: continue
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else None

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    send_tele(f"🏗️ *SHARK V7:* Đang càn quét Hạng 1-2-3 & Giải cỏ toàn cầu...")

    full_db = get_full_db()
    
    # 1. TỰ ĐỘNG CHECK HÚP/GÃY
    if full_db is not None and os.path.exists(LOG_FILE):
        logs = pd.read_csv(LOG_FILE)
        updated = False
        for idx, row in logs[logs['Result'] == 'WAITING'].iterrows():
            match_data = full_db[full_db['HomeTeam'].str.contains(str(row['Match']).split(' vs ')[0][:4], na=False, case=False)].head(1)
            if not match_data.empty and not pd.isna(match_data.iloc[0]['FTHG']):
                hg, ag = int(match_data.iloc[0]['FTHG']), int(match_data.iloc[0]['FTAG'])
                res = "HÚP ✅" if (("TÀI" in row['Action'] and hg+ag > 2.5) or ("XỈU" in row['Action'] and hg+ag < 2.5)) else "GÃY ❌"
                logs.at[idx, 'Result'] = res
                send_tele(f"📊 *KẾT QUẢ:* {row['Match']}\n🎬 {hg}-{ag} | *{res}*")
                updated = True
        if updated: logs.to_csv(LOG_FILE, index=False)

    # 2. QUÉT API DIỆN RỘNG (GỒM CÁC GIẢI HẠNG DƯỚI)
    API_KEYS_SOCCER = [
        'soccer_epl', 'soccer_efl_championship', 'soccer_england_league1', 'soccer_england_league2',
        'soccer_germany_bundesliga', 'soccer_germany_bundesliga2', 'soccer_germany_3_liga',
        'soccer_spain_la_liga', 'soccer_spain_segunda_division',
        'soccer_italy_serie_a', 'soccer_italy_serie_b',
        'soccer_france_ligue1', 'soccer_france_ligue2',
        'soccer_brazil_campeonato', 'soccer_japan_j_league', 'soccer_mexico_liga_mx', 'soccer_usa_mls'
    ]

    new_bets = []
    for sport in API_KEYS_SOCCER:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
            data = requests.get(url, params={'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals'}).json()
            for m in data:
                home, away = m['home_team'], m['away_team']
                st = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                if now_vn < st < now_vn + timedelta(hours=18):
                    # Phân tích H2H
                    h2h = full_db[((full_db['HomeTeam'].str.contains(home[:4], case=False)) & (full_db['AwayTeam'].str.contains(away[:4], case=False))) | 
                                  ((full_db['HomeTeam'].str.contains(away[:4], case=False)) & (full_db['AwayTeam'].str.contains(home[:4], case=False)))].tail(4)
                    avg_g = h2h['FTHG'].add(h2h['FTAG']).mean() if not h2h.empty else 2.5
                    
                    mkts = {mk['key']: mk for mk in m['bookmakers'][0]['markets']}
                    if 'totals' in mkts:
                        o_p, u_p = mkts['totals']['outcomes'][0]['price'], mkts['totals']['outcomes'][1]['price']
                        
                        action, reason = "---", ""
                        # ÁP DỤNG CHÂN KINH CHO GIẢI CỎ
                        if avg_g >= 3.2 and o_p > 2.18 and u_p < 1.78:
                            action, reason = "💣 VẢ MẠNH XỈU", "Bẫy Dụ Tài (Sử nổ + Tiền ép Xỉu)"
                        elif avg_g <= 1.8 and u_p > 2.18 and o_p < 1.78:
                            action, reason = "💣 VẢ MẠNH TÀI", "Bẫy Dụ Xỉu (Sử khô + Tiền ép Tài)"
                        elif o_p < 1.68:
                            action, reason = "VẢ TÀI 🔥", "Tiền ép (Cửa Tài sập sâu)"
                        elif u_p < 1.68:
                            action, reason = "VẢ XỈU ❄️", "Tiền ép (Cửa Xỉu sập sâu)"

                        if action != "---":
                            send_tele(f"💎 *GỢI Ý:* {home} vs {away}\n🎯 Lệnh: *{action}*\n📝 Lý do: _{reason}_\n📊 H2H: {avg_g:.1f} | ⏰ {st.strftime('%H:%M')}")
                            new_bets.append({"Match": f"{home} vs {away}", "Action": action, "Result": "WAITING"})
        except: continue

    if new_bets: pd.DataFrame(new_bets).to_csv(LOG_FILE, mode='a', header=not os.path.exists(LOG_FILE), index=False)

if __name__ == "__main__": main()
