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
            if r.status_code == 200 and int(r.headers.get('x-requests-remaining', 0)) > 0: return key
        except: continue
    return LIST_KEYS[0]

API_KEY = get_active_key()

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def track_odds_movement(match_id, current_odd):
    """Lấy biến động và giá cũ để Idol tự quyết"""
    if not os.path.isfile(ODDS_TRACKER):
        df = pd.DataFrame(columns=['match_id', 'old_odd', 'last_update'])
    else: df = pd.read_csv(ODDS_TRACKER)

    movement, old_val = "Scan đầu", "N/A"
    match_row = df[df['match_id'] == match_id]
    
    if not match_row.empty:
        old_val = float(match_row.iloc[0]['old_odd'])
        if current_odd < old_val: movement = "GIẢM 📉 (Tiền vào)"
        elif current_odd > old_val: movement = "TĂNG 📈 (Tiền thoát)"
        else: movement = "ỔN ĐỊNH ➖"
        df.loc[df['match_id'] == match_id, ['old_odd', 'last_update']] = [current_odd, datetime.now()]
    else:
        new_row = pd.DataFrame([{'match_id': match_id, 'old_odd': current_odd, 'last_update': datetime.now()}])
        df = pd.concat([df, new_row], ignore_index=True)
    
    df.to_csv(ODDS_TRACKER, index=False)
    return movement, old_val

def get_rankings_and_db():
    sources = ["E0", "E1", "SP1", "SP2", "I1", "I2", "D1", "D2", "F1", "F2", "N1", "B1"]
    all_dfs = []
    for s in sources:
        url = f"https://www.football-data.co.uk/mmz4281/2526/{s}.csv"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                t_df = pd.read_csv(io.StringIO(r.text))
                if all(c in t_df.columns for c in ['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']):
                    all_dfs.append(t_df[['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']])
        except: continue
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    if not (20 <= now_vn.hour or now_vn.hour < 2) and "ANDROID_ROOT" not in os.environ: return

    db = get_rankings_and_db()
    try:
        data = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=eu&markets=totals").json()
    except: return

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            h2h = db[((db['HomeTeam'] == home) & (db['AwayTeam'] == away)) | ((db['HomeTeam'] == away) & (db['AwayTeam'] == home))]
            avg_g = h2h['FTHG'].add(h2h['FTAG']).head(4).mean() if not h2h.empty else 2.5
            
            for bm in m.get('bookmakers', [])[:1]:
                mkt = next((mk for mk in bm['markets'] if mk['key'] == 'totals'), None)
                if mkt:
                    tl, tp = mkt['outcomes'][0]['point'], mkt['outcomes'][0]['price']
                    match_id = f"{home}_{away}_{tl}"
                    move, old_tp = track_odds_movement(match_id, tp)
                    
                    # --- PHÂN TÍCH BẪY (TRAP) ---
                    is_du_tai = (avg_g - tl >= 1.5)
                    is_du_xiu = (tl - avg_g >= 1.5)
                    trap_info = "DỤ TÀI" if is_du_tai else "DỤ XỈU" if is_du_xiu else "Không bẫy"

                    # --- LOGIC QUYẾT ĐỊNH CỦA IDOL ---
                    command = "🔎 BÁO CÁO KÈO" # Mặc định chỉ báo cáo
                    
                    # TRƯỜNG HỢP 1: CÙNG HƯỚNG -> VẢ
                    if is_du_tai and "TĂNG" in move: command = "🚨 VẢ CỰC MẠNH XỈU"
                    elif is_du_xiu and "GIẢM" in move: command = "🚨 VẢ CỰC MẠNH TÀI"
                    
                    # TRƯỜNG HỢP 2: KHÔNG BẪY NHƯNG TIỀN NỔ (ODD DƯỚI 1.85 HOẶC TRÊN 2.05)
                    elif tp < 1.85: command = "🔥 VẢ THEO DÒNG TIỀN TÀI"
                    elif tp > 2.05: command = "🔥 VẢ THEO DÒNG TIỀN XỈU"

                    # Bắn Tele nếu có Bẫy HOẶC có Biến động (không im lặng nữa)
                    if trap_info != "Không bẫy" or move != "ỔN ĐỊNH ➖":
                        msg = f"🏟️ *{command}*\n"
                        msg += f"⚽ {home} vs {away} ({st_vn.strftime('%H:%M')})\n"
                        msg += f"📜 Sử: {avg_g:.1f} | 🎯 Kèo: {tl}\n"
                        msg += f"🪤 Bẫy: {trap_info}\n"
                        msg += f"📈 Odd: {old_tp} ➔ {tp} ({move})\n"
                        msg += f"👉 *IDOL TỰ QUYẾT!*" if "🔎" in command else ""
                        send_tele(msg)
                        
                        if "VẢ" in command: # Lưu log các trận Vả để mai audit
                            new = pd.DataFrame([{'Match': f"{home} vs {away}", 'Trap': trap_info, 'Pick': command, 'Line': tl, 'Status': 'WAITING'}])
                            new.to_csv(DB_FILE, mode='a', header=not os.path.isfile(DB_FILE), index=False)

    send_tele(f"✅ Đã xong phiên {now_vn.strftime('%H:%M')}. Đã lọc biến động cho Idol! 🦈")

if __name__ == "__main__":
    main()
