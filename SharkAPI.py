import pandas as pd
import requests
import io
import os
import warnings
from datetime import datetime, timedelta

warnings.simplefilter(action='ignore')

# --- CẤU HÌNH HỆ THỐNG ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"
LOG_FILE = "shark_history_log.csv"  # ĐÃ KHAI BÁO LẠI Ở ĐÂY

# PHỤC HỒI FULL 25+ NGUỒN GIẢI HẠNG 1-4 (CỦA IDOL)
SOURCES = {
    "ENG": ["E0", "E1", "E2", "E3"],
    "GER": ["D1", "D2"],
    "SPA": ["SP1", "SP2"],
    "ITA": ["I1", "I2"],
    "FRA": ["F1", "F2"],
    "SCO": ["SC0", "SC1", "SC2", "SC3"],
    "EURO": ["N1", "B1", "P1", "T1", "G1"],
    "AMERICA": ["BRA.csv", "ARG.csv", "MEX.csv", "USA.csv"], 
    "ASIA": ["JPN.csv", "CHN.csv"],
    "GLOBAL": ["new_fixtures.csv"]
}

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def get_all_data():
    all_dfs = []
    base_url = "https://www.football-data.co.uk/mmz4281/2526/"
    new_url = "https://www.football-data.co.uk/new/"
    for cat, files in SOURCES.items():
        for f in files:
            target = f"{base_url}{f}.csv" if len(f) <= 3 else f"{new_url}{f}"
            try:
                r = requests.get(target, timeout=12)
                if r.status_code == 200:
                    df = pd.read_csv(io.StringIO(r.text), on_bad_lines='skip')
                    all_dfs.append(df)
            except: continue
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else None

def smart_h2h(db, home, away):
    """So khớp tên bằng 4 ký tự đầu để tránh lệch tên API vs CSV"""
    h_k, a_k = home[:4].strip(), away[:4].strip()
    h2h = db[((db['HomeTeam'].str.contains(h_k, case=False, na=False)) & (db['AwayTeam'].str.contains(a_k, case=False, na=False))) |
             ((db['HomeTeam'].str.contains(a_k, case=False, na=False)) & (db['AwayTeam'].str.contains(h_k, case=False, na=False)))]
    
    if not h2h.empty:
        return h2h['FTHG'].add(h2h['FTAG']).mean(), "H2H Chuẩn"
    
    # Lấy trung bình giải nếu không có đối đầu trực tiếp
    return 2.5, "Mặc định (Giải cỏ)"

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    # GỬI TIN NHẮN KIỂM TRA ĐẦU VÀO
    send_tele(f"📡 *SHARK SCANNER V18*\n⏰ {now_vn.strftime('%H:%M:%S')}\n✅ Đang soi 25 giải Hạng 1-4...")

    db = get_all_data()
    if db is None: return

    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    try:
        data = requests.get(api_url, params={'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals'}).json()
    except: return

    new_bets = []
    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)

        if now_vn < st_vn < now_vn + timedelta(hours=15):
            avg_g, method = smart_h2h(db, home, away)
            
            # LẤY ODDS BIẾN THIÊN (Dựa trên Nguyên tắc Idol)
            bm = m['bookmakers'][0]
            lo_p = bm['markets'][0]['outcomes'][0]['price'] # Odd Tài hiện tại
            # Opening (Trung bình các nhà cái khác)
            io_p = sum([b['markets'][0]['outcomes'][0]['price'] for b in m['bookmakers']]) / len(m['bookmakers'])
            
            delta = io_p - lo_p
            action, reason = "---", ""

            # 1. BẪY DỤ (TRAP)
            if avg_g >= 3.2 and lo_p > 2.10: 
                action, reason = "💣 VẢ MẠNH XỈU", "Bẫy Dụ Tài: H2H nổ nhưng Odd thả cao"
            elif avg_g <= 1.8 and lo_p > 2.15:
                action, reason = "💣 VẢ MẠNH TÀI", "Bẫy Dụ Xỉu: H2H khô nhưng Odd thả cao"

            # 2. BIẾN THIÊN TIỀN & ODD
            elif abs(delta) < 0.03: # Odd giữ nguyên
                if delta > 0.01: action, reason = "VẢ TÀI 🔥", "Odd ngang, Tiền giảm -> Tài"
                elif delta < -0.01: action, reason = "VẢ XỈU ❄️", "Odd ngang, Tiền tăng -> Xỉu"
            
            elif delta < -0.05: action, reason = "VẢ TÀI 🔥", "Odd tăng -> Tài"
            elif delta > 0.05: action, reason = "VẢ XỈU ❄️", "Odd giảm -> Xỉu"

            if action != "---":
                send_tele(f"💎 *KÈO NGON:* {home} vs {away}\n🎯 Lệnh: *{action}*\n📊 {method}: {avg_g:.1f} bàn\n📈 Odd: {io_p:.2f} -> {lo_p:.2f}\n⏰ Đá: {st_vn.strftime('%H:%M')}")
                new_bets.append({"Match": f"{home} vs {away}", "Action": action, "Time": st_vn})

    # CẬP NHẬT LỊCH SỬ (Fix lỗi LOG_FILE)
    if new_bets:
        df_new = pd.DataFrame(new_bets)
        df_new.to_csv(LOG_FILE, mode='a', header=not os.path.exists(LOG_FILE), index=False)

if __name__ == "__main__":
    main()
