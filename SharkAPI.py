import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- CẤU HÌNH MASTER ---
LIST_KEYS = ["f45bf78df6e60adb0d2d6d1d9e0f7c1c", "43a45057d6df74eab8e05251ca88993c"]
TELE_TOKEN = "7981423606:AAFvJ5Xin_L62k-q0lKY8BPpoOa4PSoE7Ys"
TELE_CHAT_ID = "957306386"
DB_FILE = "shark_history_log.csv"
ODDS_TRACKER = "odds_tracker.csv"

def get_active_key():
    for key in LIST_KEYS:
        try:
            r = requests.get(f"https://api.the-odds-api.com/v4/sports/?apiKey={key}", timeout=10)
            if r.status_code == 200: return key
        except: continue
    return LIST_KEYS[0]

API_KEY = get_active_key()

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def get_tele_command():
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/getUpdates"
    try:
        r = requests.get(url).json()
        if r["result"]:
            last_msg = r["result"][-1]["message"]
            msg_text = last_msg.get("text", "").lower()
            msg_time = datetime.fromtimestamp(last_msg["date"])
            if datetime.now() - msg_time < timedelta(minutes=15):
                return msg_text
    except: pass
    return None

def get_h2h_db():
    sources = ["E0", "E1", "E2", "E3", "SP1", "SP2", "I1", "I2", "D1", "D2", "F1", "F2", "N1", "B1", "P1", "T1", "SC0"]
    all_dfs = []
    for s in sources:
        try:
            r = requests.get(f"https://www.football-data.co.uk/mmz4281/2526/{s}.csv", timeout=10)
            if r.status_code == 200: all_dfs.append(pd.read_csv(io.StringIO(r.text)))
        except: continue
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

def audit_results(db_results):
    if not os.path.isfile(DB_FILE) or db_results.empty: return
    try:
        history = pd.read_csv(DB_FILE)
    except: return
    updated = False
    summary = "📊 *TỔNG KẾT HÚP GÃY*\n\n"
    for idx, row in history.iterrows():
        if row['Status'] == 'WAITING':
            teams = row['Match'].split(' vs ')
            res = db_results[(db_results['HomeTeam'].str.contains(teams[0][:4], na=False)) & (db_results['AwayTeam'].str.contains(teams[1][:4], na=False))]
            if not res.empty:
                hg, ag = res.iloc[0]['FTHG'], res.iloc[0]['FTAG']
                total, line, pick = hg + ag, float(row['Line']), row['Pick']
                status = "✅ HÚP" if (pick == 'TÀI' and total > line) or (pick == 'XỈU' and total < line) else "❌ GÃY" if total != line else "➖ HÒA"
                history.at[idx, 'Status'] = status
                summary += f"🏟️ {row['Match']}\n🎯 {pick} {line} | KQ: {hg}-{ag} -> *{status}*\n\n"
                updated = True
    if updated:
        history.to_csv(DB_FILE, index=False)
        send_tele(summary)

def track_odds_movement(match_id, current_odd):
    # SỬA LỖI: Chống file trống và lỗi đọc file
    if not os.path.isfile(ODDS_TRACKER) or os.stat(ODDS_TRACKER).st_size == 0:
        df = pd.DataFrame(columns=['match_id', 'old_odd', 'last_update'])
    else:
        try:
            df = pd.read_csv(ODDS_TRACKER)
        except:
            df = pd.DataFrame(columns=['match_id', 'old_odd', 'last_update'])
    
    move, old_val = "Scan đầu", current_odd
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    match_row = df[df['match_id'] == match_id]
    
    if not match_row.empty:
        old_val = float(match_row.iloc[0]['old_odd'])
        move = "GIẢM 📉" if current_odd < old_val else "TĂNG 📈" if current_odd > old_val else "ỔN ĐỊNH ➖"
        # SỬA LỖI: Ép kiểu thời gian sang string để tránh lỗi dtype
        df.loc[df['match_id'] == match_id, ['old_odd', 'last_update']] = [current_odd, now_str]
    else:
        new_row = pd.DataFrame([{'match_id': match_id, 'old_odd': current_odd, 'last_update': now_str}])
        df = pd.concat([df, new_row], ignore_index=True)
        
    df.to_csv(ODDS_TRACKER, index=False)
    return move, old_val

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    db = get_h2h_db()
    cmd = get_tele_command()

    # Nhận lệnh Tele
    if cmd == "quét":
        send_tele("🦈 Shark đang quét kèo theo yêu cầu...")
    elif cmd == "kết quả":
        audit_results(db)
        return

    # Khung giờ: 15h - 10h sáng
    if not (15 <= now_vn.hour <= 23 or 0 <= now_vn.hour <= 10) and cmd != "quét": return
    if 8 <= now_vn.hour <= 10: audit_results(db)

    try:
        data = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=eu&markets=totals").json()
    except: return

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        if now_vn < st_vn < now_vn + timedelta(hours=15):
            h2h_m = db[((db['HomeTeam'].str.contains(home[:4], na=False)) & (db['AwayTeam'].str.contains(away[:4], na=False))) |
                       ((db['HomeTeam'].str.contains(away[:4], na=False)) & (db['AwayTeam'].str.contains(home[:4], na=False)))]
            if h2h_m.empty: continue
            avg_g = h2h_m.head(2)['FTHG'].add(h2h_m.head(2)['FTAG']).mean()

            for bm in m.get('bookmakers', [])[:1]:
                for mkt in bm['markets']:
                    for out in mkt['outcomes']:
                        tl, tp = out.get('point', 0), out['price']
                        match_id = f"{home}_{away}_{tl}"
                        move, old_tp = track_odds_movement(match_id, tp)
                        gap = tl - avg_g

                        msg_vả, pick = "", ""
                        # Logic nén lò xo (Tài)
                        if out['name'].upper() == 'OVER' and gap >= 1.75 and "GIẢM" in move:
                            msg_vả, pick = "🚨 VẢ MẠNH TÀI (NÉN LÒ XO)", "TÀI"
                        # Logic bẫy xả (Xỉu)
                        elif out['name'].upper() == 'OVER' and gap <= -1.25 and avg_g >= 3.0 and "TĂNG" in move:
                            msg_vả, pick = "🚨 VẢ MẠNH XỈU (BẪY XẢ)", "XỈU"

                        if msg_vả:
                            send_tele(f"{msg_vả}\n🏟️ {home}-{away}\n📊 Kèo: {tl} | Odd: {tp} ({move})\n📜 Sử: {avg_g:.1f} | Gap: {gap:+.1f}")
                            pd.DataFrame([{'Match': f"{home} vs {away}", 'Line': tl, 'Pick': pick, 'Status': 'WAITING'}]).to_csv(DB_FILE, mode='a', index=False, header=not os.path.isfile(DB_FILE))

if __name__ == "__main__":
    main()
