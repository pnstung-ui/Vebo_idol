import pandas as pd
import requests
import io
import os
import sys
from datetime import datetime, timedelta

# --- CẤU HÌNH ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"

def send_tele(msg):
    print(f"--- GỬI TELEGRAM: {msg[:50]}... ---")
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
        print(f"Kết quả gửi: {r.status_code} - {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"Lỗi kết nối Tele: {e}")
        return False

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    
    # 1. TEST THÔNG NÒNG NGAY LẬP TỨC
    print(f"Bắt đầu chạy Shark V27 lúc: {now_vn}")
    send_tele(f"🚨 *SHARK V27 CHÀO IDOL!*\n⏱ Time: {now_vn.strftime('%H:%M:%S')}\n🚀 Radar Odd động đang bắt đầu quét...")

    # 2. LẤY ODD ĐỘNG TỪ API
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals', 'oddsFormat': 'decimal'}
    
    try:
        print("Đang gọi API Odds...")
        response = requests.get(api_url, params=params)
        data = response.json()
        print(f"Tìm thấy {len(data)} trận đấu từ API.")
    except Exception as e:
        print(f"Lỗi API: {e}")
        return

    for m in data:
        home, away = m['home_team'], m['away_team']
        
        # Lấy danh sách Odd của tất cả nhà cái để tính trung bình (Opening động)
        all_over_odds = []
        for bm in m.get('bookmakers', []):
            for mkt in bm['markets']:
                if mkt['key'] == 'totals':
                    all_over_odds.append(mkt['outcomes'][0]['price'])

        if len(all_over_odds) < 2: continue

        avg_market = sum(all_over_odds) / len(all_over_odds) # Odd trung bình (Gốc)
        live_odd = all_over_odds[0] # Odd nhà cái chính (Live)
        delta = avg_market - live_odd # Độ lệch

        action = "---"
        # NGUYÊN TẮC IDOL: ODD GIỮ NGUYÊN - TIỀN TĂNG/GIẢM
        # Nới lỏng mốc 0.01 để thông nòng
        if abs(delta) < 0.02:
            if delta > 0.005: action = "❄️ VẢ XỈU (Tiền tăng - Odd ngang)"
            elif delta < -0.005: action = "🔥 VẢ TÀI (Tiền giảm - Odd ngang)"
        
        # ODD DỊCH CHUYỂN MẠNH
        elif delta > 0.04: action = "❄️ VẢ XỈU (Odd sập mạnh)"
        elif delta < -0.04: action = "🔥 VẢ TÀI (Odd tăng mạnh)"

        if action != "---":
            msg = (f"🆔 *SHARK_V27*\n⚽ {home} vs {away}\n🎯 Lệnh: *{action}*\n"
                   f"📊 Mốc gốc (Avg): {avg_market:.2f}\n📈 Live hiện tại: {live_odd:.2f}")
            send_tele(msg)

    print("Chu kỳ quét kết thúc.")

if __name__ == "__main__":
    main()
