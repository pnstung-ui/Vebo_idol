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
    # Đã bổ sung hạng 1 & 2 của các giải lớn: Hà Lan, Đức, Pháp, Ý, Tây Ban Nha, Anh
    sources = [
        "E0", "E1", "E2", "E3",  # Anh: Premier, Championship, L1, L2
        "D1", "D2",              # Đức: Bundesliga 1 & 2
        "SP1", "SP2",            # Tây Ban Nha: La Liga 1 & 2
        "I1", "I2",              # Ý: Serie A & B
        "F1", "F2",              # Pháp: Ligue 1 & 2
        "N1", "B1", "P1", "T1",  # Hà Lan, Bỉ, Bồ Đào Nha, Thổ Nhĩ Kỳ
        "G1", "SC0",             # Hy Lạp, Scotland
        "BRA.csv", "ARG.csv",    # Nam Mỹ
        "NOR.csv", "DEN.csv", "SWE.csv" # Bắc Âu
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
    
    # Tính Standings cho tất cả các giải đã nạp
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
    next_run = now_vn + timedelta(hours=1)
    send_tele(f"🛰️ *SHARK V43 - FULL DIVISIONS ONLINE*\n🔎 Quét hạng 1-2 toàn hệ thống...\n⏰ Bắt đầu: {now_vn.strftime('%H:%M')}")

    db, rankings = get_real_data_and_rankings()
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals,spreads'}
    try: data = requests.get(api_url, params=params).json()
    except: return

    match_count = 0
    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            match_count += 1
            h2h = db[(db['HomeTeam'].str[:3] == home[:3]) | (db['AwayTeam'].str[:3] == away[:3])]
            avg_g_h2h = h2h['FTHG'].add(h2h['FTAG']).mean() if not h2h.empty else 2.5
            h_rank = rankings.get(next((k for k in rankings if k[:3] == home[:3]), None), 15)
            a_rank = rankings.get(next((k for k in rankings if k[:3] == away[:3]), None), 15)
            rank_diff = abs(h_rank - a_rank)

            for bm in m.get('bookmakers', [])[:1]:
                mkts = {mk['key']: mk for mk in bm['markets']}
                
                # --- PHÂN TÍCH TÀI XỈU ---
                if 'totals' in mkts:
                    line = mkts['totals'].get('point')
                    outcomes = mkts['totals'].get('outcomes', [])
                    if line and outcomes:
                        live_p = outcomes[0]['price']
                        all_prices = [mk['outcomes'][0]['price'] for b in m['bookmakers'] for mk in b['markets'] if mk['key']=='totals']
                        avg_p_world = sum(all_prices)/len(all_prices) if all_prices else live_p
                        
                        tx_trap = "TAI" if line < (avg_g_h2h - 0.45) else "XIU" if line > (avg_g_h2h + 0.45) else "NONE"
                        tx_money = "TAI" if live_p < (avg_p_world - 0.04) else "XIU" if live_p > (avg_p_world + 0.04) else "NONE"
                        
                        report_tx = f"⚽ *{home} vs {away}*\n⏰ {st_vn.strftime('%H:%M')}\n📊 Sử: {avg_g_h2h:.1f} | Mốc: {line}\n🪤 Bẫy: {tx_trap} | 💰 Tiền: {tx_money}"
                        
                        if tx_trap == tx_money and tx_trap != "NONE":
                            send_tele(f"🚨 *VẢ MẠNH {tx_trap}* 🔥\n{report_tx}")
                        else:
                            send_tele(f"📋 *BÁO CÁO TX:* \n{report_tx}")

                # --- PHÂN TÍCH CHẤP ---
                if 'spreads' in mkts:
                    line_h = mkts['spreads'].get('point')
                    if line_h is not None:
                        live_h_p = mkts['spreads']['outcomes'][0]['price']
                        h_trap = "DU_TREN" if (rank_diff >= 9 and 0 < abs(line_h) <= 0.5) else "NONE"
                        h_money = "DUOI" if live_h_p > 2.05 else "TREN" if live_h_p < 1.75 else "NONE"
                        
                        status_h = f"🚩 *CHẤP: {home} vs {away}*\n📉 Rank: {h_rank} vs {a_rank} ({rank_diff} bậc)\n🪤 Bẫy: {h_trap} | 💰 Tiền: {h_money} | Mốc: {line_h}"
                        
                        if rank_diff >= 9 and h_trap == "DU_TREN" and h_money == "DUOI":
                            send_tele(f"🚨 *VẢ MẠNH DƯỚI* ❄️\n{status_h}")
                        else:
                            send_tele(f"📋 *BÁO CÁO CHẤP:* \n{status_h}")

    footer = (f"✅ *PHIÊN QUÉT HOÀN TẤT*\n"
              f"📊 Đã soi xong {match_count} trận hạng 1&2.\n"
              f"🔄 Tự động quét lại lúc: *{next_run.strftime('%H:%M')}*.")
    send_tele(footer)

if __name__ == "__main__":
    main()
