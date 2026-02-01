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

def get_h2h_db():
    # Mở rộng nguồn để quét đủ các giải theo yêu cầu Idol
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
    
    # 1. QUY TRÌNH SĂN BẪY (20h - 04h)
    if not (20 <= now_vn.hour or now_vn.hour < 4) and not is_manual: return

    try:
        data = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=eu&markets=h2h,totals").json()
    except: return

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            # --- THAM CHIẾU LỊCH SỬ 2 TRẬN GẦN NHẤT ---
            h2h_m = db[((db['HomeTeam'].str.contains(home[:5], na=False)) & (db['AwayTeam'].str.contains(away[:5], na=False))) |
                       ((db['HomeTeam'].str.contains(away[:5], na=False)) & (db['AwayTeam'].str.contains(home[:5], na=False)))]
            
            if h2h_m.empty: continue
            
            # Lấy 2 trận gần nhất để so sánh bẫy
            last_2 = h2h_m.head(2)
            avg_g = last_2['FTHG'].add(last_2['FTAG']).mean()
            # Tính hiệu số trung bình để soi bẫy chấp
            avg_diff = (last_2['FTHG'] - last_2['FTAG']).mean()

            for bm in m.get('bookmakers', [])[:1]:
                for mkt in bm['markets']:
                    for out in mkt['outcomes']:
                        tl, tp = out.get('point', 0), out['price']
                        match_id = f"{home}_{away}_{mkt['key']}_{out['name']}_{tl}"
                        move, old_tp = track_odds_movement(match_id, tp)
                        
                        trap = "Không"
                        cmd = ""

                        # --- LOGIC BẪY TÀI XỈU (DỰA TRÊN SO SÁNH KÈO HIỆN TẠI) ---
                        if mkt['key'] == 'totals':
                            # Dụ Tài: Lịch sử nổ nhiều (avg_g cao) nhưng kèo nhà cái cho thấp (tl thấp)
                            if avg_g - tl >= 1.0: trap = "DỤ TÀI"
                            # Dụ Xỉu: Lịch sử ít bàn (avg_g thấp) nhưng kèo nhà cái cho cao (tl cao)
                            elif tl - avg_g >= 1.0: trap = "DỤ XỈU"
                            
                            # Lệnh Vả theo biến động tiền
                            if trap == "DỤ TÀI" and "TĂNG" in move: cmd = "🚨 VẢ MẠNH XỈU"
                            elif trap == "DỤ XỈU" and "GIẢM" in move: cmd = "🚨 VẢ MẠNH TÀI"

                        # --- LOGIC BẪY CHẤP (H2H) ---
                        elif mkt['key'] == 'h2h':
                            # So sánh chênh lệch bàn thắng lịch sử với việc nhà cái đánh giá đội thắng
                            if abs(avg_diff) >= 1.5 and tp > 2.2: trap = "BẪY CHẤP (Kèo thơm ảo)"
                            
                            if tp < 1.85: cmd = f"🔥 VẢ {out['name'].upper()}"

                        # Chỉ bắn tin khi có biến động hoặc phát hiện bẫy
                        if (trap != "Không" or move != "ỔN ĐỊNH ➖") and cmd != "":
                            msg = f"🏟️ *{cmd}*\n⚽ {home}-{away}\n📊 {mkt['key'].upper()} {out['name']} {tl}\n📈 {old_tp}->{tp} ({move})\n📜 H2H (2 trận): Ghi bàn {avg_g:.1f} | HS: {avg_diff:.1f}\n🪤 Bẫy: {trap}"
                            send_tele(msg)
                            
                            new_log = pd.DataFrame([{'Match': f"{home} vs {away}", 'Trap': trap, 'Pick': cmd, 'Line': tl, 'Status': 'WAITING'}])
                            new_log.to_csv(DB_FILE, mode='a', index=False, header=not os.path.isfile(DB_FILE))

    send_tele(f"✅ Phiên {now_vn.strftime('%H:%M')} मास्टर (Master) hoàn tất! 🦈")

if __name__ == "__main__":
    main()
