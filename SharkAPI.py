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

# --- 1. ĐỐI CHIẾU KẾT QUẢ (TỪ V59) ---
def audit_results():
    if not os.path.isfile(DB_FILE): return
    df = pd.read_csv(DB_FILE)
    waiting = df[df['Status'] == 'WAITING']
    if waiting.empty: return
    try:
        scores = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/scores/?daysFrom=1&apiKey={API_KEY}").json()
        report = "📝 *TỔNG KẾT KẾT QUẢ NHẬN ĐỊNH*\n\n"
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
                    report += f"{icon} {m_name}\nLệnh: {pick} | FT: {h_s}-{a_s} -> *{res}*\n\n"
                    has_up = True
        if has_up:
            df.to_csv(DB_FILE, index=False)
            send_tele(report)
    except: pass

def save_log(match, trap, pick, line):
    new = pd.DataFrame([{'Match': match, 'Trap': trap, 'Pick': pick, 'Line': line, 'Status': 'WAITING'}])
    if not os.path.isfile(DB_FILE): new.to_csv(DB_FILE, index=False)
    else: new.to_csv(DB_FILE, mode='a', header=False, index=False)

# --- 2. LẤY RANKING & DỮ LIỆU (TỪ V52) ---
def get_rankings():
    sources = ["E0", "E1", "E2", "E3", "D1", "D2", "SP1", "SP2", "I1", "I2", "F1", "F2", "B1", "BRA.csv", "ARG.csv"]
    all_dfs = []
    for s in sources:
        url = f"https://www.football-data.co.uk/new/{s}" if ".csv" in s else f"https://www.football-data.co.uk/mmz4281/2526/{s}.csv"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                all_dfs.append(pd.read_csv(io.StringIO(r.text))[['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']])
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

# --- 3. PHÂN TÍCH KÈO (TỪ V52 & V59) ---
def main():
    audit_results()
    db, rankings = get_rankings()
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'spreads,totals'}
    try: data = requests.get(api_url, params=params).json()
    except: return

    now_vn = datetime.now() + timedelta(hours=7)
    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        
        if now_vn < st_vn < now_vn + timedelta(hours=10):
            h_r = rankings.get(next((k for k in rankings if home[:4] in k or k[:4] in home), None))
            a_r = rankings.get(next((k for k in rankings if away[:4] in k or k[:4] in away), None))
            
            # Tham chiếu lịch sử (Sử)
            h2h = db[((db['HomeTeam'].str[:3] == home[:3]) & (db['AwayTeam'].str[:3] == away[:3])) | 
                     ((db['HomeTeam'].str[:3] == away[:3]) & (db['AwayTeam'].str[:3] == home[:3]))]
            avg_g = h2h['FTHG'].add(h2h['FTAG']).mean() if not h2h.empty else 2.5

            for bm in m.get('bookmakers', [])[:1]:
                mkts = {mk['key']: mk for mk in bm['markets']}
                
                # --- PHÂN TÍCH KÈO CHẤP ---
                if 'spreads' in mkts:
                    l = mkts['spreads']['outcomes'][0].get('point', 0)
                    p = mkts['spreads']['outcomes'][0].get('price', 0)
                    is_trap_hc = (h_r and a_r and abs(h_r - a_r) >= 5 and abs(l) <= 0.5)
                    money_hc = "ÉP DƯỚI" if p > 2.05 else "ÉP TRÊN" if p < 1.85 else "ỔN ĐỊNH"
                    
                    if is_trap_hc or money_hc != "ỔN ĐỊNH":
                        pick = "🚨 VẢ MẠNH DƯỚI" if is_trap_hc and p > 2.05 else "THEO DÕI CHẤP"
                        save_log(f"{home} vs {away}", "BẪY CHẤP", pick, abs(l))
                        send_tele(f"🏟️ *KÈO CHẤP: {home} vs {away}*\n⏰ {st_vn.strftime('%H:%M')}\n📈 Rank: {h_r} vs {a_r}\n🎯 Chấp: {l} | Odd: {p}\n🪤 Bẫy: {'DỤ TRÊN' if is_trap_hc else 'None'}\n💰 Tiền: {money_hc}\n👉 Lệnh: *{pick}*")

                # --- PHÂN TÍCH TÀI XỈU ---
                if 'totals' in mkts:
                    tl = mkts['totals']['outcomes'][0].get('point', 0)
                    tp = mkts['totals']['outcomes'][0].get('price', 0)
                    is_trap_tx = (tl < (avg_g - 0.45)) # Dụ Tài
                    money_tx = "VẢ TÀI" if tp < 1.85 else "VẢ XỈU" if tp > 2.05 else "THEO DÕI TX"
                    
                    if is_trap_tx or money_tx != "THEO DÕI TX":
                        final_tx = "🚨 VẢ MẠNH XỈU" if is_trap_tx and tp > 2.05 else money_tx
                        save_log(f"{home} vs {away}", "BẪY TX", final_tx, tl)
                        send_tele(f"⚽ *TÀI XỈU: {home} vs {away}*\n⏰ {st_vn.strftime('%H:%M')}\n📜 Sử: {avg_g:.1f} bàn\n🎯 Mốc: {tl} | Odd: {tp}\n🪤 Bẫy: {'DỤ TÀI' if is_trap_tx else 'None'}\n👉 Lệnh: *{final_tx}*")

    send_tele(f"✅ Đã quét xong phiên {now_vn.strftime('%H:%M')}. 🦈")

if __name__ == "__main__":
    main()
