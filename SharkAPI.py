import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# ==========================================
# CẤU HÌNH HỆ THỐNG
# ==========================================
LIST_KEYS = [
    "f45bf78df6e60adb0d2d6d1d9e0f7c1c", 
    "43a45057d6df74eab8e05251ca88993c"
]
TELE_TOKEN = "7981423606:AAFvJ5Xin_L62k-q0lKY8BPpoOa4PSoE7Ys"
TELE_CHAT_ID = "957306386"
DB_FILE = "shark_history_log.csv"

# ==========================================
# CÁC HÀM CÔNG CỤ (UTILITIES)
# ==========================================
def get_active_key():
    """Tự động kiểm tra và xoay vòng Key còn lượt quét"""
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

def save_log(match, trap, pick, line):
    """Lưu lịch sử kèo để đối chiếu Húp/Gãy"""
    new = pd.DataFrame([{'Match': match, 'Trap': trap, 'Pick': pick, 'Line': line, 'Status': 'WAITING'}])
    new.to_csv(DB_FILE, mode='a', header=not os.path.isfile(DB_FILE), index=False)

# ==========================================
# XỬ LÝ DỮ LIỆU & ĐỐI CHIẾU
# ==========================================
def audit_results():
    """Kiểm tra kết quả trận đấu đã xong và báo Tele"""
    if not os.path.isfile(DB_FILE): return
    try:
        df = pd.read_csv(DB_FILE)
        waiting_idx = df[df['Status'] == 'WAITING'].index
        if len(waiting_idx) == 0: return
        
        r = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/scores/?daysFrom=1&apiKey={API_KEY}")
        if r.status_code != 200: return
        scores = r.json()
        
        report = "📝 *TỔNG KẾT HÚP/GÃY PHIÊN TRƯỚC*\n\n"
        hup, gay, has_update = 0, 0, False
        
        for idx in waiting_idx:
            m_name = df.loc[idx, 'Match']
            s = next((s for s in scores if s.get('completed') and m_name.split(' vs ')[0][:5].lower() in s['home_team'].lower()), None)
            if s:
                try:
                    h_s, a_s = int(s['scores'][0]['score']), int(s['scores'][1]['score'])
                    pick, line = df.loc[idx, 'Pick'], float(df.loc[idx, 'Line'])
                    total = h_s + a_s
                    # Logic check thắng thua
                    win = ("XỈU" in pick and total < line) or ("TÀI" in pick and total > line) or \
                          ("DƯỚI" in pick and (a_s + line > h_s)) or ("TRÊN" in pick and (h_s - line > a_s))
                    res = "✅ HÚP" if win else "❌ GÃY"
                    hup += 1 if win else 0; gay += 0 if win else 1
                    df.loc[idx, 'Status'] = res
                    report += f"🏟️ {m_name}\n🎯 {pick} | FT: {h_s}-{a_s} -> *{res}*\n\n"
                    has_update = True
                except: continue
        
        if has_update:
            df.to_csv(DB_FILE, index=False)
            send_tele(report + f"📊 *Thống kê:* Húp {hup} - Gãy {gay}")
    except: pass

def get_h2h_data():
    """Gom dữ liệu lịch sử từ các giải (Fix lỗi KeyError: Div)"""
    sources = ["E0", "E1", "SP1", "SP2", "I1", "I2", "D1", "D2", "F1", "F2", "N1", "B1"]
    all_dfs = []
    for s in sources:
        url = f"https://www.football-data.co.uk/mmz4281/2526/{s}.csv"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                t_df = pd.read_csv(io.StringIO(r.text))
                # Chỉ lấy những giải có đủ cột dữ liệu, lỗi thì bỏ qua không làm sập code
                if all(col in t_df.columns for col in ['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']):
                    all_dfs.append(t_df[['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG']])
        except: continue
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

# ==========================================
# CHƯƠNG TRÌNH CHÍNH
# ==========================================
def main():
    now_vn = datetime.now() + timedelta(hours=7)
    
    # LỊCH QUÉT: Tự động 20h - 02h sáng. (Pydroid quét tay thoải mái)
    if not (20 <= now_vn.hour or now_vn.hour < 2) and "ANDROID_ROOT" not in os.environ:
        return

    # 1. Kiểm tra kết quả cũ
    audit_results()
    
    # 2. Lấy dữ liệu H2H để soi kèo
    db = get_h2h_data()
    
    # 3. Quét kèo API mới (Tự động nổ C1, C2, C3 khi đến giờ đá)
    try:
        api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
        params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals'}
        data = requests.get(api_url, params=params).json()
    except: return

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        
        # Chỉ soi các trận trong 12 tiếng tới
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            # Lọc H2H 4 trận gần nhất
            h2h = db[((db['HomeTeam'] == home) & (db['AwayTeam'] == away)) | 
                     ((db['HomeTeam'] == away) & (db['AwayTeam'] == home))]
            avg_g = h2h['FTHG'].add(h2h['FTAG']).head(4).mean() if not h2h.empty else 2.5

            for bm in m.get('bookmakers', [])[:1]:
                mkt = next((mk for mk in bm['markets'] if mk['key'] == 'totals'), None)
                if mkt:
                    tl, tp = mkt['outcomes'][0]['point'], mkt['outcomes'][0]['price']
                    
                    # LOGIC CHÂN KINH V72
                    is_du_tai = (avg_g - tl >= 1.5)
                    is_du_xiu = (tl - avg_g >= 1.5)
                    
                    # Nhận diện lệnh
                    pick = "🚨 VẢ MẠNH XỈU" if is_du_tai and tp > 2.05 else \
                           "🚨 VẢ MẠNH TÀI" if is_du_xiu and tp < 1.85 else \
                           "VẢ TÀI" if tp < 1.85 else "VẢ XỈU" if tp > 2.05 else "THEO DÕI"
                    
                    if "VẢ MẠNH" in pick:
                        save_log(f"{home} vs {away}", "BẪY TX", pick, tl)
                        msg = f"⚽ *KÈO VIP SHARK*\n⏰ {st_vn.strftime('%H:%M')}\n🏟️ {home} vs {away}\n📜 Sử: {avg_g:.1f} | 🎯 Kèo: {tl}\n💰 Odd: {tp}\n👉 *LỆNH: {pick}*"
                        send_tele(msg)

    send_tele(f"✅ Đã quét xong phiên {now_vn.strftime('%H:%M')}. Full giải VIP & Cup! 🦈")

if __name__ == "__main__":
    main()
