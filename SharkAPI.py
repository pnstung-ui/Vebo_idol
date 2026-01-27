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

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    send_tele(f"📡 *SHARK REAL-TIME V26*\n🔄 Đang phân tích Odd động từ API...")

    # 1. LẤY DỮ LIỆU TỪ API (Lấy nhiều nhà cái để so sánh)
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals', 'oddsFormat': 'decimal'}
    data = requests.get(api_url, params=params).json()

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)

        if now_vn < st_vn < now_vn + timedelta(hours=15):
            # 2. TÍNH TOÁN ODD ĐỘNG (Không dùng số chết nữa)
            all_over_odds = []
            for bm in m['bookmakers']:
                for mkt in bm['markets']:
                    if mkt['key'] == 'totals':
                        all_over_odds.append(mkt['outcomes'][0]['price']) # Lấy giá Tài (Over)

            if len(all_over_odds) < 2: continue # Không đủ dữ liệu so sánh thì bỏ qua

            avg_market_over = sum(all_over_odds) / len(all_over_odds) # Trung bình thị trường (Opening giả lập)
            live_over = all_over_odds[0] # Lấy nhà cái đầu tiên làm Live (ví dụ Bet365/Pinnacle)
            
            # 3. BIẾN THIÊN (Delta) - TIỀN TĂNG/GIẢM
            # Delta dương (>0): Live thấp hơn trung bình -> Tiền đang đổ vào, ép Odd giảm.
            # Delta âm (<0): Live cao hơn trung bình -> Nhà cái đang thả, dụ người chơi.
            delta = avg_market_over - live_over
            
            action = "---"
            # ÁP DỤNG NGUYÊN TẮC IDOL VỚI ODD ĐỘNG:
            
            # BÀI 1: ODD GIỮ NGUYÊN, TIỀN TĂNG THÌ XỈU (Delta rất nhỏ nhưng vẫn có xu hướng ép)
            if abs(delta) < 0.02 and delta > 0: 
                action = "❄️ VẢ XỈU (Tiền tăng - Odd ngang)"
            
            # BÀI 2: ODD GIỮ NGUYÊN, TIỀN GIẢM THÌ TÀI
            elif abs(delta) < 0.02 and delta < 0:
                action = "🔥 VẢ TÀI (Tiền giảm - Odd ngang)"

            # BÀI 3: ODD GIẢM THÌ XỈU (Live thấp hơn hẳn trung bình)
            elif delta > 0.05:
                action = "❄️ VẢ XỈU (Odd giảm mạnh)"

            # BÀI 4: ODD TĂNG THÌ TÀI (Live cao hơn hẳn trung bình)
            elif delta < -0.05:
                action = "🔥 VẢ TÀI (Odd tăng mạnh)"

            if action != "---":
                msg = (f"⚽ *{home} vs {away}*\n"
                       f"🎯 Lệnh: *{action}*\n"
                       f"📊 Opening (Avg): {avg_market_over:.2f}\n"
                       f"📈 Live: {live_over:.2f}\n"
                       f"📉 Biến động: {'+' if delta>0 else ''}{delta:.2f}")
                send_tele(msg)

if __name__ == "__main__":
    main()
