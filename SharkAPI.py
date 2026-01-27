import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- THÔNG TIN ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "7981423606:AAFvJ5Xin_L62k-q0lKY8BPpoOa4PSoE7Ys"
TELE_CHAT_ID = "957306386"

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def get_real_data_and_rankings():
    sources = ["E0", "E1", "D1", "D2", "SP1", "I1", "F1", "N1", "B1", "P1", "T1", "G1", "BRA.csv", "ARG.csv", "NOR.csv", "DEN.csv"]
    all_dfs = []
    for s in sources:
        url = f"https://www.football-data.co.uk/new/{s}" if ".csv" in s else f"https://www.football-data.co.uk/mmz4281/2526/{s}.csv"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                df = pd.read_csv(io.StringIO(r.text))
                all_dfs.append(df[['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']])
        except: continue
    if not all_dfs: return pd.DataFrame(), {}
    full_db = pd.concat(all_dfs, ignore_index=True)
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
    rankings = {team: r + 1 for r, (team, pts) in enumerate(sorted(table.items(), key=lambda x: x[1], reverse=True))}
    return full_db, rankings

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    send_tele(f"🛰️ *SHARK V41.2 - FIX BUG POINT*\n🔎 Đang quét lại hệ thống...")

    db, rankings = get_real_data_and_rankings()
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals,spreads'}
    try:
        data = requests.get(api_url, params=params).json()
    except: return

    for m in data:
        home, away = m['home_team'], m['away_team']
        h2h = db[(db['HomeTeam'].str[:3] == home[:3]) | (db['AwayTeam'].str[:3] == away[:3])]
        avg_g_h2h = h2h['FTHG'].add(h2h['FTAG']).mean() if not h2h.empty else 2.5
        h_rank = rankings.get(next((k for k in rankings if k[:3] == home[:3]), None), 10)
        a_rank = rankings.get(next((k for k in rankings if k[:3] == away[:3]), None), 10)
        rank_diff = abs(h_rank - a_rank)

        for bm in m.get('bookmakers', [])[:1]:
            mkts = {mk['key']: mk for mk in bm['markets']}
            
            # --- 1. PHÂN TÍCH TÀI XỈU (FIXED KeyError) ---
            if 'totals' in mkts:
                # Kiểm tra an toàn xem có key 'point' không
                line = mkts['totals'].get('point')
                if line is None: continue # Bỏ qua nếu không có mốc kèo
                
                outcomes = mkts['totals'].get('outcomes', [])
                if len(outcomes) < 2: continue
                
                live_p = outcomes[0]['price']
                all_prices = [mk['outcomes'][0]['price'] for b in m['bookmakers'] for mk in b['markets'] if mk['key']=='totals' and len(mk['outcomes'])>0]
                avg_p_world = sum(all_prices)/len(all_prices) if all_prices else live_p
                
                tx_trap = "TAI" if line < (avg_g_h2h - 0.45) else "XIU" if line > (avg_g_h2h + 0.45) else "NONE"
                tx_money = "TAI" if live_p < (avg_p_world - 0.04) else "XIU" if live_p > (avg_p_world + 0.04) else "NONE"
                
                status_tx = f"⚽ *TX: {home} vs {away}*\n📊 Sử: {avg_g_h2h:.1f} | Mốc: {line}\n🪤 Bẫy: {tx_trap} | 💰 Tiền: {tx_money}"
                
                if tx_trap == tx_money and tx_trap != "NONE":
                    send_tele(f"🚨 *VẢ MẠNH {tx_trap}* 🔥\n{status_tx}")
                else:
                    send_tele(f"📋 *BÁO CÁO TX:* \n{status_tx}")

            # --- 2. PHÂN TÍCH CHẤP ---
            if 'spreads' in mkts:
                line_h = mkts['spreads'].get('point')
                if line_h is None: continue
                
                live_h_p = mkts['spreads']['outcomes'][0]['price']
                h_trap = "DU_TREN" if (rank_diff >= 9 and 0 < abs(line_h) <= 0.5) else "NONE"
                h_money = "DUOI" if live_h_p > 2.05 else "TREN" if live_h_p < 1.75 else "NONE"
                
                status_h = f"🚩 *CHẤP: {home} vs {away}*\n📉 Rank: {h_rank} vs {a_rank}\n🪤 Bẫy: {h_trap} | 💰 Tiền: {h_money} | Mốc: {line_h}"
                
                if rank_diff >= 9 and h_trap == "DU_TREN" and h_money == "DUOI":
                    send_tele(f"🚨 *VẢ MẠNH DƯỚI* ❄️\n{status_h}")
                else:
                    send_tele(f"📋 *BÁO CÁO CHẤP:* \n{status_h}")

if __name__ == "__main__":
    main()
