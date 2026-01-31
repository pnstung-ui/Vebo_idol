import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- CẤU HÌNH ---
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

# --- HÀM THAM CHIẾU KẾT QUẢ THÔNG MINH ---
def audit_results(db_results):
    if not os.path.isfile(DB_FILE) or db_results.empty: return
    try: 
        history = pd.read_csv(DB_FILE)
        if history.empty: return
    except: return

    updated = False
    summary = "📊 *TỔNG KẾT KÈO ĐÊM QUA*\n\n"

    for idx, row in history.iterrows():
        if row['Status'] == 'WAITING':
            teams = row['Match'].split(' vs ')
            h_api, a_api = teams[0], teams[1]
            
            # Khớp tên thông minh (dùng 5 ký tự đầu để tránh lệch Man Utd/Manchester)
            res = db_results[
                (db_results['HomeTeam'].str.contains(h_api[:5], case=False, na=False)) & 
                (db_results['AwayTeam'].str.contains(a_api[:5], case=False, na=False))
            ]
            
            if not res.empty:
                hg, ag = res.iloc[0]['FTHG'], res.iloc[0]['FTAG']
                total, line, pick = hg + ag, float(row['Line']), row['Pick'].upper()
                status = "HÒA"
                
                # Tham chiếu kết quả dựa trên loại kèo
                if "TÀI" in pick:
                    status = "✅ HÚP" if total > line else "❌ GÃY" if total < line else "➖ HÒA"
                elif "XỈU" in pick:
                    status = "✅ HÚP" if total < line else "❌ GÃY" if total > line else "➖ HÒA"
                elif "VẢ MẠNH" in pick or "VẢ" in pick: # Đối với kèo chấp
                    diff = hg - ag # Hiệu số thực tế
                    # Logic so sánh kèo chấp (Tạm thời báo KQ để Idol check)
                    status = f"Kết quả: {hg}-{ag}"
                
                history.at[idx, 'Status'] = status
                summary += f"🏟️ {row['Match']}\n🎯 {row['Pick']} {line} | KQ: {hg}-{ag} -> *{status}*\n\n"
                updated = True

    if updated:
        history.to_csv(DB_FILE, index=False)
        send_tele(summary)

def get_h2h_db():
    sources = ["E0", "E1", "E2", "E3", "SP1", "SP2", "I1", "I2", "D1", "D2", "F1", "F2", "N1", "B1"]
    all_dfs = []
    for s in sources:
        try:
            r = requests.get(f"https://www.football-data.co.uk/mmz4281/2526/{s}.csv", timeout=10)
            if r.status_code == 200: all_dfs.append(pd.read_csv(io.StringIO(r.text)))
        except: continue
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

def track_odds_movement(match_id, current_odd):
    if not os.path.isfile(ODDS_TRACKER):
        df = pd.DataFrame(columns=['match_id', 'old_odd', 'last_update'])
    else:
        try: df = pd.read_csv(ODDS_TRACKER)
        except: df = pd.DataFrame(columns=['match_id', 'old_odd', 'last_update'])
    move, old_val = "Scan đầu", "N/A"
    match_row = df[df['match_id'] == match_id]
    if not match_row.empty:
        old_val = float(match_row.iloc[0]['old_odd'])
        move = "GIẢM 📉" if current_odd < old_val else "TĂNG 📈" if current_odd > old_val else "ỔN ĐỊNH ➖"
        df.loc[df['match_id'] == match_id, ['old_odd', 'last_update']] = [current_odd, datetime.now()]
    else:
        new = pd.DataFrame([{'match_id': match_id, 'old_odd': current_odd, 'last_update': datetime.now()}])
        df = pd.concat([df, new], ignore_index=True)
    df.to_csv(ODDS_TRACKER, index=False)
    return move, old_val

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    is_manual = os.getenv('GITHUB_EVENT_NAME') == 'workflow_dispatch'
    db = get_h2h_db()
    
    # 1. THAM CHIẾU LỊCH SỬ (7h - 11h sáng VN)
    if 7 <= now_vn.hour <= 11:
        audit_results(db)
        if not is_manual: return

    # 2. CHẾ ĐỘ QUÉT KÈO (20h - 03h sáng VN)
    if not (20 <= now_vn.hour or now_vn.hour < 3) and not is_manual: return

    try:
        # Quét cả kèo chấp (h2h) và tài xỉu (totals)
        data = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=eu&markets=h2h,totals").json()
    except: return

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            # --- CHÂN KINH BẪY ---
            h2h_m = db[((db['HomeTeam'].str.contains(home[:5], na=False)) & (db['AwayTeam'].str.contains(away[:5], na=False)))]
            avg_g = h2h_m['FTHG'].add(h2h_m['FTAG']).head(4).mean() if not h2h_m.empty else 2.5

            for bm in m.get('bookmakers', [])[:1]:
                for mkt in bm['markets']:
                    for out in mkt['outcomes']:
                        tl, tp = out.get('point', 0), out['price']
                        match_id = f"{home}_{away}_{mkt['key']}_{out['name']}_{tl}"
                        move, old_tp = track_odds_movement(match_id, tp)
                        
                        # Logic Bẫy (Trap)
                        is_du_tai = (mkt['key'] == 'totals' and avg_g >= 2.75 and tl <= 2.25)
                        is_du_xiu = (mkt['key'] == 'totals' and avg_g <= 2.0 and tl >= 2.5)
                        trap = "DỤ TÀI" if is_du_tai else "DỤ XỈU" if is_du_xiu else "Không"

                        # QUYẾT ĐỊNH VẢ
                        cmd = ""
                        if is_du_tai and "TĂNG" in move: cmd = "🚨 VẢ MẠNH XỈU"
                        elif is_du_xiu and "GIẢM" in move: cmd = "🚨 VẢ MẠNH TÀI"
                        elif tp < 1.85: cmd = f"🔥 VẢ {out['name'].upper()}"

                        if cmd and move != "ỔN ĐỊNH ➖":
                            msg = f"🏟️ *{cmd}*\n⚽ {home}-{away}\n📊 {mkt['key'].upper()} {out['name']} {tl}\n📈 {old_tp}->{tp} ({move})\n📜 H2H: {avg_g:.1f} | 🪤 Bẫy: {trap}"
                            send_tele(msg)
                            # Lưu log định dạng chuẩn để sáng mai Tham Chiếu
                            new_log = pd.DataFrame([{'Match': f"{home} vs {away}", 'Trap': trap, 'Pick': cmd, 'Line': tl, 'Status': 'WAITING'}])
                            new_log.to_csv(DB_FILE, mode='a', index=False, header=not os.path.isfile(DB_FILE))

    send_tele(f"✅ Phiên {now_vn.strftime('%H:%M')} rực rỡ! 🦈")

if __name__ == "__main__":
    main()