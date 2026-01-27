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
    # Mở rộng nguồn dữ liệu tối đa (Hạng 1-2-3 Châu Âu & Nam Mỹ)
    sources = ["E0", "E1", "E2", "E3", "D1", "D2", "SP1", "SP2", "I1", "I2", "F1", "F2", 
               "N1", "N2", "B1", "B2", "P1", "T1", "G1", "BRA.csv", "ARG.csv", "MEX.csv", "NOR.csv"]
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
    
    # Tính bảng xếp hạng Standings
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

def find_rank(team_name, rankings):
    if team_name in rankings: return rankings[team_name]
    for k in rankings:
        if k in team_name or team_name in k or k[:4] == team_name[:4]: return rankings[k]
    return None

def main():
    now_vn = datetime.now() + timedelta(hours=7)
    send_tele(f"🛰️ *SHARK V52 - SUPREME HUNTER*\n🎯 Chế độ: Bẫy Chân Kinh & Mở rộng giải đấu\n⏰ Khởi chạy: {now_vn.strftime('%H:%M:%S')}")

    db, rankings = get_real_data_and_rankings()
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'spreads,totals'}
    try: data = requests.get(api_url, params=params).json()
    except: return

    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            h_rank = find_rank(home, rankings)
            a_rank = find_rank(away, rankings)
            
            # Tính Sử đối đầu (Avg Goals)
            h2h = db[((db['HomeTeam'].str[:3] == home[:3]) & (db['AwayTeam'].str[:3] == away[:3])) | 
                     ((db['HomeTeam'].str[:3] == away[:3]) & (db['AwayTeam'].str[:3] == home[:3]))]
            avg_g_h2h = h2h['FTHG'].add(h2h['FTAG']).mean() if not h2h.empty else 2.5

            for bm in m.get('bookmakers', [])[:1]:
                mkts = {mk['key']: mk for mk in bm['markets']}
                
                # --- PHÂN TÍCH BẪY (CHÂN KINH) ---
                trap_msg = ""
                # 1. Bẫy Chấp (Position Trap)
                if 'spreads' in mkts and h_rank and a_rank:
                    line = mkts['spreads'].get('point', 0)
                    price = mkts['spreads']['outcomes'][0].get('price', 0)
                    rank_diff = abs(h_rank - a_rank)
                    
                    h_trap = "🔥 DỤ TRÊN (KÈO THỐI)" if rank_diff >= 5 and abs(line) <= 0.5 else "Bình thường"
                    money = "ÉP TRÊN" if price < 1.85 else "ÉP DƯỚI" if price > 2.05 else "ỔN ĐỊNH"
                    
                    if h_trap != "Bình thường" or money != "ỔN ĐỊNH":
                        trap_msg += f"\n🚩 Chấp: {line} | Rank Lệch: {rank_diff}\n🪤 Bẫy: {h_trap}\n💰 Tiền: {money}"

                # 2. Bẫy Tài Xỉu (History Trap)
                if 'totals' in mkts:
                    t_line = mkts['totals'].get('point', 0)
                    t_price = mkts['totals']['outcomes'][0].get('price', 0)
                    
                    tx_trap = "DỤ TÀI" if t_line < (avg_g_h2h - 0.45) else "DỤ XỈU" if t_line > (avg_g_h2h + 0.45) else "Bình thường"
                    
                    if tx_trap != "Bình thường":
                        trap_msg += f"\n⚽ TX: {t_line} (Sử: {avg_g_h2h:.1f})\n🪤 Bẫy TX: {tx_trap}"

                # GỬI BÁO CÁO NẾU PHÁT HIỆN BẤT THƯỜNG
                if trap_msg:
                    header = f"⚽ *{home} vs {away}*\n⏰ {st_vn.strftime('%H:%M')}"
                    if "DỤ TRÊN" in trap_msg and "ÉP DƯỚI" in trap_msg:
                        send_tele(f"🚨 *VẢ MẠNH CỬA DƯỚI* ❄️\n{header}{trap_msg}")
                    else:
                        send_tele(f"📋 *PHÁT HIỆN BẪY:* \n{header}{trap_msg}")

    send_tele(f"✅ Hết phiên quét. Shark vẫn đang rình rập... 🦈")

if __name__ == "__main__":
    main()
