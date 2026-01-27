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
    sources = ["E0", "E1", "E2", "E3", "D1", "D2", "SP1", "SP2", "I1", "I2", "F1", "F2", "N1", "N2", "B1", "B2", "P1", "T1", "G1", "BRA.csv", "ARG.csv"]
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
    send_tele(f"🛰️ *SHARK V47 - CHẾ ĐỘ BÁO CÁO CƯỠNG BỨC*\n🔎 Sát thủ bẫy chấp mốc 5 bậc...\n⏰ Quét lúc: {now_vn.strftime('%H:%M')}")

    db, rankings = get_real_data_and_rankings()
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'spreads,totals'}
    try: data = requests.get(api_url, params=params).json()
    except: return

    match_count = 0
    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            match_count += 1
            # Fix Mapping: Tìm tên gần đúng nhất
            h_rank = rankings.get(next((k for k in rankings if home[:4] in k or k[:4] in home), None), 15)
            a_rank = rankings.get(next((k for k in rankings if away[:4] in k or k[:4] in away), None), 15)
            rank_diff = abs(h_rank - a_rank)
            
            # Khởi tạo báo cáo cơ bản
            report_msg = f"⚽ *{home} vs {away}*\n⏰ {st_vn.strftime('%H:%M')}\n📈 Rank: {h_rank} vs {a_rank} (Lệch {rank_diff})"
            
            for bm in m.get('bookmakers', [])[:1]:
                mkts = {mk['key']: mk for mk in bm['markets']}
                
                # --- PHẦN CHẤP ---
                if 'spreads' in mkts:
                    line_h = mkts['spreads'].get('point', 0)
                    live_h_p = mkts['spreads']['outcomes'][0]['price']
                    
                    # Logic Dụ Trên: Lệch >= 5 bậc mà chấp <= 0.5
                    h_trap = "🔥 DỤ TRÊN (KÈO THỐI)" if rank_diff >= 5 and abs(line_h) <= 0.5 else "Bình thường"
                    
                    # Logic Dòng tiền (Money Flow)
                    money_flow = "ÉP TRÊN" if live_h_p < 1.85 else "ÉP DƯỚI" if live_h_p > 2.05 else "ỔN ĐỊNH"
                    
                    detail = f"\n🎯 Chấp: {line_h} | Odd: {live_h_p}\n🪤 Bẫy: {h_trap}\n💰 Tiền: {money_flow}"
                    
                    if h_trap != "Bình thường" and money_flow == "ÉP DƯỚI":
                        send_tele(f"🚨 *VẢ MẠNH CỬA DƯỚI* ❄️\n{report_msg}{detail}")
                    else:
                        send_tele(f"📋 *BÁO CÁO:* \n{report_msg}{detail}")

    send_tele(f"✅ *XONG PHIÊN:* Soi được {match_count} trận.\n🔄 Quét lại lúc: *{next_run.strftime('%H:%M')}*.")

if __name__ == "__main__":
    main()
