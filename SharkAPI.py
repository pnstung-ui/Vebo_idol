import requests
from datetime import datetime, timedelta

# --- THÔNG TIN CỦA IDOL ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5Ofo7xw"
TELE_CHAT_ID = "957306386"

# Nhóm giải đấu (The Odds API gom theo khu vực)
REGIONS = ['soccer_epl', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 
           'soccer_spain_la_liga', 'soccer_france_ligue_1', 'soccer_uefa_champs_league',
           'soccer_usa_mls', 'soccer_brazil_campeonato', 'soccer_netherlands_ere_divisie',
           'soccer_norway_eliteserien', 'soccer_japan_j_league', 'soccer_korea_kleague_1']

def shark_scanner():
    now_gmt7 = datetime.now() + timedelta(hours=7)
    print(f"--- Bắt đầu quét lúc: {now_gmt7.strftime('%H:%M')} ---")

    for sport in REGIONS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {
            'apiKey': API_KEY,
            'regions': 'eu', # Lấy kèo các sàn lớn
            'markets': 'totals,h2h', # Tài Xỉu và Kèo Chấp
            'oddsFormat': 'decimal'
        }
        
        try:
            r = requests.get(url, params=params)
            if r.status_code != 200: continue
            data = r.json()
            
            for match in data:
                home = match['home_team']
                away = match['away_team']
                # Chuyển giờ quốc tế sang GMT+7
                start_time = datetime.strptime(match['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                # Chỉ soi các trận sắp đá trong 8h tới để đảm bảo Odd đang "nóng"
                if now_gmt7 < start_time < now_gmt7 + timedelta(hours=8):
                    analyze_odds(match, home, away, start_time, sport)
        except: continue

def analyze_odds(match, home, away, start_time, sport):
    bookmakers = match['bookmakers']
    if not bookmakers: return
    
    # Lấy dữ liệu sàn đầu tiên làm mốc (thường là sàn uy tín nhất trong danh sách)
    bm = bookmakers[0]
    for market in bm['markets']:
        # 1. LOGIC TÀI XỈU
        if market['key'] == 'totals':
            # Outcomes[0] thường là Over (Tài)
            line = market['outcomes'][0]['point']
            over_price = market['outcomes'][0]['price']
            
            action, trap = "---", "---"
            
            # Check bẫy dựa trên Line (Đặc sản của API)
            if line < 2.25 and "norway" in sport: trap = "DỤ TÀI (Giải nổ mà Line thấp)"
            elif line > 2.75 and "italy" in sport: trap = "DỤ XỈU (Giải khô mà Line cao)"
            
            # Logic Tiền ép (Odd giảm sâu)
            if over_price < 1.80:
                action = "VẢ TÀI 🔥"
                if trap == "DỤ XỈU": action = "💣 VẢ TÀI THẬT MẠNH (Bẻ bẫy)"
            elif over_price > 2.20:
                action = "VẢ XỈU ❄️"
                if trap == "DỤ TÀI": action = "💣 VẢ XỈU THẬT MẠNH (Bẻ bẫy)"
            
            if "VẢ" in action:
                send_tele(f"⚽ *TÀI XỈU - {home} vs {away}*\n🏆 Giải: {sport}\n🎯 Lệnh: *{action}*\n🚩 Bẫy: {trap}\n📊 Line: {line} | Odd: {over_price}\n⏰ {start_time.strftime('%H:%M')}")

def send_tele(msg):
    requests.post(f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage", 
                  json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    shark_scanner()
