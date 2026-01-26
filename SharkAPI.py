import pandas as pd
import requests
import os
from datetime import datetime, timedelta

# --- CONFIG ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c" # API Real-time
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"

# Danh sách các giải đấu cần quét sát sao
REGIONS = ['soccer_epl', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 'soccer_spain_la_liga', 
           'soccer_brazil_campeonato', 'soccer_usa_mls', 'soccer_portugal_primeira_liga']

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
    except: pass

def main():
    now_gmt7 = datetime.now() + timedelta(hours=7)
    # Tin nhắn khởi động
    send_tele(f"📡 *SHARK REAL-TIME:* Đang quét biến động API...")

    for sport in REGIONS:
        api_url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {
            'apiKey': API_KEY,
            'regions': 'eu', # Lấy các nhà cái Châu Âu uy tín
            'markets': 'spreads,totals',
            'oddsFormat': 'decimal'
        }
        try:
            r = requests.get(api_url, params=params, timeout=15)
            if r.status_code != 200: continue
            data = r.json()
            
            for m in data:
                home, away = m['home_team'], m['away_team']
                st = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                # Chỉ quét trận trong vòng 6 tiếng tới (Thời điểm Odd biến động mạnh nhất)
                if now_gmt7 < st < now_gmt7 + timedelta(hours=6):
                    # Lấy dữ liệu từ nhà cái đầu tiên (Thường là Pinnacle/Bet365 làm gốc)
                    # Trong API, 'bookmakers' được sắp xếp theo độ uy tín
                    bm = m['bookmakers'][0]
                    mkts = {mk['key']: mk for mk in bm['markets']}
                    
                    action_chap, action_tx = "---", "---"
                    tag_chap, tag_tx = "---", "---"

                    # 1. PHÂN TÍCH KÈO CHẤP (Spreads)
                    if 'spreads' in mkts:
                        outcome = mkts['spreads']['outcomes']
                        # Giả định: outcome[0] là đội Home
                        line = outcome[0]['point']
                        price_h = outcome[0]['price']
                        price_a = outcome[1]['price']
                        
                        # Logic: Nếu kèo giảm (vd từ -1.5 xuống -1.25) mà tiền tăng -> Vả ngược
                        # API không có Max/Avg như CSV nên ta so sánh giá trị Odd hiện tại
                        # Nếu Odd cửa nào > 2.10 (Nhà cái đang nhả tiền) -> Cẩn thận Bẫy
                        if price_h > 2.15: 
                            action_chap = f"VẢ DƯỚI ({away})"
                            tag_chap = "💣 BẪY DỤ TRÊN (Tiền cao bất thường)"
                        elif price_a > 2.15:
                            action_chap = f"VẢ TRÊN ({home})"
                            tag_chap = "💣 BẪY DỤ DƯỚI (Tiền cao bất thường)"
                        elif price_h < 1.75:
                            action_chap = f"VẢ TRÊN ({home})"
                            tag_chap = "🔥 TIỀN ÉP TRÊN"
                        elif price_a < 1.75:
                            action_chap = f"VẢ DƯỚI ({away})"
                            tag_chap = "❄️ TIỀN ÉP DƯỚI"

                    # 2. PHÂN TÍCH TÀI XỈU (Totals)
                    if 'totals' in mkts:
                        out_tx = mkts['totals']['outcomes']
                        tx_line = out_tx[0]['point']
                        p_over = out_tx[0]['price']
                        p_under = out_tx[1]['price']
                        
                        # Chân kinh: Odd tăng thì Tài, Tiền giảm (Odd thấp) thì Xỉu
                        if p_over > 2.15: 
                            action_tx = "VẢ TÀI 🔥 (Odd tăng)"
                        elif p_over < 1.78:
                            action_tx = "VẢ XỈU ❄️ (Tiền giảm/Ép Xỉu)"

                    # Gửi tin nhắn nếu có kèo sáng
                    if action_chap != "---" or action_tx != "---":
                        diff = int((st - now_gmt7).total_seconds() / 60)
                        msg = (f"🏪 *SHARK REAL-TIME RADAR*\n"
                               f"🏟️ {home} vs {away}\n"
                               f"⏰ {st.strftime('%H:%M')} (Đá sau {diff}p)\n"
                               f"--------------------------\n"
                               f"🛡️ *KÈO CHẤP:* {action_chap}\n"
                               f"🚩 Tín hiệu: {tag_chap}\n"
                               f"⚽ *TÀI XỈU:* {action_tx}\n"
                               f"📊 Odd {tx_line}: T{p_over:.2f} | X{p_under:.2f}")
                        send_tele(msg)
        except Exception as e:
            print(f"Lỗi: {e}")
            continue

if __name__ == "__main__":
    main()
