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
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def get_all_legacy_data():
    """Quét sạch 25+ nguồn giải đấu để làm tham chiếu H2H"""
    all_dfs = []
    base_url = "https://www.football-data.co.uk/mmz4281/2526/" # Mùa mới
    new_url = "https://www.football-data.co.uk/new/"
    
    for country, files in SOURCES.items():
        for f in files:
            # Chọn link tải phù hợp cho từng loại giải
            target_url = f"{base_url}{f}.csv" if len(f) <= 3 else f"{new_url}{f}"
            try:
                r = requests.get(target_url, timeout=10)
                if r.status_code == 200:
                    df = pd.read_csv(io.StringIO(r.text), on_bad_lines='skip')
                    df['Src_Div'] = f # Đánh dấu giải
                    all_dfs.append(df)
            except: continue
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else None

def find_h2h_exact(db, home, away):
    """So khớp tên 4 ký tự để không trượt trận nào"""
    h_key, a_key = home[:4].strip(), away[:4].strip()
    h2h = db[((db['HomeTeam'].str.contains(h_key, case=False, na=False)) & (db['AwayTeam'].str.contains(a_key, case=False, na=False))) |
             ((db['HomeTeam'].str.contains(a_key, case=False, na=False)) & (db['AwayTeam'].str.contains(h_key, case=False, na=False)))]
    
    if not h2h.empty:
        return h2h['FTHG'].add(h2h['FTAG']).mean(), "H2H Trực Tiếp"
    
    # Fallback: Lấy trung bình bàn thắng của 2 đội trong các trận gần nhất tại giải đó
    h_form = db[(db['HomeTeam'].str.contains(h_key, case=False, na=False)) | (db['AwayTeam'].str.contains(h_key, case=False, na=False))].tail(4)
    a_form = db[(db['HomeTeam'].str.contains(a_key, case=False, na=False)) | (db['AwayTeam'].str.contains(a_key, case=False, na=False))].tail(4)
    
    if not h_form.empty and not a_form.empty:
        avg = (h_form['FTHG'].add(h_form['FTAG']).mean() + a_form['FTHG'].add(a_form['FTAG']).mean()) / 2
        return avg, "Tham Chiếu Giải"
    return 2.5, "Mặc định"

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    send_tele(f"🦈 *SHARK V16:* Đã nạp 25+ nguồn giải (Hạng 1-4). Đang săn bẫy...")

    db = get_all_legacy_data()
    
    # API quét các giải đang mở kèo
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    data = requests.get(api_url, params={'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals'}).json()

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)

        if now_vn < st_vn < now_vn + timedelta(hours=15):
            avg_g, method = find_h2h_exact(db, home, away)
            
            # Phân tích kèo biến thiên (Chân Kinh Idol)
            bm = m['bookmakers'][0]
            lo_p = bm['markets'][0]['outcomes'][0]['price'] # Odd Live
            io_p = sum([b['markets'][0]['outcomes'][0]['price'] for b in m['bookmakers']]) / len(m['bookmakers'])
            
            delta = io_p - lo_p
            action = "---"

            # 1. Bẫy Dụ (Dựa trên H2H chuẩn của Idol)
            if avg_g >= 3.3 and lo_p > 2.15: action = "💣 VẢ MẠNH XỈU (Bẫy Dụ Tài)"
            elif avg_g <= 2.0 and lo_p > 2.20: action = "💣 VẢ MẠNH TÀI (Bẫy Dụ Xỉu)"
            
            # 2. Tiền Ép (Odd giữ nguyên, tiền giảm -> Tài)
            elif 0.01 < delta < 0.04: action = "VẢ TÀI 🔥 (Tiền ép)"
            
            # 3. Biến động Odd
            elif delta < -0.06: action = "VẢ TÀI 🔥 (Odd tăng)"
            elif delta > 0.06: action = "VẢ XỈU ❄️ (Odd giảm)"

            if action != "---":
                send_tele(f"💎 *PHÂN TÍCH:* {home} vs {away}\n"
                          f"🎯 Lệnh: *{action}*\n"
                          f"📊 Nguồn: {method} ({avg_g:.2f} bàn)\n"
                          f"📈 Odd: {io_p:.2f} -> {lo_p:.2f}\n"
                          f"⏰ Đá lúc: {st_vn.strftime('%H:%M')}")

if __name__ == "__main__":
    main()
