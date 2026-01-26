import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- CONFIG ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5Ofo7xw"
TELE_CHAT_ID = "957306386"
FREE_SOURCE = "https://www.football-data.co.uk/new_fixtures.csv"

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=10)
    except: pass

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    # Gửi tin xác nhận hệ thống sống
    send_tele(f"🛰️ *SHARK HYBRID 2026:* Đang quét API & Football-Data...")

    # 1. LẤY DỮ LIỆU THAM CHIẾU TỪ TRANG FREE (FOOTBALL-DATA)
    free_df = None
    try:
        r = requests.get(FREE_SOURCE, timeout=20)
        free_df = pd.read_csv(io.StringIO(r.text), on_bad_lines='skip', engine='python')
    except: print("Lỗi tải trang Free")

    # 2. LẤY DỮ LIỆU BIẾN ĐỘNG TỪ API
    REGIONS = ['soccer_epl', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 'soccer_spain_la_liga', 'soccer_brazil_campeonato', 'soccer_usa_mls']
    for sport in REGIONS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'spreads,totals', 'oddsFormat': 'decimal'}
        try:
            data = requests.get(url, params=params, timeout=15).json()
            for m in data:
                home, away = m['home_team'], m['away_team']
                st = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                if now_vn < st < now_vn + timedelta(hours=12):
                    # Tìm trận tương ứng bên trang Free để lấy tham chiếu Max/Avg
                    ref_row = None
                    if free_df is not None:
                        # Tìm kiếm tương đối tên đội
                        ref_row = free_df[(free_df['HomeTeam'].str.contains(home[:5], na=False)) | 
                                          (free_df['AwayTeam'].str.contains(away[:5], na=False))].head(1)

                    bm = m['bookmakers'][0]
                    mkts = {mk['key']: mk for mk in bm['markets']}
                    
                    # --- PHÂN TÍCH CHÂN KINH ---
                    # Lấy Odd hiện tại (lo) từ API
                    if 'spreads' in mkts:
                        cp = mkts['spreads']['outcomes']
                        line_cp, lo_h, lo_a = cp[0]['point'], cp[0]['price'], cp[1]['price']
                        
                        # Tham chiếu Odd mở (io) từ trang Free nếu có
                        io_h = float(ref_row['MaxH'].values[0]) if ref_row is not None and 'MaxH' in ref_row else lo_h
                        
                        action, tag = "---", "---"
                        # Logic Idol: Hạ kèo + Tăng tiền -> Vả Dưới
                        if lo_h > io_h + 0.05:
                            action, tag = f"VẢ DƯỚI ({away})", "💣 BẪY DỤ TRÊN"
                        elif lo_h < io_h - 0.08:
                            action, tag = f"VẢ TRÊN ({home})", "🔥 TIỀN ÉP TRÊN"

                        if action != "---":
                            msg = (f"🛡️ *KÈO CHẤP (HYBRID)*\n🏟️ {home} vs {away}\n"
                                   f"🎯 Lệnh: *{action}*\n🚩 Tín hiệu: {tag}\n"
                                   f"📊 Biến động: {io_h:.2f} ➔ {lo_h:.2f}\n"
                                   f"⏰ Còn {int((st-now_vn).total_seconds()/60)}p")
                            send_tele(msg)

                    if 'totals' in mkts:
                        tx = mkts['totals']['outcomes']
                        tx_line, lo_o = tx[0]['point'], tx[0]['price']
                        io_o = float(ref_row['Max>2.5'].values[0]) if ref_row is not None and 'Max>2.5' in ref_row else lo_o

                        # Logic Tài Xỉu: Odd tăng thì Tài, Tiền giảm thì Xỉu
                        action_tx = ""
                        if lo_o > io_o + 0.04: action_tx = "VẢ TÀI 🔥"
                        elif lo_o < io_o - 0.04: action_tx = "VẢ XỈU ❄️"

                        if action_tx:
                            send_tele(f"⚽ *TÀI XỈU (HYBRID)*\n🏟️ {home} vs {away}\n🎯 Lệnh: *{action_tx}*\n📊 Line {tx_line}: {io_o:.2f}➔{lo_o:.2f}")

        except: continue

if __name__ == "__main__":
    main()
