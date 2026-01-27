import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- THÔNG TIN ĐÃ CẬP NHẬT ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "7981423606:AAFvJ5Xin_L62k-q0lKY8BPpoOa4PSoE7Ys"
TELE_CHAT_ID = "957306386"

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
        print(f"📡 Status: {r.status_code} | {r.text}")
        return r.status_code == 200
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        return False

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    # PHÁT SÚNG CHÀO SÂN CỦA IDOL_VEBO_BOT
    send_tele(f"🦈 *IDOL_VEBO_BOT ONLINE!* 🦈\n🚀 Radar Shark V29.1 đã sẵn sàng vả kèo.\n⏰ Khởi động: {now_vn.strftime('%H:%M:%S')}")

    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals,spreads', 'oddsFormat': 'decimal'}
    
    try:
        data = requests.get(api_url, params=params).json()
    except: return

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)

        if now_vn < st_vn < now_vn + timedelta(hours=15):
            for bm in m.get('bookmakers', []):
                mkts = {mk['key']: mk for mk in bm['markets']}
                
                # --- [PHÂN TÍCH TÀI XỈU ĐỘNG] ---
                if 'totals' in mkts:
                    all_overs = [mk['outcomes'][0]['price'] for b in m['bookmakers'] for mk in b['markets'] if mk['key'] == 'totals']
                    if len(all_overs) >= 3:
                        avg_mkt = sum(all_overs) / len(all_overs)
                        live_o = mkts['totals']['outcomes'][0]['price']
                        delta = avg_mkt - live_o

                        action = "---"
                        # CHÂN KINH: ODD NGANG - TIỀN BIẾN (DELTA CỰC NHẠY 0.005)
                        if abs(delta) < 0.02:
                            if delta > 0.005: action = "❄️ VẢ XỈU (Tiền tăng - Odd ngang)"
                            elif delta < -0.005: action = "🔥 VẢ TÀI (Tiền giảm - Odd ngang)"
                        
                        elif delta > 0.04: action = "❄️ VẢ XỈU (Odd giảm/Tiền ép)"
                        elif delta < -0.04: action = "🔥 VẢ TÀI (Odd tăng/Tiền nhả)"

                        if action != "---":
                            send_tele(f"💎 *TÀI XỈU REAL-TIME*\n⚽ {home} vs {away}\n🎯 Lệnh: *{action}*\n📈 Gốc: {avg_mkt:.2f} ➡️ Live: {live_o:.2f}")

                # --- [PHÂN TÍCH CHẤP ĐỘNG] ---
                if 'spreads' in mkts:
                    h_p = mkts['spreads']['outcomes'][0]['price']
                    a_p = mkts['spreads']['outcomes'][1]['price']
                    if h_p < 1.68:
                        send_tele(f"🚩 *KÈO CHẤP ĐỘNG*\n⚽ {home} vs {away}\n🎯 Lệnh: *🔥 VẢ TRÊN {home}*\n💰 Odd ép sập: {h_p:.2f}")
                    elif a_p < 1.68:
                        send_tele(f"🚩 *KÈO CHẤP ĐỘNG*\n⚽ {home} vs {away}\n🎯 Lệnh: *❄️ VẢ DƯỚI {away}*\n💰 Odd ép sập: {a_p:.2f}")

    print("Hoàn thành.")

if __name__ == "__main__":
    main()
