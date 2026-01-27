import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- CẤU HÌNH ĐỒNG BỘ TÊN FILE CỦA IDOL ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "7981423606:AAFvJ5Xin_L62k-q0lKY8BPpoOa4PSoE7Ys"
TELE_CHAT_ID = "957306386"
DB_FILE = "shark_history_log.csv" # Đã đổi tên khớp với ảnh GitHub của Idol

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def audit_results():
    if not os.path.isfile(DB_FILE): return
    try:
        df = pd.read_csv(DB_FILE)
        waiting = df[df['Status'] == 'WAITING']
        if waiting.empty: return
        
        scores = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/scores/?daysFrom=1&apiKey={API_KEY}").json()
        report = "📝 *ĐỐI CHIẾU KẾT QUẢ PHIÊN TRƯỚC*\n\n"
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
                    report += f"🏟️ {m_name}\n🎯 Lệnh: {pick} | FT: {h_s}-{a_s} -> *{res}*\n\n"
                    has_up = True
        if has_up:
            df.to_csv(DB_FILE, index=False)
            send_tele(report)
    except Exception as e: print(f"Lỗi audit: {e}")

def save_log(match, trap, pick, line):
    """Ghi đè hoặc tạo mới file history đúng tên Idol đang dùng"""
    new_entry = pd.DataFrame([{'Match': match, 'Trap': trap, 'Pick': pick, 'Line': line, 'Status': 'WAITING'}])
    if not os.path.isfile(DB_FILE):
        new_entry.to_csv(DB_FILE, index=False)
    else:
        new_entry.to_csv(DB_FILE, mode='a', header=False, index=False)

def get_rankings_and_db():
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

def main():
    audit_results()
    db, rankings = get_rankings_and_db()
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'spreads,totals'}
    try: data = requests.get(api_url, params=params).json()
    except: return

    now_vn = datetime.now() + timedelta(hours=7)
    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            h_r = rankings.get(next((k for k in rankings if home[:4].lower() in k.lower()), None))
            a_r = rankings.get(next((k for k in rankings if away[:4].lower() in k.lower()), None))
            h2h = db[((db['HomeTeam'].str[:3] == home[:3]) & (db['AwayTeam'].str[:3] == away[:3])) | 
                     ((db['HomeTeam'].str[:3] == away[:3]) & (db['AwayTeam'].str[:3] == home[:3]))]
            avg_g = h2h['FTHG'].add(h2h['FTAG']).mean() if not h2h.empty else 2.5

            for bm in m.get('bookmakers', [])[:1]:
                mkts = {mk['key']: mk for mk in bm['markets']}
                
                # --- LUỒNG KÈO CHẤP ---
                if 'spreads' in mkts:
                    l = mkts['spreads']['outcomes'][0].get('point', 0)
                    p = mkts['spreads']['outcomes'][0].get('price', 0)
                    is_trap_hc = (h_r and a_r and abs(h_r - a_r) >= 5 and abs(l) <= 0.5)
                    money_hc = "GIẢM (ÉP DƯỚI)" if p > 2.05 else "TĂNG (ÉP TRÊN)" if p < 1.85 else "ỔN ĐỊNH"
                    
                    if is_trap_hc or money_hc != "ỔN ĐỊNH":
                        pick_hc = "🚨 VẢ MẠNH DƯỚI" if is_trap_hc and p > 2.05 else "THEO DÕI CHẤP"
                        save_log(f"{home} vs {away}", "BẪY CHẤP", pick_hc, abs(l))
                        send_tele(f"🏟️ *NHẬN ĐỊNH KÈO CHẤP*\n⏰ {st_vn.strftime('%H:%M')}\n⚽ {home} vs {away}\n📈 Rank: {h_r} vs {a_r}\n🎯 Chấp: {l} | Odd: {p}\n🪤 Bẫy: {'DỤ TRÊN' if is_trap_hc else 'None'}\n💰 Tiền: {money_hc}\n👉 Lệnh: *{pick_hc}*")

                # --- LUỒNG TÀI XỈU ---
                if 'totals' in mkts:
                    tl = mkts['totals']['outcomes'][0].get('point', 0)
                    tp = mkts['totals']['outcomes'][0].get('price', 0)
                    is_trap_tx = (tl < (avg_g - 0.45))
                    money_tx = "VẢ TÀI" if tp < 1.85 else "VẢ XỈU" if tp > 2.05 else "THEO DÕI TX"
                    
                    if is_trap_tx or money_tx != "THEO DÕI TX":
                        pick_tx = "🚨 VẢ MẠNH XỈU" if is_trap_tx and tp > 2.05 else money_tx
                        save_log(f"{home} vs {away}", "BẪY TX", pick_tx, tl)
                        send_tele(f"⚽ *NHẬN ĐỊNH TÀI XỈU*\n⏰ {st_vn.strftime('%H:%M')}\n🏟️ {home} vs {away}\n📜 Sử: {avg_g:.1f} bàn\n🎯 Mốc: {tl} | Odd: {tp}\n🪤 Bẫy: {'DỤ TÀI' if is_trap_tx else 'None'}\n👉 Lệnh: *{pick_tx}*")

    send_tele(f"✅ Phiên {now_vn.strftime('%H:%M')} hoàn tất. Log đã được ghi vào {DB_FILE}. 🦈")

if __name__ == "__main__":
    main()
