import pandas as pd
import requests
import io
import os
from datetime import datetime, timedelta

# --- CẤU HÌNH ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "7981423606:AAFvJ5Xin_L62k-q0lKY8BPpoOa4PSoE7Ys"
TELE_CHAT_ID = "957306386"
DB_FILE = "shark_history_log.csv"

def send_tele(msg):
    url = f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=15)
    except: pass

def audit_results():
    """Hàm kiểm tra kết quả Húp/Gãy và báo cáo tỷ lệ thắng"""
    if not os.path.isfile(DB_FILE): return
    try:
        df = pd.read_csv(DB_FILE)
        waiting_idx = df[df['Status'] == 'WAITING'].index
        if len(waiting_idx) == 0: return
        
        r = requests.get(f"https://api.the-odds-api.com/v4/sports/soccer/scores/?daysFrom=1&apiKey={API_KEY}")
        if r.status_code != 200: return
        scores = r.json()
        
        report = "📝 *TỔNG KẾT KẾT QUẢ PHIÊN TRƯỚC*\n\n"
        hup, gay, has_update = 0, 0, False

        for idx in waiting_idx:
            m_name = df.loc[idx, 'Match']
            s_match = next((s for s in scores if s.get('completed') and 
                          (m_name.split(' vs ')[0][:5].lower() in s['home_team'].lower() or
                           m_name.split(' vs ')[1][:5].lower() in s['away_team'].lower())), None)
            
            if s_match:
                try:
                    h_s, a_s = int(s_match['scores'][0]['score']), int(s_match['scores'][1]['score'])
                    pick, line = df.loc[idx, 'Pick'], float(df.loc[idx, 'Line'])
                    total = h_s + a_s
                    win = False
                    if "XỈU" in pick and total < line: win = True
                    elif "TÀI" in pick and total > line: win = True
                    elif "DƯỚI" in pick and (a_s + line > h_s): win = True
                    elif "TRÊN" in pick and (h_s - line > a_s): win = True
                    
                    res = "✅ HÚP" if win else "❌ GÃY"
                    if win: hup += 1 
                    else: gay += 1
                    df.loc[idx, 'Status'] = res
                    report += f"🏟️ {m_name}\n🎯 {pick} | FT: {h_s}-{a_s} -> *{res}*\n\n"
                    has_update = True
                except: continue

        if has_update:
            win_rate = (hup / (hup + gay)) * 100 if (hup + gay) > 0 else 0
            report += f"📊 *THỐNG KÊ:* Húp {hup} - Gãy {gay}\n🔥 Tỷ lệ rực rỡ: {win_rate:.1f}%"
            df.to_csv(DB_FILE, index=False)
            send_tele(report)
    except: pass

def save_log(match, trap, pick, line):
    new_entry = pd.DataFrame([{'Match': match, 'Trap': trap, 'Pick': pick, 'Line': line, 'Status': 'WAITING'}])
    if not os.path.isfile(DB_FILE): new_entry.to_csv(DB_FILE, index=False)
    else: new_entry.to_csv(DB_FILE, mode='a', header=False, index=False)

def get_rankings_and_db():
    sources = ["E0", "E1", "E2", "E3", "D1", "D2", "SP1", "SP2", "I1", "I2", "F1", "F2", "B1", "BRA.csv", "ARG.csv"]
    all_dfs = []
    for s in sources:
        url = f"https://www.football-data.co.uk/new/{s}" if ".csv" in s else f"https://www.football-data.co.uk/mmz4281/2526/{s}.csv"
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200: all_dfs.append(pd.read_csv(io.StringIO(r.text))[['HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']])
        except: continue
    full_db = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    teams = pd.concat([full_db['HomeTeam'], full_db['AwayTeam']]).unique()
    table = {t: 0 for t in teams if pd.notna(t)}
    for _, row in full_db.iterrows():
        try:
            if row['FTR'] == 'H': table[row['HomeTeam']] += 3
            elif row['FTR'] == 'A': table[row['AwayTeam']] += 3
            else: table[row['HomeTeam']] += 1; table[row['AwayTeam']] += 1
        except: continue
    rankings = {t: r + 1 for r, (t, p) in enumerate(sorted(table.items(), key=lambda x: x[1], reverse=True))}
    return full_db, rankings

