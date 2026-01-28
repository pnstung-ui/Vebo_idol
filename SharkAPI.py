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
ODDS_TRACKER = "odds_tracker.csv" # "Sổ tay" ghi chép biến động

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

# --- HÀM THEO DÕI BIẾN ĐỘNG ---
def track_odds_movement(match_id, current_odd):
    """So sánh Odd hiện tại với Odd phiên trước để tìm biến động"""
    if not os.path.isfile(ODDS_TRACKER):
        df = pd.DataFrame(columns=['match_id', 'old_odd', 'last_update'])
    else:
        df = pd.read_csv(ODDS_TRACKER)

    movement = "First Scan" # Mặc định là lần quét đầu
    match_row = df[df['match_id'] == match_id]
    
    if not match_row.empty:
        old_odd = float(match_row.iloc[0]['old_odd'])
        if current_odd < old_odd: movement = "DOWN (Tiền vào)"
        elif current_odd > old_odd: movement = "UP (Tiền thoát)"
        else: movement = "STABLE"
        
        # Cập nhật Odd mới cho lần sau
        df.loc[df['match_id'] == match_id, ['old_odd', 'last_update']] = [current_odd, datetime.now()]
    else:
        # Thêm trận mới vào sổ tay
        new_row = pd.DataFrame([{'match_id': match_id, 'old_odd': current_odd, 'last_update': datetime.now()}])
        df = pd.concat([df, new_row], ignore_index=True)
    
    # Xóa các trận cũ quá 24h để file không bị nặng
    df['last_update'] = pd.to_datetime(df['last_update'])
    df = df[df['last_update'] > (datetime.now() - timedelta(hours=24))]
    df.to_csv(ODDS_TRACKER, index=False)
    return movement

# ... (Các hàm audit_results, get_h2h_data giữ nguyên như bản trước) ...

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    if not (20 <= now_vn.hour or now_vn.hour < 2) and "ANDROID_ROOT" not in os.environ: return

    # 1. Audit kết quả
    # (Gọi hàm audit_results ở đây)

    # 2. Lấy dữ liệu kèo
    try:
        data = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/odds/?apiKey={API_KEY}&regions=eu&markets=totals").json()
    except: return

    # Lấy DB H2H để check bẫy
    sources = ["E0", "E1", "SP1", "SP2", "I1", "I2", "D1", "D2", "F1", "F2", "N1", "B1"]
    all_dfs = []
    for s in sources:
        try:
            r = requests.get(f"https://www.football-data.co.uk/mmz4281/2526/{s}.csv", timeout=10)
            if r.status_code == 200:
                t_df = pd.read_csv(io.StringIO(r.text))
                if 'HomeTeam' in t_df.columns: all_dfs.append(t_df)
        except: continue
    db = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            # Check H2H
            h2h = db[((db['HomeTeam'] == home) & (db['AwayTeam'] == away)) | ((db['HomeTeam'] == away) & (db['AwayTeam'] == home))]
            avg_g = h2h['FTHG'].add(h2h['FTAG']).head(4).mean() if not h2h.empty else 2.5
            
            for bm in m.get('bookmakers', [])[:1]:
                mkt = next((mk for mk in bm['markets'] if mk['key'] == 'totals'), None)
                if mkt:
                    tl, tp = mkt['outcomes'][0]['point'], mkt['outcomes'][0]['price']
                    match_id = f"{home}_{away}_{tl}"
                    
                    # --- BẮT BIẾN ĐỘNG ---
                    move = track_odds_movement(match_id, tp)
                    
                    # Logic Trap
                    is_du_tai = (avg_g - tl >= 1.5)
                    is_du_xiu = (tl - avg_g >= 1.5)
                    
                    final_pick = "THEO DÕI"
                    
                    # 1. Nếu có Bẫy + Biến động ủng hộ -> VẢ CỰC MẠNH
                    if is_du_tai and "UP" in move: 
                        final_pick = "🚨 VẢ CỰC MẠNH XỈU (Bẫy Tài + Tiền Thoát)"
                    elif is_du_xiu and "DOWN" in move:
                        final_pick = "🚨 VẢ CỰC MẠNH TÀI (Bẫy Xỉu + Tiền Ép)"
                    
                    # 2. Nếu không bẫy nhưng có biến động mạnh
                    elif "DOWN" in move and tp < 1.80:
                        final_pick = "🔥 THEO DÒNG TIỀN TÀI"
                    elif "UP" in move and tp > 2.10:
                        final_pick = "🔥 THEO DÒNG TIỀN XỈU"

                    if "VẢ" in final_pick or "THEO DÒNG TIỀN" in final_pick:
                        msg = f"🏟️ *BÁO CÁO CÁ MẬP*\n⚽ {home} vs {away}\n⏰ {st_vn.strftime('%H:%M')}\n\n"
                        msg += f"📜 H2H: {avg_g:.1f} bàn | 🎯 Kèo: {tl}\n"
                        msg += f"📈 Biến động: *{move}* (Giá cũ: ..., Giá mới: {tp})\n"
                        msg += f"👉 *LỆNH: {final_pick}*"
                        send_tele(msg)

    send_tele(f"✅ Đã quét xong phiên {now_vn.strftime('%H:%M')}. Đã nạp dữ liệu biến động! 🦈")

if __name__ == "__main__":
    main()
