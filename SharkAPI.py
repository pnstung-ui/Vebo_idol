import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- CẤU HÌNH API ---
LIST_KEYS = [
    "f45bf78df6e60adb0d2d6d1d9e0f7c1c", 
    "43a45057d6df74eab8e05251ca88993c"
]
TELE_TOKEN = "7981423606:AAFvJ5Xin_L62k-q0lKY8BPpoOa4PSoE7Ys"
TELE_CHAT_ID = "957306386"
DB_FILE = "shark_history_log.csv"

def get_active_key():
    """Xoay vòng 2 API Key để lách quota"""
    for key in LIST_KEYS:
        try:
            r = requests.get(f"https://api.the-odds-api.com/v4/sports/?apiKey={key}", timeout=10)
            if r.status_code == 200 and int(r.headers.get('x-requests-remaining', 0)) > 0:
                return key
        except: continue
    return LIST_KEYS[0]

API_KEY = get_active_key()

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def audit_results():
    """Đối chiếu tỉ số và báo Gãy/Húp"""
    if not os.path.isfile(DB_FILE): return
    try:
        df = pd.read_csv(DB_FILE)
        waiting_idx = df[df['Status'] == 'WAITING'].index
        if len(waiting_idx) == 0: return
        r = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/scores/?daysFrom=1&apiKey={API_KEY}")
        if r.status_code != 200: return
        scores = r.json()
        report = "📝 *TỔNG KẾT KẾT QUẢ PHIÊN TRƯỚC*\n\n"
        hup, gay, update = 0, 0, False
        for idx in waiting_idx:
            m_name = df.loc[idx, 'Match']
            s = next((s for s in scores if s.get('completed') and m_name.split(' vs ')[0][:5].lower() in s['home_team'].lower()), None)
            if s:
                try:
                    h_s, a_s = int(s['scores'][0]['score']), int(s['scores'][1]['score'])
                    pick, line = df.loc[idx, 'Pick'], float(df.loc[idx, 'Line'])
                    total = h_s + a_s
                    win = ("XỈU" in pick and total < line) or ("TÀI" in pick and total > line) or \
                          ("DƯỚI" in pick and (a_s + line > h_s)) or ("TRÊN" in pick and (h_s - line > a_s))
                    res = "✅ HÚP" if win else "❌ GÃY"
                    hup += 1 if win else 0; gay += 0 if win else 1
                    df.loc[idx, 'Status'] = res
                    report += f"🏟️ {m_name}\n🎯 {pick} | FT: {h_s}-{a_s} -> *{res}*\n\n"
                    update = True
                except: continue
        if update:
            df.to_csv(DB_FILE, index=False)
            send_tele(report + f"📊 *Thống kê:* Húp {hup} - Gãy {gay}")
    except: pass

def save_log(match, trap, pick, line):
    new = pd.DataFrame([{'Match': match, 'Trap': trap, 'Pick': pick, 'Line': line, 'Status': 'WAITING'}])
    new.to_csv(DB_FILE, mode='a', header=not os.path.isfile(DB_FILE), index=False)

def get_rankings_and_db():
    sources = ["E0", "E1", "SP1", "SP2", "I1", "I2", "D1", "D2", "F1", "F2" "N1" "N2" "T1" ]
    all_dfs = []
    for s in sources:
        url = f"https://www.football-data.co.uk/mmz4281/2526/{s}.csv"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                t_df = pd.read_csv(io.StringIO(r.text))
                # Fix lỗi KeyError: 'Div' bằng cách kiểm tra cột
                if 'HomeTeam' in t_df.columns:
                    all_dfs.append(t_df[['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']])
        except: continue
    db = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    if db.empty: return pd.DataFrame(), {}
    teams = pd.concat([db['HomeTeam'], db['AwayTeam']]).unique()
    table = {t: 0 for t in teams if pd.notna(t)}
    for _, row in db.iterrows():
        try:
            if row['FTR'] == 'H': table[row['HomeTeam']] += 3
            elif row['FTR'] == 'A': table[row['AwayTeam']] += 3
            else: table[row['HomeTeam']] += 1; table[row['AwayTeam']] += 1
        except: continue
    rankings = {t: r + 1 for r, (t, p) in enumerate(sorted(table.items(), key=lambda x: x[1], reverse=True))}
    return db, rankings

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    # LỊCH QUÉT: 20h - 02h (GitHub) hoặc Manual (Pydroid)
    if not (20 <= now_vn.hour or now_vn.hour < 2) and "ANDROID_ROOT" not in os.environ:
        return

    audit_results()
    db, rankings = get_rankings_and_db()
    try:
        data = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=eu&markets=spreads,totals").json()
    except: return

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            h_r, a_r = rankings.get(home), rankings.get(away)
            h2h = db[((db['HomeTeam'] == home) & (db['AwayTeam'] == away)) | ((db['HomeTeam'] == away) & (db['AwayTeam'] == home))]
            avg_g = h2h['FTHG'].add(h2h['FTAG']).head(4).mean() if not h2h.empty else 2.5

            for bm in m.get('bookmakers', [])[:1]:
                mkts = {mk['key']: mk for mk in bm['markets']}
                # Tài Xỉu
                if 'totals' in mkts:
                    tl, tp = mkts['totals']['outcomes'][0]['point'], mkts['totals']['outcomes'][0]['price']
                    is_du_tai = (avg_g - tl >= 1.5)
                    is_du_xiu = (tl - avg_g >= 1.5)
                    trap = "DỤ TÀI" if is_du_tai else "DỤ XỈU" if is_du_xiu else "None"
                    pick = "🚨 VẢ MẠNH XỈU" if is_du_tai and tp > 2.05 else "🚨 VẢ MẠNH TÀI" if is_du_xiu and tp < 1.85 else "THEO DÕI"
                    if "VẢ MẠNH" in pick:
                        save_log(f"{home} vs {away}", trap, pick, tl)
                        send_tele(f"🏟️ *BẮT BẪY TÀI XỈU*\n⏰ {st_vn.strftime('%H:%M')}\n⚽ {home} vs {away}\n📜 Sử: {avg_g:.1f} | 🎯 Kèo: {tl}\n💰 Odd: {tp}\n👉 *LỆNH: {pick}*")

    send_tele(f"✅ Đã quét phiên {now_vn.strftime('%H:%M')}. (Key: {API_KEY[:4]}***) 🦈")

if __name__ == "__main__":
    main()
