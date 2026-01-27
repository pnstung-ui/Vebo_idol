import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- THÔNG TIN CHUẨN ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "7981423606:AAFvJ5Xin_L62k-q0lKY8BPpoOa4PSoE7Ys"
TELE_CHAT_ID = "957306386"

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
        return r.status_code == 200
    except: return False

def get_h2h_data():
    all_dfs = []
    # Quét full nguồn từ Châu Âu đến Nam Mỹ
    sources = ["E0", "E1", "D1", "D2", "SP1", "I1", "F1", "BRA.csv", "ARG.csv"]
    for f in sources:
        url = f"https://www.football-data.co.uk/mmz4281/2526/{f}.csv" if len(f) <= 3 else f"https://www.football-data.co.uk/new/{f}"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200: all_dfs.append(pd.read_csv(io.StringIO(r.text)))
        except: continue
    return pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    send_tele(f"🛰️ *SHARK V30: ĐÃ XIẾT KÈO CHUẨN*\n🎯 Radar đang quét Odd động & Check sử Nam Mỹ...")

    db = get_h2h_data()
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals,spreads', 'oddsFormat': 'decimal'}
    
    try:
        data = requests.get(api_url, params=params).json()
    except: return

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)

        if now_vn < st_vn < now_vn + timedelta(hours=12):
            # 1. LẤY SỬ BÀN THẮNG (H2H)
            h2h = db[((db['HomeTeam'].str.contains(home[:4], na=False)) & (db['AwayTeam'].str.contains(away[:4], na=False)))]
            avg_g = h2h['FTHG'].add(h2h['FTAG']).mean() if not h2h.empty else 2.5
            
            # 2. XỬ LÝ ODD ĐỘNG (Gom nhóm để tránh báo lung tung)
            all_overs = []
            for bm in m.get('bookmakers', []):
                for mk in bm['markets']:
                    if mk['key'] == 'totals':
                        all_overs.append(mk['outcomes'][0]['price'])
            
            if len(all_overs) >= 3:
                avg_market = sum(all_overs) / len(all_overs)
                live_odd = all_overs[0] # Lấy nhà cái chính để đại diện
                delta = avg_market - live_odd
                
                # --- XIẾT CHÂN KINH TÀI XỈU ---
                action_tx = ""
                # Bẫy Dụ Tài -> VẢ XỈU: Sử nổ (>3.0) nhưng Odd Tài thị trường thả cao (>2.10) và Live đang bị ép sụt
                if avg_g >= 3.0 and live_odd > 2.05 and delta > 0.05:
                    action_tx = "❄️ VẢ XỈU (Dụ Tài - Tiền ép Xỉu)"
                # Bẫy Dụ Xỉu -> VẢ TÀI: Sử khô (<2.2) nhưng Odd Xỉu thả cao và Live đang tăng (Tiền giảm)
                elif avg_g <= 2.2 and live_odd > 2.05 and delta < -0.05:
                    action_tx = "🔥 VẢ TÀI (Dụ Xỉu - Tiền giảm)"

                if action_tx:
                    msg = (f"⚽ *{home} vs {away}*\n🎯 Lệnh: *{action_tx}*\n"
                           f"📊 Sử (Avg G): {avg_g:.1f}\n📈 Gốc: {avg_market:.2f} ➡️ Live: {live_odd:.2f}")
                    send_tele(msg)

            # 3. KÈO CHẤP (Chỉ báo khi ép cực mạnh)
            for bm in m.get('bookmakers', [])[:1]: # Chỉ lấy 1 nhà cái uy tín nhất
                for mk in bm['markets']:
                    if mk['key'] == 'spreads':
                        h_p = mk['outcomes'][0]['price']
                        a_p = mk['outcomes'][1]['price']
                        if h_p < 1.60:
                            send_tele(f"🚩 *KÈO CHẤP*\n⚽ {home} vs {away}\n🎯 Lệnh: *🔥 VẢ TRÊN {home}*\n💰 Tiền ép chết: {h_p:.2f}")
                        elif a_p < 1.60:
                            send_tele(f"🚩 *KÈO CHẤP*\n⚽ {home} vs {away}\n🎯 Lệnh: *❄️ VẢ DƯỚI {away}*\n💰 Tiền ép chết: {a_p:.2f}")

if __name__ == "__main__":
    main()
