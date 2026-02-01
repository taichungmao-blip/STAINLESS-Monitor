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

# 擴充鎳價備用代號，增加穩定性
NICKEL_TICKERS = ["NI=F", "NICKEL=F", "DBB"] 

# 修正：唐榮與燁聯在 Yahoo Finance 主要是 .TWO 後綴
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
    """ 抓取數據並生成走勢圖，包含維度修正 """
    data = None
    target_ticker = ""
    
    for ticker in NICKEL_TICKERS:
        try:
            print(f"嘗試抓取 {ticker} 數據...")
            data = yf.download(ticker, period="1y", interval="1d", progress=False)
            if not data.empty and 'Close' in data:
                target_ticker = ticker
                break
        except Exception as e:
            print(f"{ticker} 抓取失敗: {e}")
            continue

    if data is None or data.empty:
        print("所有鎳價相關代號皆無法抓取數據")
        return None

    try:
        # --- 維度修正重點：確保資料是 1D Series ---
        # yfinance 0.2.x 有時會返回 MultiIndex DataFrame
        prices = data['Close']
        if isinstance(prices, pd.DataFrame):
            prices = prices.iloc[:, 0] # 取第一欄確保為 1D
        
        # 確保 index 也是平坦的
        dates = data.index

        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 5))
        
        # 繪製線條
        ax.plot(dates, prices.values, color='#00d2ff', linewidth=2)
        ax.fill_between(dates, 0, prices.values.flatten(), color='#00d2ff', alpha=0.1) # 修正 y1
        
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
        print(f"繪圖發生錯誤: {e}") # 捕捉 'y1' is not 1-dimensional 等錯誤
        return None

def get_nickel_price():
    """ 抓取 Business Insider 即時報價 """
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
    """ 個股表現追蹤，含自動後綴切換 """
    lines = [f"{'代號':<5} {'名稱':<4} {'現價':>6} {'漲跌%':>7} {'特性'}", "-" * 42]
    for info in STOCK_LIST:
        try:
            stock = yf.Ticker(info['id'])
            data = stock.history(period="3d")
            # 如果 .TW 失敗，嘗試 .TWO，反之亦然
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
    except Exception as e: print(f"發送失敗: {e}")

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
