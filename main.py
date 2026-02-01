import yfinance as yf
import requests
import os
import io
import json
from bs4 import BeautifulSoup
from datetime import datetime

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

# --- 設定區 ---
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK')
NICKEL_URL = "https://markets.businessinsider.com/commodities/nickel-price"
TREND_PROXY_TICKER = "DBB"  
# 嘗試多個可能代號: LME 鎳期貨或相關 ETF
NICKEL_TICKERS = ["NI=F", "NICK-USD", "DBB"] 

STOCK_LIST = [
    {"id": "2025.TW", "name": "千興", "tag": "小型飆股"},
    {"id": "2030.TW", "name": "彰源", "tag": "庫存利得"},
    {"id": "1605.TW", "name": "華新", "tag": "鎳礦資源"},
    {"id": "2034.TW", "name": "允強", "tag": "製造龍頭"},
    {"id": "2027.TW", "name": "大成鋼", "tag": "美鋁通路"},
    {"id": "2035.TWO", "name": "唐榮", "tag": "官股代表"}, # 修正為 .TWO
    {"id": "9957.TWO", "name": "燁聯", "tag": "不銹鋼龍頭"} # 修正為 .TWO
]

def generate_nickel_chart():
    """ 嘗試抓取可用數據並生成走勢圖 """
    data = None
    target_ticker = ""
    
    # 輪詢代號直到抓到資料
    for ticker in NICKEL_TICKERS:
        try:
            print(f"嘗試抓取 {ticker} 數據...")
            data = yf.download(ticker, period="1y", interval="1d", progress=False)
            if not data.empty:
                target_ticker = ticker
                break
        except:
            continue

    if data is None or data.empty:
        print("所有鎳價相關代號皆無法抓取數據")
        return None

    try:
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(data.index, data['Close'], color='#00d2ff', linewidth=2)
        ax.fill_between(data.index, data['Close'], color='#00d2ff', alpha=0.1)
        
        last_price = data['Close'].iloc[-1]
        ax.set_title(f"{target_ticker} 1-Year Trend (Last: {last_price:.0f})", fontsize=14, pad=20)
        ax.grid(True, linestyle=':', alpha=0.3)
        
        img_objs = io.BytesIO()
        plt.savefig(img_objs, format='png', facecolor='#2c2f33', bbox_inches='tight')
        img_objs.seek(0)
        plt.close()
        return img_objs
    except Exception as e:
        print(f"繪圖發生錯誤: {e}")
        return None

def get_nickel_price():
    """ 爬蟲邏輯 (不受 Yahoo 代號影響) """
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(NICKEL_URL, headers=headers, timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        price_div = soup.find('span', class_='price-section__current-value') or soup.find('span', class_='push-data')
        if not price_div: return None
        current_price = float(price_div.text.replace(',', ''))
        change_pct = 0.0
        try:
            pct_div = soup.find('span', class_='price-section__relative-value')
            if pct_div: change_pct = float(pct_div.text.replace('%', '').strip())
        except: pass 
        return {"price": current_price, "change_pct": change_pct}
    except: return None

def get_tw_stocks_status():
    table_lines = []
    header = f"{'代號':<5} {'名稱':<4} {'現價':>6} {'漲跌%':>7} {'特性'}"
    table_lines.append(header)
    table_lines.append("-" * 42)
    for stock_info in STOCK_LIST:
        try:
            # 加入 retry 機制嘗試 .TW 或 .TWO
            stock = yf.Ticker(stock_info['id'])
            data = stock.history(period="3d")
            if data.empty:
                # 嘗試自動切換後綴
                alt_id = stock_info['id'].replace(".TW", ".TWO") if ".TW" in stock_info['id'] else stock_info['id'].replace(".TWO", ".TW")
                stock = yf.Ticker(alt_id)
                data = stock.history(period="3d")
            
            if not data.empty:
                price = data['Close'].iloc[-1]
                prev = data['Close'].iloc[-2]
                change = ((price - prev) / prev) * 100
                change_str = f"{'+' if change > 0 else ''}{change:.2f}%"
                table_lines.append(f"{stock_info['id'].split('.')[0]:<5} {stock_info['name']:<4} {price:>6.2f} {change_str:>7}  {stock_info['tag']}")
        except: continue
    return "\n".join(table_lines)

def send_discord_message(content, image_file=None):
    if not DISCORD_WEBHOOK_URL: return
    payload = {"content": content, "username": "不銹鋼戰情室"}
    try:
        if image_file:
            image_file.seek(0)
            files = {'file': ('nickel_chart.png', image_file, 'image/png')}
            requests.post(DISCORD_WEBHOOK_URL, data={'payload_json': json.dumps(payload)}, files=files)
        else:
            requests.post(DISCORD_WEBHOOK_URL, json=payload)
    except: pass

def main():
    print("開始執行策略分析...")
    nickel_data = get_nickel_price()
    chart_img = generate_nickel_chart()
    
    msg = f"📊 **不銹鋼產業戰情室** ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"
    if nickel_data:
        msg += f"**🔩 LME 鎳價 (Spot)**\n> 現價: `{nickel_data['price']:,.0f}` USD\n> 漲跌: `{nickel_data['change_pct']}%`\n"
    
    msg += f"\n**🏭 個股表現**\n```yaml\n{get_tw_stocks_status()}\n```"
    send_discord_message(msg, image_file=chart_img)

if __name__ == "__main__":
    main()
