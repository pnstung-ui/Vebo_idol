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

# --- PHẦN 1: DỮ LIỆU & RANKING (ỔN ĐỊNH TỪ V52) ---
def get_real_data_and_rankings():
    sources = ["E0", "E1", "E2", "E3", "D1", "D2", "SP1", "SP2", "I1", "I2", "F1", "F2", 
               "N1", "N2", "B1", "B2", "P1", "T1", "G1", "BRA.csv", "ARG.csv", "MEX.csv"]
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

# --- PHẦN 2: ĐỐI CHIẾU KẾT QUẢ (V59) ---
def audit_results():
    if not os.path.isfile(DB_FILE): return
    df = pd.read_csv(DB_FILE)
    waiting = df[df['Status'] == 'WAITING']
    if waiting.empty: return
    try:
        scores = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/scores/?daysFrom=1&apiKey={API_KEY}").json()
        report = "📝 *CHỐT HIỆU QUẢ CHÂN KINH*\n\n"
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
                    icon = "🚨" if "MẠNH" in pick else "📋"
                    report += f"{icon} {m_name}: {h_s}-{a_s} -> *{res}*\n"
                    has_up = True
        if has_up:
            df.to_csv(DB_FILE, index=False)
            send_tele(report)
    except: pass

def save_log(match, trap, pick, line):
    new = pd.DataFrame([{'Match': match, 'Trap': trap, 'Pick': pick, 'Line': line, 'Status': 'WAITING'}])
    if not os.path.isfile(DB_FILE): new.to_csv(DB_FILE, index=False)
    else: new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- PHẦN 3: LOGIC CHÍNH (BỔ SUNG CHÂN KINH KÈO CHẤP) ---
def main():
    audit_results() # Đối chiếu trước
    db, rankings = get_real_data_and_rankings()
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'spreads,totals'}
    try: data = requests.get(api_url, params=params).json()
    except: return

    now_vn = datetime.now() + timedelta(hours=7)
    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            h_r = rankings.get(next((k for k in rankings if home[:4] in k or k[:4] in home), None))
            a_r = rankings.get(next((k for k in rankings if away[:4] in k or k[:4] in away), None))
            
            for bm in m.get('bookmakers', [])[:1]:
                mkts = {mk['key']: mk for mk in bm['markets']}
                
                # --- CHÂN KINH KÈO CHẤP (BỔ SUNG) ---
                if 'spreads' in mkts:
                    l = mkts['spreads']['outcomes'][0].get('point', 0)
                    p = mkts['spreads']['outcomes'][0].get('price', 0)
                    # Bẫy chấp (Trap)
                    is_trap = (h_r and a_r and abs(h_r - a_r) >= 5 and abs(l) <= 0.5)
                    # Tiền (Money Flow)
                    money = "ÉP DƯỚI" if p > 2.05 else "ÉP TRÊN" if p < 1.85 else "ỔN ĐỊNH"
                    
                    if is_trap:
                        pick = "🚨 VẢ MẠNH CỬA DƯỚI" if money == "ÉP DƯỚI" else "BÁO TRAP DỤ TRÊN"
                        save_log(f"{home} vs {away}", "DỤ TRÊN", pick, abs(l))
                        send_tele(f"🏟️ *BẪY CHẤP: {home} vs {away}*\n📈 Rank: {h_r} vs {a_r}\n🎯 Chấp: {l} | Odd: {p}\n🪤 Bẫy: DỤ TRÊN (KÈO THỐI)\n💰 Tiền: {money}\n👉 Lệnh: *{pick}*")

                # --- CHÂN KINH TÀI XỈU ---
                if 'totals' in mkts:
                    tl = mkts['totals']['outcomes'][0].get('point', 0)
                    tp = mkts['totals']['outcomes'][0].get('price', 0)
                    # Odd giữ nguyên, tiền tăng (giảm sâu) -> Xỉu | Tiền giảm (tăng cao) -> Tài
                    tx_pick = "THEO DÕI"
                    if tp < 1.85: tx_pick = "VẢ TÀI"
                    elif tp > 2.05: tx_pick = "VẢ XỈU"
                    
                    if tx_pick != "THEO DÕI":
                        save_log(f"{home} vs {away}", "TIỀN BIẾN ĐỘNG", tx_pick, tl)
                        # send_tele(f"⚽ *TÀI XỈU: {home} vs {away}*\n🎯 Mốc: {tl} | Odd: {tp}\n🚨 Lệnh: {tx_pick}")

    send_tele(f"✅ Đã quét xong phiên {now_vn.strftime('%H:%M')}. Shark đang rình rập... 🦈")

if __name__ == "__main__":
    main()
