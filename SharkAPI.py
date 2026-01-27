import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- CẤU HÌNH ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"

# PHỤC HỒI ĐẦY ĐỦ CÁC GIẢI HẠNG 1-4 CỦA IDOL
SOURCES = {
    "ENG": ["E0", "E1", "E2", "E3"], # Hạng 1 -> Hạng 4 Anh
    "SCO": ["SC0", "SC1", "SC2", "SC3"], # Hạng 1 -> Hạng 4 Scotland
    "GER": ["D1", "D2"], # Đức 1, 2
    "SPA": ["SP1", "SP2"], # TBN 1, 2
    "ITA": ["I1", "I2"], # Ý 1, 2
    "FRA": ["F1", "F2"], # Pháp 1, 2
    "EURO": ["N1", "B1", "P1", "T1", "G1"], # Hà Lan, Bỉ, Bồ, Thổ, Hy Lạp
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
                    df['Div_Ref'] = f
                    all_dfs.append(df)
            except: continue
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else None

def smart_match_h2h(db, home, away):
    """Tìm H2H thông minh bằng 4 ký tự đầu"""
    h_k, a_k = home[:4].strip(), away[:4].strip()
    # Tìm trực tiếp
    h2h = db[((db['HomeTeam'].str.contains(h_k, case=False, na=False)) & (db['AwayTeam'].str.contains(a_k, case=False, na=False))) |
             ((db['HomeTeam'].str.contains(a_k, case=False, na=False)) & (db['AwayTeam'].str.contains(h_k, case=False, na=False)))]
    
    if not h2h.empty:
        return h2h['FTHG'].add(h2h['FTAG']).mean(), "H2H Trực Tiếp"
    
    # Dự phòng: Lấy trung bình giải của 2 đội đó
    h_f = db[(db['HomeTeam'].str.contains(h_k, case=False, na=False)) | (db['AwayTeam'].str.contains(h_k, case=False, na=False))].tail(5)
    a_f = db[(db['HomeTeam'].str.contains(a_k, case=False, na=False)) | (db['AwayTeam'].str.contains(a_k, case=False, na=False))].tail(5)
    
    if not h_f.empty and not a_f.empty:
        avg = (h_f['FTHG'].add(h_f['FTAG']).mean() + a_f['FTHG'].add(a_f['FTAG']).mean()) / 2
        return avg, "Tham Chiếu Giải"
    
    return 2.5, "Mặc định"

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    # TIN NHẮN KIỂM TRA HỆ THỐNG
    send_tele(f"🦈 *SHARK V17 START* 🦈\n⏰ {now_vn.strftime('%H:%M:%S')}\n📡 Đang quét 25+ giải cỏ...")

    db = get_all_data()
    if db is None:
        send_tele("❌ Lỗi: Không tải được dữ liệu CSV tham chiếu.")
        return

    # API QUÉT KÈO LIVE
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    try:
        data = requests.get(api_url, params={'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals'}).json()
    except:
        send_tele("❌ Lỗi: Không kết nối được API.")
        return

    new_bets = []
    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)

        if now_vn < st_vn < now_vn + timedelta(hours=18):
            avg_g, method = smart_match_h2h(db, home, away)
            
            # BIẾN THIÊN TIỀN & ODD
            bm = m['bookmakers'][0]
            lo_p = bm['markets'][0]['outcomes'][0]['price'] # Odd Live Over 2.5
            # Lấy Opening (Trung bình các nhà cái)
            io_p = sum([b['markets'][0]['outcomes'][0]['price'] for b in m['bookmakers']]) / len(m['bookmakers'])
            
            delta = io_p - lo_p
            action, reason = "---", ""

            # 1. NGUYÊN TẮC BẪY DỤ (Idol's Principle)
            if avg_g >= 3.3 and lo_p > 2.10: 
                action, reason = "💣 VẢ MẠNH XỈU", "Bẫy Dụ Tài: H2H cao nhưng Odd thả cho ăn cao"
            elif avg_g <= 1.9 and lo_p > 2.20:
                action, reason = "💣 VẢ MẠNH TÀI", "Bẫy Dụ Xỉu: H2H thấp nhưng Odd thả cho ăn cao"

            # 2. BIẾN THIÊN TIỀN (Idol's Principle)
            elif abs(delta) < 0.04: # Odd giữ nguyên
                if delta > 0.01: action, reason = "VẢ TÀI 🔥", "Tiền giảm (Odd đi ngang) -> Tài"
                elif delta < -0.01: action, reason = "VẢ XỈU ❄️", "Tiền tăng (Odd đi ngang) -> Xỉu"
            
            # 3. ODD TĂNG/GIẢM
            elif delta < -0.06: action, reason = "VẢ TÀI 🔥", "Odd tăng -> Tài"
            elif delta > 0.06: action, reason = "VẢ XỈU ❄️", "Odd giảm -> Xỉu"

            if action != "---":
                msg = (f"💎 *GỢI Ý VẢ:* {home} vs {away}\n"
                       f"🎯 Lệnh: *{action}*\n"
                       f"📊 {method}: {avg_g:.2f} bàn\n"
                       f"📈 Odd: {io_p:.2f} -> {lo_p:.2f}\n"
                       f"⏰ Đá: {st_vn.strftime('%H:%M')}")
                send_tele(msg)
                new_bets.append({"Time": st_vn, "Match": f"{home} vs {away}", "Action": action})

    # Cập nhật History
    if new_bets:
        df_new = pd.DataFrame(new_bets)
        df_new.to_csv(LOG_FILE, mode='a', header=not os.path.exists(LOG_FILE), index=False)

if __name__ == "__main__":
    main()
