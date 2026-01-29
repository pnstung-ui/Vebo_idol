import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# ==========================================
# 1. CẤU HÌNH HỆ THỐNG
# ==========================================
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

# ==========================================
# 2. XỬ LÝ BIẾN ĐỘNG (ODD MOVEMENT)
# ==========================================
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
        if current_odd < old_val: move = "GIẢM 📉" 
        elif current_odd > old_val: move = "TĂNG 📈"
        else: move = "ỔN ĐỊNH ➖"
        df.loc[df['match_id'] == match_id, ['old_odd', 'last_update']] = [current_odd, datetime.now()]
    else:
        new_row = pd.DataFrame([{'match_id': match_id, 'old_odd': current_odd, 'last_update': datetime.now()}])
        df = pd.concat([df, new_row], ignore_index=True)
    
    df.to_csv(ODDS_TRACKER, index=False)
    return move, old_val

# ==========================================
# 3. LẤY DỮ LIỆU LỊCH SỬ (H2H)
# ==========================================
def get_h2h_db():
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

# ==========================================
# 4. CHƯƠNG TRÌNH CHÍNH
# ==========================================
def main():
    now_vn = datetime.now() + timedelta(hours=7)
    
    # MỞ KHÓA MANUAL: Kiểm tra nếu bấm nút trên GitHub hoặc chạy Pydroid
    is_manual = os.getenv('GITHUB_EVENT_NAME') == 'workflow_dispatch'
    is_android = "ANDROID_ROOT" in os.environ

    if not (is_manual or is_android):
        if not (20 <= now_vn.hour or now_vn.hour < 2):
            print(f"💤 Đang ngoài giờ săn ({now_vn.hour}h). Nghỉ để tiết kiệm API.")
            return

    db = get_h2h_db()
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
                    
                    # Logic Bẫy (Trap)
                    is_du_tai = (avg_g >= 2.75 and tl <= 2.25)
                    is_du_xiu = (avg_g <= 2.0 and tl >= 2.5)
                    trap = "DỤ TÀI" if is_du_tai else "DỤ XỈU" if is_du_xiu else "Không bẫy"

                    # QUYẾT ĐỊNH LỆNH THEO Ý IDOL
                    cmd = "🔎 BÁO CÁO"
                    if is_du_tai and "TĂNG" in move: cmd = "🚨 VẢ CỰC MẠNH XỈU"
                    elif is_du_xiu and "GIẢM" in move: cmd = "🚨 VẢ CỰC MẠNH TÀI"
                    elif tp < 1.85: cmd = "🔥 VẢ TÀI (DÒNG TIỀN)"
                    elif tp > 2.05: cmd = "🔥 VẢ XỈU (DÒNG TIỀN)"

                    if trap != "Không bẫy" or move != "ỔN ĐỊNH ➖":
                        msg = f"🏟️ *{cmd}*\n"
                        msg += f"⚽ {home} vs {away} ({st_vn.strftime('%H:%M')})\n"
                        msg += f"📜 H2H: {avg_g:.1f} | 🎯 Kèo: {tl}\n"
                        msg += f"🪤 Bẫy: {trap}\n"
                        msg += f"📈 Odd: {old_tp} ➔ {tp} ({move})\n"
                        if "🔎" in cmd: msg += "👉 *Idol xem biến động rồi tự quyết!*"
                        send_tele(msg)

    send_tele(f"✅ Phiên {now_vn.strftime('%H:%M')} hoàn tất! Shark đang trực chiến. 🦈")

if __name__ == "__main__":
    main()
