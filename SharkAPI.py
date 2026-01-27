import pandas as pd
import requests
import io
from datetime import datetime, timedelta

# --- CẤU HÌNH ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "7981423606:AAFvJ5Xin_L62k-q0lKY8BPpoOa4PSoE7Ys"
TELE_CHAT_ID = "957306386"

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def get_real_data_and_rankings():
    # Full nguồn giải hạng 1-2 toàn cầu
    sources = ["E0", "E1", "E2", "E3", "D1", "D2", "SP1", "SP2", "I1", "I2", "F1", "F2", 
               "N1", "N2", "B1", "B2", "P1", "T1", "G1", "BRA.csv", "ARG.csv", "NOR.csv", "DEN.csv"]
    all_dfs = []
    for s in sources:
        url = f"https://www.football-data.co.uk/new/{s}" if ".csv" in s else f"https://www.football-data.co.uk/mmz4281/2526/{s}.csv"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                all_dfs.append(df[['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']])
        except: continue
    full_db = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    
    # Tính bảng xếp hạng (Standings)
    teams = pd.concat([full_db['HomeTeam'], full_db['AwayTeam']]).unique()
    table = {team: 0 for team in teams if pd.notna(team)}
    for _, row in full_db.iterrows():
        try:
            if row['FTR'] == 'H': table[row['HomeTeam']] += 3
            elif row['FTR'] == 'A': table[row['AwayTeam']] += 3
            else: table[row['HomeTeam']] += 1; table[row['AwayTeam']] += 1
        except: continue
    rankings = {team: r + 1 for r, (team, pts) in enumerate(sorted(table.items(), key=lambda x: x[1], reverse=True))}
    return full_db, rankings

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    next_run = now_vn + timedelta(hours=1)
    send_tele(f"🛰️ *SHARK V46 - RADAR BẪY CHẤP (MỐC 5 BẬC)*\n🔎 Đang săn tìm kèo thối hạng 1-2...\n⏰ Giờ quét: {now_vn.strftime('%H:%M')}")

    db, rankings = get_real_data_and_rankings()
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'spreads,totals'}
    try: data = requests.get(api_url, params=params).json()
    except: return

    match_count = 0
    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        
        # Quét khung giờ vàng 12 tiếng
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            match_count += 1
            # Lấy hạng (Mapping 3 ký tự đầu)
            h_rank = rankings.get(next((k for k in rankings if k[:3] == home[:3]), None), 15)
            a_rank = rankings.get(next((k for k in rankings if k[:3] == away[:3]), None), 15)
            rank_diff = abs(h_rank - a_rank)
            
            # Lịch sử đối đầu
            h2h = db[((db['HomeTeam'].str[:3] == home[:3]) & (db['AwayTeam'].str[:3] == away[:3])) | 
                     ((db['HomeTeam'].str[:3] == away[:3]) & (db['AwayTeam'].str[:3] == home[:3]))]
            h2h_info = "N/A" if h2h.empty else f"{len(h2h)} trận | {h2h['FTHG'].add(h2h['FTAG']).mean():.1f} bàn"

            for bm in m.get('bookmakers', [])[:1]:
                mkts = {mk['key']: mk for mk in bm['markets']}
                
                if 'spreads' in mkts:
                    line_h = mkts['spreads'].get('point')
                    if line_h is None: continue
                    live_h_p = mkts['spreads']['outcomes'][0]['price'] # Giá cửa đầu tiên (thường là Home)
                    
                    # --- CHÂN KINH DỤ KÈO CHẤP ---
                    h_trap = "NONE"
                    # Nếu chênh lệch >= 5 bậc mà chấp thấp (<= 0.5) => Kèo thối Dụ Trên
                    # Hoặc đội hạng cao hơn lại được chấp => Dụ Trên cực nặng
                    if rank_diff >= 5 and abs(line_h) <= 0.5:
                        h_trap = "DỤ NẰM TRÊN (Kèo Thối)"
                    
                    # --- CHÂN KINH DÒNG TIỀN (MONEY FLOW) ---
                    # Nguyên tắc: Odd giữ nguyên, tiền tăng (giá giảm) thì theo hướng đó. 
                    # Ở đây ta so sánh giá Live với mốc chuẩn 1.90
                    money_flow = "ÉP TRÊN" if live_h_p < 1.80 else "ÉP DƯỚI" if live_h_p > 2.10 else "ỔN ĐỊNH"
                    
                    report = (f"⚽ *{home} vs {away}*\n"
                              f"📈 Rank: {h_rank} vs {a_rank} (Lệch {rank_diff} bậc)\n"
                              f"📜 Sử: {h2h_info}\n"
                              f"🎯 Chấp: {line_h} | Odd: {live_h_p}\n"
                              f"🪤 Bẫy: {h_trap}\n"
                              f"💰 Tiền: {money_flow}")

                    # RA LỆNH VẢ MẠNH: Khi Dụ Trên mà tiền lại ép Dưới (Phá bẫy)
                    if h_trap != "NONE" and money_flow == "ÉP DƯỚI":
                        send_tele(f"🚨 *VẢ MẠNH CỬA DƯỚI* ❄️\n{report}")
                    else:
                        send_tele(f"📋 *BÁO CÁO DỤ KÈO:* \n{report}")

    send_tele(f"✅ *PHIÊN QUÉT HOÀN TẤT*\n📊 Đã soi {match_count} trận.\n🔄 Tự động quét lại lúc: *{next_run.strftime('%H:%M')}*.")

if __name__ == "__main__":
    main()
