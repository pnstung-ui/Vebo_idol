import requests
import pandas as pd
import os

TELE_TOKEN = "8477918500:AAFCazBYVwDq6iJGlLfVZ-UTCK3B5OFO7XW"
TELE_CHAT_ID = "957306386"
API_KEY = "f45bf78df6e60adb0d2d6d1d9e0f7c1c"
MEMORY_FILE = "shark_memory.csv"

def check_results():
    if not os.path.exists(MEMORY_FILE): return
    df = pd.read_csv(MEMORY_FILE)
    waiting = df[df['status'] == 'WAITING']
    if waiting.empty: return

    url = f"https://api.the-odds-api.com/v4/sports/soccer/scores/?apiKey={API_KEY}&daysFrom=1"
    try:
        res = requests.get(url).json()
        for idx, row in waiting.iterrows():
            for match in res:
                if f"{match['home_team']}-{match['away_team']}" == row['match'] and match['completed']:
                    s1, s2 = int(match['scores'][0]['score']), int(match['scores'][1]['score'])
                    total = s1 + s2
                    result = "GÃY ❌"
                    # Kiểm tra HÚP/GÃY cho Tài Xỉu
                    if "TÀI" in row['side'] and total > float(row['line']): result = "HÚP ✅"
                    elif "XỈU" in row['side'] and total < float(row['line']): result = "HÚP ✅"
                    
                    df.at[idx, 'status'] = result
                    msg = f"📊 *TỔNG KẾT: {row['match']}*\n🎯 Lệnh: {row['side']} {row['line']}\n⚽ Tỉ số: {s1}-{s2}\n💰 Kết quả: *{result}*"
                    requests.post(f"https://api.telegram.org/bot{TELE_TOKEN}/sendMessage", json={"chat_id": TELE_CHAT_ID, "text": msg, "parse_mode": "Markdown"})
        df.to_csv(MEMORY_FILE, index=False)
    except: pass

if __name__ == "__main__": check_results()
