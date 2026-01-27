import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- CONFIG ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def get_h2h_db():
    all_dfs = []
    # Quét sạch các giải hạng 1-4 để lấy gốc H2H
    sources = ["E0", "E1", "E2", "E3", "D1", "D2", "SP1", "SP2", "I1", "I2", "F1", "F2", "BRA.csv", "ARG.csv"]
    for f in sources:
        url = f"https://www.football-data.co.uk/mmz4281/2526/{f}.csv" if len(f) <= 3 else f"https://www.football-data.co.uk/new/{f}"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200: all_dfs.append(pd.read_csv(io.StringIO(r.text)))
        except: continue
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else None

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    # TEST THÔNG NÒNG: Nhắn ngay khi chạy
    send_tele(f"🔥 *SHARK V23 RADAR ONLINE*\n🛰️ Đang quét toàn bộ Odd động API...")

    db = get_h2h_db()
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    # Quét cả Tài Xỉu (totals) và Chấp (spreads)
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals,spreads', 'oddsFormat': 'decimal'}
    data = requests.get(api_url, params=params).json()

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)

        # Quét các trận trong 15 tiếng tới
        if now_vn < st_vn < now_vn + timedelta(hours=15):
            h2h = db[((db['HomeTeam'].str.contains(home[:4], case=False, na=False)) & (db['AwayTeam'].str.contains(away[:4], case=False, na=False)))]
            avg_g = h2h['FTHG'].add(h2h['FTAG']).mean() if not h2h.empty else 2.5
            
            for bm in m['bookmakers']:
                mkts = {mk['key']: mk for mk in bm['markets']}
                
                # --- [1] LOGIC TÀI XỈU (VẢ CẢ TÀI LẪN XỈU) ---
                if 'totals' in mkts:
                    o_p = mkts['totals']['outcomes'][0]['price'] # Odd Tài
                    u_p = mkts['totals']['outcomes'][1]['price'] # Odd Xỉu
                    
                    # Bẫy Dụ: Sử nổ (>3.0) mà Odd Tài > 2.0 -> VẢ XỈU ❄️
                    if avg_g >= 3.0 and o_p > 2.00:
                        send_tele(f"⚽ {home} vs {away}\n🎯 *Lệnh: 💣 VẢ MẠNH XỈU*\n📊 Lý do: Dụ Tài (Sử {avg_g:.1f} - Odd {o_p:.2f})")
                    
                    # Bẫy Dụ: Sử khô (<2.0) mà Odd Xỉu > 2.0 -> VẢ TÀI 🔥
                    elif avg_g <= 2.0 and u_p > 2.00:
                        send_tele(f"⚽ {home} vs {away}\n🎯 *Lệnh: 💣 VẢ MẠNH TÀI*\n📊 Lý do: Dụ Xỉu (Sử {avg_g:.1f} - Odd {u_p:.2f})")

                # --- [2] LOGIC KÈO CHẤP (VẢ CẢ TRÊN LẪN DƯỚI) ---
                if 'spreads' in mkts:
                    h_p = mkts['spreads']['outcomes'][0]['price'] # Đội nhà (Thường là kèo trên)
                    a_p = mkts['spreads']['outcomes'][1]['price'] # Đội khách (Thường là kèo dưới)
                    
                    # Tiền ép kèo trên (Sập dưới 1.65)
                    if h_p < 1.65:
                        send_tele(f"⚽ {home} vs {away}\n🎯 *Lệnh: 🔥 VẢ TRÊN {home}*\n📈 Lý do: TIỀN ÉP CHẾT CỬA ({h_p:.2f})")
                    
                    # Tiền ép kèo dưới (Odd khách sập sâu)
                    elif a_p < 1.65:
                        send_tele(f"⚽ {home} vs {away}\n🎯 *Lệnh: ❄️ VẢ DƯỚI {away}*\n📈 Lý do: DÒNG TIỀN ĐỔ VỀ DƯỚI ({a_p:.2f})")

    send_tele(f"✅ Quét xong. Hệ thống Radar đang trực chiến!")

if __name__ == "__main__":
    main()
