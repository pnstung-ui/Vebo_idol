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
    # Danh sách 22 giải đấu tiêu chuẩn
    sources = ["E0", "E1", "D1", "D2", "SP1", "I1", "F1", "N1", "B1", "P1", "T1", "G1", "BRA.csv", "ARG.csv", "MEX.csv", "NOR.csv"]
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
    
    # Tính bảng xếp hạng thật
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
    
    send_tele(f"🛰️ *SHARK V42 - PHIÊN TUẦN TRA ĐANG CHẠY*\n🔎 Phạm vi: 12 tiếng tới\n⏰ Bắt đầu lúc: {now_vn.strftime('%H:%M')}")

    db, rankings = get_real_data_and_rankings()
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'totals,spreads'}
    try: data = requests.get(api_url, params=params).json()
    except: return

    match_count = 0
    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        
        # Chỉ quét trong khung giờ vàng 12 tiếng
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            match_count += 1
            h2h = db[(db['HomeTeam'].str[:3] == home[:3]) | (db['AwayTeam'].str[:3] == away[:3])]
            avg_g_h2h = h2h['FTHG'].add(h2h['FTAG']).mean() if not h2h.empty else 2.5
            
            for bm in m.get('bookmakers', [])[:1]:
                mkts = {mk['key']: mk for mk in bm['markets']}
                
                if 'totals' in mkts:
                    line = mkts['totals'].get('point')
                    outcomes = mkts['totals'].get('outcomes', [])
                    if line and outcomes:
                        live_p = outcomes[0]['price']
                        all_prices = [mk['outcomes'][0]['price'] for b in m['bookmakers'] for mk in b['markets'] if mk['key']=='totals' and len(mk['outcomes'])>0]
                        avg_p_world = sum(all_prices)/len(all_prices) if all_prices else live_p
                        
                        tx_trap = "TAI" if line < (avg_g_h2h - 0.45) else "XIU" if line > (avg_g_h2h + 0.45) else "NONE"
                        tx_money = "TAI" if live_p < (avg_p_world - 0.04) else "XIU" if live_p > (avg_p_world + 0.04) else "NONE"
                        
                        report = f"⚽ *{home} vs {away}*\n⏰ Đá lúc: {st_vn.strftime('%H:%M')}\n📊 Sử: {avg_g_h2h:.1f} | Mốc: {line}\n🪤 Bẫy: {tx_trap} | 💰 Tiền: {tx_money}"
                        
                        if tx_trap == tx_money and tx_trap != "NONE":
                            send_tele(f"🚨 *VẢ MẠNH {tx_trap}* 🔥\n{report}")
                        else:
                            send_tele(f"📋 *BÁO CÁO THÁM TỬ:* \n{report}")

    # CHỐT PHIÊN TUẦN TRA
    footer = (f"✅ *PHIÊN QUÉT HOÀN TẤT*\n"
              f"📊 Đã soi xong {match_count} trận.\n"
              f"🔄 Hệ thống sẽ nghỉ ngơi và tự động quét lại vào lúc: *{next_run.strftime('%H:%M')}*.")
    send_tele(footer)

if __name__ == "__main__":
    main()