def main():
    audit_results()
    db, rankings = get_rankings_and_db()
    api_url = "https://api.the-odds-api.com/v4/sports/soccer/odds/"
    params = {'apiKey': API_KEY, 'regions': 'eu', 'markets': 'spreads,totals'}
    try: data = requests.get(api_url, params=params).json()
    except: return

    now_vn = datetime.now() + timedelta(hours=7)
    for m in data:
        home, away = m['home_team'], m['away_team']
        st_vn = datetime.strptime(m['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
        if now_vn < st_vn < now_vn + timedelta(hours=12):
            h_r = rankings.get(next((k for k in rankings if home[:4].lower() in k.lower()), None))
            a_r = rankings.get(next((k for k in rankings if away[:4].lower() in k.lower()), None))
            
            # --- TÍNH TOÁN LỊCH SỬ THỰC TẾ (H2H) ---
            h2h = db[((db['HomeTeam'].str[:3] == home[:3]) & (db['AwayTeam'].str[:3] == away[:3])) | 
                     ((db['HomeTeam'].str[:3] == away[:3]) & (db['AwayTeam'].str[:3] == home[:3]))]
            avg_g = h2h['FTHG'].add(h2h['FTAG']).head(4).mean() if not h2h.empty else 2.5

            for bm in m.get('bookmakers', [])[:1]:
                mkts = {mk['key']: mk for mk in bm['markets']}
                
                # --- PHÂN TÍCH KÈO CHẤP ---
                if 'spreads' in mkts:
                    l = mkts['spreads']['outcomes'][0].get('point', 0)
                    p = mkts['spreads']['outcomes'][0].get('price', 0)
                    is_trap_hc = (h_r and a_r and abs(h_r - a_r) >= 5 and abs(l) <= 0.5)
                    money_hc = "GIẢM (ÉP DƯỚI)" if p > 2.05 else "TĂNG (ÉP TRÊN)" if p < 1.85 else "ỔN ĐỊNH"
                    if is_trap_hc or money_hc != "ỔN ĐỊNH":
                        pick_hc = "🚨 VẢ MẠNH DƯỚI" if is_trap_hc and p > 2.05 else "THEO DÕI CHẤP"
                        save_log(f"{home} vs {away}", "BẪY CHẤP", pick_hc, abs(l))
                        send_tele(f"🏟️ *NHẬN ĐỊNH KÈO CHẤP*\n⏰ {st_vn.strftime('%H:%M')}\n⚽ {home} vs {away}\n📈 Rank: {h_r} vs {a_r}\n🎯 Chấp: {l} | Odd: {p}\n🪤 Bẫy: {'DỤ TRÊN' if is_trap_hc else 'None'}\n👉 Lệnh: *{pick_hc}*")

                # --- PHÂN TÍCH TÀI XỈU LINH HOẠT (TRỊ KÈO SIÊU CẤP) ---
                if 'totals' in mkts:
                    tl = mkts['totals']['outcomes'][0].get('point', 0)
                    tp = mkts['totals']['outcomes'][0].get('price', 0)
                    
                    # LOGIC BẪY: So sánh độ lệch Sử và Kèo
                    is_du_tai = (avg_g - tl >= 1.5) # Sử cao mà Kèo thấp hơn hẳn -> DỤ TÀI
                    is_du_xiu = (tl - avg_g >= 1.5) # Sử thấp mà Kèo cao hơn hẳn -> DỤ XỈU
                    
                    trap_name = "DỤ TÀI (KÈO THỐI)" if is_du_tai else "DỤ XỈU (KÈO ẢO)" if is_du_xiu else "None"
                    
                    pick_tx = "THEO DÕI TX"
                    if is_du_tai:
                        # Dụ Tài thì Vả Xỉu nếu Odd tăng (tiền thoát khỏi Tài)
                        pick_tx = "🚨 VẢ MẠNH XỈU" if tp > 2.05 else "THEO DÕI XỈU"
                    elif is_du_xiu:
                        # Dụ Xỉu thì Vả Tài nếu Odd giảm (tiền ép vào Tài)
                        pick_tx = "🚨 VẢ MẠNH TÀI" if tp < 1.85 else "THEO DÕI TÀI"
                    else:
                        # Không bẫy thì đánh theo dòng tiền: Odd giảm -> Tài, Odd tăng -> Xỉu
                        if tp < 1.85: pick_tx = "VẢ TÀI"
                        elif tp > 2.05: pick_tx = "VẢ XỈU"
                    
                    if trap_name != "None" or "VẢ" in pick_tx:
                        save_log(f"{home} vs {away}", trap_name, pick_tx, tl)
                        send_tele(f"⚽ *NHẬN ĐỊNH TÀI XỈU*\n⏰ {st_vn.strftime('%H:%M')}\n🏟️ {home} vs {away}\n📜 Sử (H2H): {avg_g:.2f} bàn\n🎯 Mốc Kèo: {tl}\n💰 Odd: {tp}\n🪤 Bẫy: {trap_name}\n👉 Lệnh: *{pick_tx}*")

    send_tele(f"✅ Đã quét xong phiên {now_vn.strftime('%H:%M')}. Đã nạp Logic Bẫy linh hoạt! 🦈")

if __name__ == "__main__":
    main()
