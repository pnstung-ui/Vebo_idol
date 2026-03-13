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

# --- HÀM ĐIỀU KHIỂN BẰNG TIN NHẮN (COMMAND) ---
def check_tele_commands():
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/getUpdates"
    try:
        updates = requests.get(url).json()
        if not updates["result"]: return None
        last_msg = updates["result"][-1]["message"]["text"].lower()
        return last_msg
    except: return None

# --- HÀM AUDIT (BÁO HÚP GÃY) ---
def audit_results(db_results, manual=False):
    if not os.path.isfile(DB_FILE): return
    history = pd.read_csv(DB_FILE)
    if history.empty: return

    updated = False
    summary = "📊 *KẾT QUẢ CHIẾN ĐOÀN SHARK*\n\n"
    for idx, row in history.iterrows():
        if row['Status'] == 'WAITING':
            teams = row['Match'].split(' vs ')
            res = db_results[(db_results['HomeTeam'].str.contains(teams[0][:4], case=False, na=False)) & 
                             (db_results['AwayTeam'].str.contains(teams[1][:4], case=False, na=False))]
            if not res.empty:
                hg, ag = res.iloc[0]['FTHG'], res.iloc[0]['FTAG']
                total, line, pick = hg + ag, float(row['Line']), row['Pick']
                
                if pick == 'TÀI':
                    status = "✅ HÚP TÀI" if total > line else "❌ GÃY" if total < line else "➖ HÒA"
                else:
                    status = "✅ HÚP XỈU" if total < line else "❌ GÃY" if total > line else "➖ HÒA"
                
                history.at[idx, 'Status'] = status
                summary += f"🏟️ {row['Match']}\n🎯 {pick} {line} | KQ: {hg}-{ag} -> *{status}*\n\n"
                updated = True
    
    if updated:
        history.to_csv(DB_FILE, index=False)
        send_tele(summary)
    elif manual:
        send_tele("🏟️ Chưa có kết quả mới cho các trận đang chờ, Idol đợi tí nhé!")

def get_h2h_db():
    sources = ["E0", "E1", "E2", "E3", "SP1", "SP2", "I1", "I2", "D1", "D2", "F1", "F2", "N1", "B1", "P1", "T1", "SC0", "G1", "A1"]
    all_dfs = []
    for s in sources:
        try:
            r = requests.get(f"https://www.football-data.co.uk/mmz4281/2526/{s}.csv", timeout=10)
            if r.status_code == 200: all_dfs.append(pd.read_csv(io.StringIO(r.text)))
        except: continue
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

def track_odds_movement(match_id, current_tp):
    if not os.path.isfile(ODDS_TRACKER):
        df = pd.DataFrame(columns=['match_id', 'old_tp', 'last_update'])
    else:
        df = pd.read_csv(ODDS_TRACKER)
    
    move, old_val = "Scan đầu", current_tp
    match_row = df[df['match_id'] == match_id]
    if not match_row.empty:
        old_val = float(match_row.iloc[0]['old_tp'])
        move = "GIẢM 📉" if current_tp < old_val else "TĂNG 📈" if current_tp > old_val else "ỔN ĐỊNH ➖"
        df.loc[df['match_id'] == match_id, ['old_tp', 'last_update']] = [current_tp, datetime.now()]
    else:
        new_row = pd.DataFrame([{'match_id': match_id, 'old_tp': current_tp, 'last_update': datetime.now()}])
        df = pd.concat([df, new_row], ignore_index=True)
    df.to_csv(ODDS_TRACKER, index=False)
    return move, old_val

def scan_kèo(db, manual=False):
    try:
        data = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=eu&markets=totals").json()
    except: return
    
    found = False
    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        if datetime.now() + timedelta(hours=7) < st_vn < datetime.now() + timedelta(hours=19):
            h2h_m = db[((db['HomeTeam'].str.contains(home[:4], na=False)) & (db['AwayTeam'].str.contains(away[:4], na=False))) |
                       ((db['HomeTeam'].str.contains(away[:4], na=False)) & (db['AwayTeam'].str.contains(home[:4], na=False)))]
            if not h2h_m.empty:
                avg_g = h2h_m.head(2)['FTHG'].add(h2h_m.head(2)['FTAG']).mean()
                for bm in m.get('bookmakers', [])[:1]:
                    for mkt in bm['markets']:
                        for out in mkt['outcomes']:
                            tl, tp = out['point'], out['price']
                            match_id = f"{home}_{away}_{tl}"
                            move, old_tp = track_odds_movement(match_id, tp)
                            gap = tl - avg_g
                            
                            cmd, pick = "", ""
                            # --- QUY LUẬT THUẬN (SĂN TÀI) ---
                            if out['name'].upper() == 'OVER' and gap >= 1.75 and "GIẢM" in move:
                                cmd, pick = "🚨 VẢ MẠNH TÀI (NÉN LÒ XO)", "TÀI"
                            
                            # --- QUY LUẬT NGƯỢC (SĂN XỈU) ---
                            elif out['name'].upper() == 'OVER' and gap <= -1.25 and avg_g >= 3.0 and "TĂNG" in move:
                                cmd, pick = "🚨 VẢ MẠNH XỈU (BẪY XẢ KÈO)", "XỈU"

                            if cmd:
                                msg = f"{cmd}\n🏟️ {home}-{away}\n📊 Kèo: {tl} | Odd: {tp} ({move})\n📜 Sử: {avg_g:.1f} bàn | Gap: {gap:+.1f}"
                                send_tele(msg)
                                pd.DataFrame([{'Match':f"{home} vs {away}", 'Line':tl, 'Pick':pick, 'Status':'WAITING'}]).to_csv(DB_FILE, mode='a', index=False, header=not os.path.isfile(DB_FILE))
                                found = True
    if manual and not found: send_tele("🏟️ Vừa quét xong, chưa thấy kèo nào đủ độ lệch Idol ơi!")

def main():
    db = get_h2h_db()
    cmd = check_tele_commands()
    
    # Idol nhắn "quét" -> Bot quét kèo ngay
    if cmd == "quét":
        send_tele("🦈 Shark đang lặn sâu quét kèo theo yêu cầu của Idol...")
        scan_kèo(db, manual=True)
    # Idol nhắn "kết quả" -> Bot báo húp gãy ngay
    elif cmd == "kết quả":
        send_tele("📊 Đang kiểm tra bảng vàng cho Idol...")
        audit_results(db, manual=True)
    else:
        # Chế độ tự động theo giờ
        now_vn = datetime.now() + timedelta(hours=7)
        if 7 <= now_vn.hour <= 10: audit_results(db)
        if (20 <= now_vn.hour or now_vn.hour < 4): scan_kèo(db)

if __name__ == "__main__":
    main()
