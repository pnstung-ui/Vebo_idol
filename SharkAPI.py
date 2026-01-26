import requests
from datetime import datetime, timedelta

# --- CẤU HÌNH ---
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"

# Danh sách giải đấu vét cạn
REGIONS = [
    'soccer_epl', 'soccer_germany_bundesliga', 'soccer_italy_serie_a', 
    'soccer_spain_la_liga', 'soccer_france_ligue_1', 'soccer_uefa_champs_league',
    'soccer_usa_mls', 'soccer_brazil_campeonato', 'soccer_netherlands_ere_divisie',
    'soccer_norway_eliteserien', 'soccer_japan_j_league', 'soccer_korea_kleague_1'
]

def shark_scanner():
    now_gmt7 = datetime.now() + timedelta(hours=7)
    print(f"--- Radar khởi động: {now_gmt7.strftime('%d/%m %H:%M')} ---")

    for sport in REGIONS:
        url = f"https://api.the-odds-api.com/v4/sports/{sport}/odds/"
        params = {
            'apiKey': API_KEY,
            'regions': 'eu', # Lấy dữ liệu sàn uy tín
            'markets': 'totals,spreads', # totals = Tài Xỉu, spreads = Kèo Chấp
            'oddsFormat': 'decimal'
        }
        
        try:
            r = requests.get(url, params=params)
            if r.status_code != 200: continue
            data = r.json()
            
            for match in data:
                home, away = match['home_team'], match['away_team']
                start_time = datetime.strptime(match['commence_time'], "%Y-%m-%dT%H:%M:%SZ") + timedelta(hours=7)
                
                # Chỉ quét trận trong 12h tới để đảm bảo Odd đang "nhảy"
                if now_gmt7 < start_time < now_gmt7 + timedelta(hours=12):
                    analyze_match_full(match, home, away, start_time, sport)
        except Exception as e:
            print(f"Lỗi giải {sport}: {e}")

def analyze_match_full(match, home, away, start_time, sport):
    bookmakers = match['bookmakers']
    if not bookmakers: return
    
    # Lấy sàn đầu tiên làm mốc soi
    bm = bookmakers[0]
    for market in bm['markets']:
        
        # 1. LOGIC TÀI XỈU BIẾN THIÊN
        if market['key'] == 'totals':
            line = market['outcomes'][0]['point']
            over_p = market['outcomes'][0]['price']
            under_p = market['outcomes'][1]['price']
            
            action, trap = "---", "---"
            
            # Nhận diện bẫy theo Line & Giải đấu
            if line < 2.5 and any(x in sport for x in ['netherlands', 'norway', 'germany']):
                trap = f"⚠️ DỤ TÀI (Line {line} quá thấp)"
            elif line > 2.75 and any(x in sport for x in ['italy', 'spain']):
                trap = f"❄️ DỤ XỈU (Line {line} quá cao)"
            
            # Logic Tiền ép (Vả theo Odd giảm sâu)
            if over_p < 1.80:
                action = f"VẢ TÀI {line} 🔥"
                if "DỤ XỈU" in trap: action = f"💣 VẢ TÀI {line} MẠNH (Bẻ bẫy)"
            elif under_p < 1.80:
                action = f"VẢ XỈU {line} ❄️"
                if "DỤ TÀI" in trap: action = f"💣 VẢ XỈU {line} MẠNH (Bẻ bẫy)"
            
            if "VẢ" in action:
                send_tele(f"📊 *TÀI XỈU BIẾN THIÊN*\n🏟️ {home} vs {away}\n🏆 Giải: {sport}\n🎯 Lệnh: *{action}*\n🚩 Bẫy: {trap}\n💰 Odd: {over_p if 'TÀI' in action else under_p}\n⏰ {start_time.strftime('%H:%M')}")

        # 2. LOGIC KÈO CHẤP BIẾN THIÊN (Spreads)
        elif market['key'] == 'spreads':
            h_line = market['outcomes'][0]['point'] # Ví dụ -0.75
            h_price = market['outcomes'][0]['price']
            a_price = market['outcomes'][1]['price']
            
            # Nếu giá cửa nào giảm xuống dưới 1.82 -> Tiền ép cửa đó
            if h_price < 1.82:
                send_tele(f"🛡️ *KÈO CHẤP BIẾN THIÊN*\n🏟️ {home} vs {away}\n🎯 Lệnh: *✅ THEO {home} ({h_line})*\n📊 Odd: {h_price}\n⏰ {start_time.strftime('%H:%M')}")
            elif a_price < 1.82:
                a_line = market['outcomes'][1]['point']
                send_tele(f"🛡️ *KÈO CHẤP BIẾN THIÊN*\n🏟️ {home} vs {away}\n🎯 Lệnh: *✅ THEO {away} ({a_line})*\n📊 Odd: {a_price}\n⏰ {start_time.strftime('%H:%M')}")

def send_tele(msg):
    requests.post(f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage", 
                  json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"})

if __name__ == "__main__":
    shark_scanner()
