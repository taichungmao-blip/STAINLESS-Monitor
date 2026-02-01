import yfinance as yf
import requests
import os
import io
import json
import pandas as pd
from bs4 import BeautifulSoup
from datetime import datetime

# 強制使用無介面繪圖後端
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# --- 設定區 ---
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK')
NICKEL_URL = "https://markets.businessinsider.com/commodities/nickel-price"
TREND_PROXY_TICKER = "DBB"  

# 備用代號清單
NICKEL_TICKERS = ["NI=F", "NICKEL=F", "DBB"] 

STOCK_LIST = [
    {"id": "2025.TW", "name": "千興", "tag": "小型飆股"},
    {"id": "2030.TW", "name": "彰源", "tag": "庫存利得"},
    {"id": "1605.TW", "name": "華新", "tag": "鎳礦資源"},
    {"id": "2034.TW", "name": "允強", "tag": "製造龍頭"},
    {"id": "2027.TW", "name": "大成鋼", "tag": "美鋁通路"},
    {"id": "2035.TWO", "name": "唐榮", "tag": "官股代表"},
    {"id": "9957.TWO", "name": "燁聯", "tag": "不銹鋼龍頭"}
]

def generate_nickel_chart():
    """ 抓取數據並生成走勢圖 (優化 y 軸縮放) """
    data = None
    target_ticker = ""
    
    for ticker in NICKEL_TICKERS:
        try:
            data = yf.download(ticker, period="1y", interval="1d", progress=False)
            if not data.empty and 'Close' in data:
                target_ticker = ticker
                break
        except:
            continue

    if data is None or data.empty:
        return None

    try:
        # 確保資料維度正確
        prices = data['Close']
        if isinstance(prices, pd.DataFrame):
            prices = prices.iloc[:, 0]
        
        y_values = prices.values.flatten()
        dates = data.index

        # --- 優化重點：計算 y 軸顯示範圍 ---
        y_min = y_values.min()
        y_max = y_values.max()
        padding = (y_max - y_min) * 0.1  # 給予上下 10% 的緩衝空間，不從 0 開始

        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 5))
        
        # 繪製線條
        ax.plot(dates, y_values, color='#00d2ff', linewidth=2)
        
        # 修正：填滿底色從 y_min - padding 開始，而非從 0 開始
        ax.fill_between(dates, y_min - padding, y_values, color='#00d2ff', alpha=0.1)
        
        # 強制設定 y 軸範圍，讓波動變明顯
        ax.set_ylim(y_min - padding, y_max + padding)
        
        last_val = float(prices.iloc[-1])
        ax.axhline(last_val, color='red', linestyle='--', alpha=0.5)
        ax.set_title(f"{target_ticker} 1-Year Trend (Latest: {last_val:.0f})", fontsize=12, pad=15)
        ax.grid(True, linestyle=':', alpha=0.3)
        
        for s in ax.spines.values(): s.set_visible(False)

        img_objs = io.BytesIO()
        plt.savefig(img_objs, format='png', facecolor='#2c2f33', bbox_inches='tight')
        img_objs.seek(0)
        plt.close()
        return img_objs
    except Exception as e:
        print(f"繪圖發生錯誤: {e}")
        return None

def get_nickel_price():
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(NICKEL_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        price_div = soup.find('span', class_='price-section__current-value') or soup.find('span', class_='push-data')
        if not price_div: return None
        price = float(price_div.text.replace(',', ''))
        change = 0.0
        try:
            pct_div = soup.find('span', class_='price-section__relative-value')
            if pct_div: change = float(pct_div.text.replace('%', '').strip())
        except: pass 
        return {"price": price, "change_pct": change}
    except: return None

def get_tw_stocks_status():
    lines = [f"{'代號':<5} {'名稱':<4} {'現價':>6} {'漲跌%':>7} {'特性'}", "-" * 42]
    for info in STOCK_LIST:
        try:
            stock = yf.Ticker(info['id'])
            data = stock.history(period="3d")
            if data.empty:
                alt_id = info['id'].replace(".TW", ".TWO") if ".TW" in info['id'] else info['id'].replace(".TWO", ".TW")
                data = yf.Ticker(alt_id).history(period="3d")
            
            if not data.empty:
                price = data['Close'].iloc[-1]
                prev = data['Close'].iloc[-2]
                change = ((price - prev) / prev) * 100
                lines.append(f"{info['id'].split('.')[0]:<5} {info['name']:<4} {price:>6.2f} {change:+.2f}%  {info['tag']}")
        except: continue
    return "\n".join(lines)

def send_discord_message(content, img=None):
    if not DISCORD_WEBHOOK_URL: return
    try:
        payload = {"content": content, "username": "不銹鋼戰情室"}
        if img:
            img.seek(0)
            files = {'file': ('chart.png', img, 'image/png')}
            requests.post(DISCORD_WEBHOOK_URL, data={'payload_json': json.dumps(payload)}, files=files)
        else:
            requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except: pass

def main():
    print("戰情室啟動...")
    nickel = get_nickel_price()
    chart = generate_nickel_chart()
    stocks = get_tw_stocks_status()
    
    msg = f"📊 **不銹鋼產業戰情室** ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"
    if nickel:
        msg += f"**🔩 LME 鎳價 (Spot)**\n> 現價: `{nickel['price']:,.0f}` USD\n> 漲跌: `{nickel['change_pct']}%`\n"
    msg += f"\n**🏭 個股表現**\n```yaml\n{stocks}\n```"
    
    send_discord_message(msg, img=chart)

if __name__ == "__main__":
    main()
