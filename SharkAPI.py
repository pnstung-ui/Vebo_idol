import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- CẤU HÌNH ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "7981423606:AAFvJ5Xin_L62k-q0lKY8BPpoOa4PSoE7Ys"
TELE_CHAT_ID = "957306386"
DB_FILE = "shark_master_log.csv"

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except: pass

# --- PHẦN 1: LẤY DỮ LIỆU & RANKING (V52) ---
def get_real_data_and_rankings():
    sources = ["E0", "E1", "E2", "E3", "D1", "D2", "SP1", "SP2", "I1", "I2", "F1", "F2", "N1", "N2", "B1", "B2", "P1", "T1", "G1", "BRA.csv", "ARG.csv"]
    all_dfs = []
    for s in sources:
        url = f"https://www.football-data.co.uk/new/{s}" if ".csv" in s else f"https://www.football-data.co.uk/mmz4281/2526/{s}.csv"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                all_dfs.append(df[['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']])
        except: continue
    full_db = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    teams = pd.concat([full_db['HomeTeam'], full_db['AwayTeam']]).unique()
    table = {team: 0 for team in teams if pd.notna(team)}
    for _, row in full_db.iterrows():
        try:
            if row['FTR'] == 'H': table[row['HomeTeam']] += 3
            elif row['FTR'] == 'A': table[row['AwayTeam']] += 3
            else: table[row['HomeTeam']] += 1; table[row['AwayTeam']] += 1
        except: continue
    rankings = {team: r + 1 for r, (team, pts) in enumerate(sorted(table.items(), key=lambda x: x[1], reverse=True))}
    return full_db, rankings

def find_rank(team_name, rankings):
    if team_name in rankings: return rankings[team_name]
    for k in rankings:
        if k in team_name or team_name in k or k[:4] == team_name[:4]: return rankings[k]
    return None

# --- PHẦN 2: LƯU TRỮ & ĐỐI CHIẾU (V57) ---
def save_trap_log(home, away, trap_type, pick, line):
    new_entry = pd.DataFrame([{'Time': (datetime.now() + timedelta(hours=7)).strftime('%H:%M %d/%m'), 'Match': f"{home} vs {away}", 'Trap': trap_type, 'Pick': pick, 'Line': line, 'Status': 'WAITING'}])
    if not os.path.isfile(DB_FILE): new_entry.to_csv(DB_FILE, index=False)
    else: new_entry.to_csv(DB_FILE, mode='a', header=False, index=False)

def audit_results():
    if not os.path.isfile(DB_FILE): return
    df = pd.read_csv(DB_FILE)
    waiting = df[df['Status'] == 'WAITING']
    if waiting.empty: return
    try:
        scores = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/scores/?daysFrom=1&apiKey={API_KEY}").json()
        report = "📝 *ĐỐI CHIẾU KẾT QUẢ BẪY*\n"
        has_up = False
        for s in scores:
            if s.get('completed'):
                m_name = f"{s['home_team']} vs {s['away_team']}"
                idx = df[df['Match'] == m_name].index
                if not idx.empty and df.loc[idx[0], 'Status'] == 'WAITING':
                    h_s, a_s = int(s['scores'][0]['score']), int(s['scores'][1]['score'])
                    pick, line = df.loc[idx[0], 'Pick'], float(df.loc[idx[0], 'Line'])
                    win = False
                    if "XỈU" in pick and (h_s+a_s) < line: win = True
                    elif "TÀI" in pick and (h_s+a_s) > line: win = True
                    elif "DƯỚI" in pick and (a_s + line > h_s): win = True
                    elif "TRÊN" in pick and (h_s - line > a_s): win = True
                    res = "✅ ĐÚNG" if win else "❌ SAI"
                    df.loc[idx[0], 'Status'] = res
                    report += f"🏟️ {m_name}: {h_s}-{a_s} -> *{res}*\n"
                    has_up = True
        if has_up:
            df.to_csv(DB_FILE, index=False)
            send_tele(report)
    except: pass

# --- PHẦN 3: LOGIC CHÍNH ---
def main():
    now_vn = datetime.now() + timedelta(hours=7)
    # Báo cáo bắt đầu & Kiểm tra kết quả cũ
    audit_results()
    
    db, rankings = get_real_data_and_rankings()
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'spreads,totals'}
    try: data = requests.get(api_url, params=params).json()
    except: return

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            h_r, a_r = find_rank(home, rankings), find_rank(away, rankings)
            h2h = db[((db['HomeTeam'].str[:3] == home[:3]) & (db['AwayTeam'].str[:3] == away[:3])) | ((db['HomeTeam'].str[:3] == away[:3]) & (db['AwayTeam'].str[:3] == home[:3]))]
            avg_g = h2h['FTHG'].add(h2h['FTAG']).mean() if not h2h.empty else 2.5

            for bm in m.get('bookmakers', [])[:1]:
                mkts = {mk['key']: mk for mk in bm['markets']}
                # Chân kinh Chấp
                if 'spreads' in mkts and h_r and a_r:
                    l, p = mkts['spreads'].get('point', 0), mkts['spreads']['outcomes'][0].get('price', 0)
                    r_diff = abs(h_r - a_r)
                    trap = "DỤ TRÊN" if r_diff >= 5 and abs(l) <= 0.5 else "Bình thường"
                    money = "ÉP DƯỚI" if p > 2.05 else "ÉP TRÊN" if p < 1.85 else "ỔN ĐỊNH"
                    if trap != "Bình thường":
                        pick = "VẢ DƯỚI" if trap == "DỤ TRÊN" and money == "ÉP DƯỚI" else "THEO DÕI"
                        save_trap_log(home, away, trap, pick, abs(l))
                        send_tele(f"🏟️ *{home} vs {away}*\n🪤 Bẫy: {trap} | 💰 {money}\n🚨 Lệnh: *{pick}*")
                # Chân kinh Tài Xỉu
                if 'totals' in mkts:
                    tl, tp = mkts['totals'].get('point', 0), mkts['totals']['outcomes'][0].get('price', 0)
                    txtrap = "DỤ TÀI" if tl < (avg_g - 0.45) else "DỤ XỈU" if tl > (avg_g + 0.45) else "Bình thường"
                    if txtrap != "Bình thường":
                        txpick = "VẢ XỈU" if txtrap == "DỤ TÀI" and tp > 2.0 else "VẢ TÀI" if txtrap == "DỤ XỈU" and tp < 1.85 else "THEO DÕI"
                        save_trap_log(home, away, txtrap, txpick, tl)
                        send_tele(f"⚽ *{home} vs {away}*\n🪤 Bẫy TX: {txtrap} (Sử: {avg_g:.1f})\n🚨 Lệnh: *{txpick}*")

    send_tele(f"✅ Hẹn 1 tiếng sau quét lại! 🦈")

if __name__ == "__main__":
    main()
