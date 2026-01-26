import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- CẤU HÌNH HỆ THỐNG ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"
LOG_FILE = "shark_history_log.csv"

# FULL 20+ NGUỒN DỮ LIỆU ĐỐI ĐẦU (H2H)
SOURCES = {
    "ENG": ["E0", "E1", "E2", "E3"], # Ngoại hạng -> Hạng 3 Anh
    "GER": ["D1", "D2"],             # Đức 1, 2
    "SPA": ["SP1", "SP2"],           # TBN 1, 2
    "ITA": ["I1", "I2"],             # Ý 1, 2
    "FRA": ["F1", "F2"],             # Pháp 1, 2
    "SCO": ["SC0", "SC1"],           # Scotland
    "EURO": ["N1", "B1", "P1", "T1", "G1"], # Hà Lan, Bỉ, Bồ, Thổ, Hy Lạp
    "AMERICA": ["BRA.csv", "ARG.csv", "MEX.csv", "USA.csv"], 
    "ASIA": ["JPN.csv", "CHN.csv"],
    "GLOBAL": ["new_fixtures.csv"]
}

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
        return r.status_code == 200
    except: return False

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

def verify_results(db):
    if not os.path.exists(LOG_FILE) or db is None: return
    logs = pd.read_csv(LOG_FILE)
    if logs.empty: return
    updated = False
    # Lấy danh sách chờ kết quả
    for idx, row in logs[logs['Result'] == 'WAITING'].iterrows():
        # Tìm trận đấu trong database (khớp 4 ký tự đầu tên đội)
        match_data = db[db['HomeTeam'].str.contains(str(row['Match']).split(' vs ')[0][:4], na=False, case=False)].head(1)
        if not match_data.empty and not pd.isna(match_data.iloc[0]['FTHG']):
            hg, ag = int(match_data.iloc[0]['FTHG']), int(match_data.iloc[0]['FTAG'])
            total = hg + ag
            res_text = "GÃY ❌"
            
            # Kiểm tra HÚP/GÃY (Mặc định line 2.5 cho Tài Xỉu)
            if "TÀI" in row['Action'] and total > 2.5: res_text = "HÚP ✅"
            elif "XỈU" in row['Action'] and total < 2.5: res_text = "HÚP ✅"
            
            logs.at[idx, 'Result'] = res_text
            send_tele(f"📊 *XÁC NHẬN KẾT QUẢ:*\n⚽ {row['Match']}\n🎬 Tỉ số: {hg}-{ag}\n💰 Trạng thái: *{res_text}*")
            updated = True
    if updated: logs.to_csv(LOG_FILE, index=False)

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    
    # TIN NHẮN THÔNG NÒNG
    send_tele(f"📡 *SHARK ONLINE:* {now_vn.strftime('%H:%M:%S')}\n✅ Trạng thái: Đang quét Full 18+ nguồn...")

    full_db = get_full_db()
    
    # 1. TỰ ĐỘNG KIỂM TRA HÚP/GÃY
    verify_results(full_db)

    # 2. QUÉT KÈO MỚI (PHÂN TÍCH CHÂN KINH)
    API_KEYS = [
        'soccer_epl', 'soccer_efl_championship', 'soccer_england_league1', 'soccer_england_league2',
        'soccer_germany_bundesliga', 'soccer_germany_bundesliga2', 'soccer_spain_la_liga',
        'soccer_italy_serie_a', 'soccer_italy_serie_b', 'soccer_brazil_campeonato',
        'soccer_japan_j_league', 'soccer_usa_mls', 'soccer_mexico_liga_mx'
    ]
    
    new_bets = []
    for sport in API_KEYS:
        try:
            url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
            data = requests.get(url, params={'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals', 'oddsFormat': 'decimal'}).json()
            
            for m in data:
                home, away = m['home_team'], m['away_team']
                st = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                # Quét kèo trong 18 tiếng tới
                if now_vn < st < now_vn + timedelta(hours=18):
                    # Tính toán H2H
                    h2h = full_db[((full_db['HomeTeam'].str.contains(home[:4], case=False)) & (full_db['AwayTeam'].str.contains(away[:4], case=False))) | 
                                  ((full_db['HomeTeam'].str.contains(away[:4], case=False)) & (full_db['AwayTeam'].str.contains(home[:4], case=False)))].tail(4)
                    avg_g = h2h['FTHG'].add(h2h['FTAG']).mean() if not h2h.empty else 2.5
                    
                    mkts = {mk['key']: mk for mk in m['bookmakers'][0]['markets']}
                    if 'totals' in mkts:
                        o_p, u_p = mkts['totals']['outcomes'][0]['price'], mkts['totals']['outcomes'][1]['price']
                        
                        action, reason = "---", ""
                        
                        # CHÂN KINH 1: VẢ MẠNH (Hội tụ Dụ + Ép)
                        if avg_g >= 3.2 and o_p > 2.15 and u_p < 1.78:
                            action, reason = "💣 VẢ MẠNH XỈU", "Dụ Tài (H2H cao) + Tiền ép Xỉu"
                        elif avg_g <= 1.8 and u_p > 2.15 and o_p < 1.78:
                            action, reason = "💣 VẢ MẠNH TÀI", "Dụ Xỉu (H2H thấp) + Tiền ép Tài"
                        
                        # CHÂN KINH 2: BẺ DỤ (Trap)
                        elif avg_g >= 3.5 and o_p > 2.10:
                            action, reason = "VẢ XỈU ❄️", "Bẻ Dụ Tài (Odd cao bất thường)"
                        elif avg_g <= 1.5 and u_p > 2.10:
                            action, reason = "VẢ TÀI 🔥", "Bẻ Dụ Xỉu (Odd cao bất thường)"
                            
                        # CHÂN KINH 3: TIỀN ÉP (Dòng tiền sập)
                        elif o_p < 1.65:
                            action, reason = "VẢ TÀI 🔥", "Dòng tiền ép mạnh cửa Tài"
                        elif u_p < 1.65:
                            action, reason = "VẢ XỈU ❄️", "Dòng tiền ép mạnh cửa Xỉu"

                        if action != "---":
                            send_tele(f"💎 *GỢI Ý VẢ:* {home} vs {away}\n🎯 Lệnh: *{action}*\n📝 Lý do: _{reason}_\n📊 H2H: {avg_g:.1f} bàn\n⏰ Đá lúc: {st.strftime('%H:%M')}")
                            new_bets.append({"Match": f"{home} vs {away}", "Action": action, "Result": "WAITING"})
        except: continue

    # Lưu kèo vào log
    if new_bets:
        pd.DataFrame(new_bets).to_csv(LOG_FILE, mode='a', header=not os.path.exists(LOG_FILE), index=False)

if __name__ == "__main__":
    main()
