import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- CẤU HÌNH THÔNG TIN ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "7981423606:AAFvJ5Xin_L62k-q0lKY8BPpoOa4PSoE7Ys"
TELE_CHAT_ID = "957306386"

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except:
        pass

def get_real_data_and_rankings():
    """Quét dữ liệu thật từ 22 giải đấu và tự tính bảng xếp hạng"""
    sources = [
        "E0", "E1", "E2", "E3", "EC", "D1", "D2", "SP1", "SP2", 
        "I1", "I2", "F1", "F2", "N1", "B1", "P1", "T1", "G1", "SC0",
        "NOR.csv", "DEN.csv", "SWE.csv", "BRA.csv", "ARG.csv", "MEX.csv"
    ]
    all_dfs = []
    for s in sources:
        url = f"https://www.football-data.co.uk/new/{s}" if ".csv" in s else f"https://www.football-data.co.uk/mmz4281/2526/{s}.csv"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                cols = ['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']
                all_dfs.append(df[[c for c in cols if c in df.columns]])
        except: continue
    
    if not all_dfs: return pd.DataFrame(), {}
    
    full_db = pd.concat(all_dfs, ignore_index=True)
    
    # Tính bảng xếp hạng (Standings)
    teams = pd.concat([full_db['HomeTeam'], full_db['AwayTeam']]).unique()
    table = {team: 0 for team in teams if pd.notna(team)}
    for _, row in full_db.iterrows():
        try:
            if row['FTR'] == 'H': table[row['HomeTeam']] += 3
            elif row['FTR'] == 'A': table[row['AwayTeam']] += 3
            else: 
                table[row['HomeTeam']] += 1
                table[row['AwayTeam']] += 1
        except: continue
    
    sorted_table = sorted(table.items(), key=lambda x: x[1], reverse=True)
    rankings = {team: rank + 1 for rank, (team, pts) in enumerate(sorted_table)}
    return full_db, rankings

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    send_tele(f"🔱 *SHARK V40: TOTAL PREDATOR ONLINE*\n🌍 Đang quét 22 giải đấu & Bẫy Chân Kinh...")

    db, rankings = get_real_data_and_rankings()
    
    # Lấy Odd động từ API
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals,spreads', 'oddsFormat': 'decimal'}
    try:
        data = requests.get(api_url, params=params).json()
    except: return

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)

        # Chỉ quét các trận trong vòng 15 tiếng tới
        if now_vn < st_vn < now_vn + timedelta(hours=15):
            # 1. PHÂN TÍCH SỬ & RANK
            h2h = db[((db['HomeTeam'].str.contains(home[:4], na=False)) & (db['AwayTeam'].str.contains(away[:4], na=False)))]
            avg_g_h2h = h2h['FTHG'].add(h2h['FTAG']).mean() if not h2h.empty else 2.5
            h_rank, a_rank = rankings.get(home, 10), rankings.get(away, 10)
            rank_diff = abs(h_rank - a_rank)

            for bm in m.get('bookmakers', [])[:1]:
                mkts = {mk['key']: mk for mk in bm['markets']}

                # --- CHÂN KINH TÀI XỈU ---
                if 'totals' in mkts:
                    all_lines = [mk['point'] for b in m['bookmakers'] for mk in b['markets'] if mk['key']=='totals']
                    avg_line_stable = sum(all_lines)/len(all_lines)
                    all_prices = [mk['outcomes'][0]['price'] for b in m['bookmakers'] for mk in b['markets'] if mk['key']=='totals']
                    avg_price_market = sum(all_prices)/len(all_prices)
                    live_price = mkts['totals']['outcomes'][0]['price']

                    tx_trap = "TAI" if avg_line_stable < (avg_g_h2h - 0.4) else "XIU" if avg_line_stable > (avg_g_h2h + 0.4) else "NONE"
                    tx_money = "TAI" if live_price < (avg_price_market - 0.04) else "XIU" if live_price > (avg_price_market + 0.04) else "NONE"

                    if tx_trap == tx_money and tx_trap != "NONE":
                        send_tele(f"🚨 *VẢ MẠNH {tx_trap}* 🔥\n⚽ {home} vs {away}\n🪤 Bẫy: {tx_trap} | 💰 Tiền: {tx_money}\n📈 Line: {avg_line_stable:.2f} | Odd: {live_price:.2f}")
                    else:
                        send_tele(f"📋 *BÁO CÁO TX:* {home}-{away}\n🪤 Bẫy: {tx_trap} | 💰 Tiền: {tx_money}")

                # --- CHÂN KINH CHẤP ---
                if 'spreads' in mkts:
                    all_h_lines = [mk['point'] for b in m['bookmakers'] for mk in b['markets'] if mk['key']=='spreads']
                    avg_h_line = sum(all_h_lines)/len(all_h_lines)
                    h_live_price = mkts['spreads']['outcomes'][0]['price']

                    h_trap = "DU_TREN" if (rank_diff >= 9 and 0 < abs(avg_h_line) <= 0.5) else "NONE"
                    h_money = "DUOI" if h_live_price > 2.05 else "TREN" if h_live_price < 1.80 else "NONE"

                    if h_trap == "DU_TREN" and h_money == "DUOI":
                        send_tele(f"🚨 *VẢ MẠNH DƯỚI* ❄️\n⚽ {home} vs {away}\n🚩 Cách {rank_diff} bậc | Line: {avg_h_line}\n🪤 Bẫy: {h_trap} | 💰 Tiền: {h_money}")
                    else:
                        send_tele(f"📋 *BÁO CÁO CHẤP:* {home}-{away}\n🚩 Cách {rank_diff} bậc | Bẫy: {h_trap}")

if __name__ == "__main__":
    main()
