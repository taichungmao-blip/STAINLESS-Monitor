import yfinance as yf
import requests
import os
import io
import json
from bs4 import BeautifulSoup
from datetime import datetime

# --- 關鍵修正：解決 GitHub Actions 無顯示器環境下的繪圖問題 ---
import matplotlib
matplotlib.use('Agg')  # 必須在 import pyplot 之前執行
import matplotlib.pyplot as plt

# --- 設定區 ---
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK')
NICKEL_URL = "https://markets.businessinsider.com/commodities/nickel-price"
TREND_PROXY_TICKER = "DBB"  # 原物料趨勢指標 ETF
NICKEL_TICKER = "NI=F"      # Yahoo Finance 鎳期貨代號

# 個股清單：已加入唐榮與燁聯
STOCK_LIST = [
    {"id": "2025.TW", "name": "千興", "tag": "小型飆股"},
    {"id": "2030.TW", "name": "彰源", "tag": "庫存利得"},
    {"id": "1605.TW", "name": "華新", "tag": "鎳礦資源"},
    {"id": "2034.TW", "name": "允強", "tag": "製造龍頭"},
    {"id": "2027.TW", "name": "大成鋼", "tag": "美鋁通路"},
    {"id": "2035.TW", "name": "唐榮", "tag": "官股代表"},
    {"id": "9957.TW", "name": "燁聯", "tag": "不銹鋼龍頭"}
]

# --- 函數區 ---

def generate_nickel_chart():
    """ 抓取一年鎳價並生成深色專業風格走勢圖 """
    try:
        data = yf.download(NICKEL_TICKER, period="1y", interval="1d", progress=False)
        if data.empty:
            print("無法抓取歷史數據")
            return None

        # 設定適合 Discord 深色模式的風格
        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 5))
        
        # 繪製線條與漸層
        ax.plot(data.index, data['Close'], color='#00d2ff', linewidth=2)
        ax.fill_between(data.index, data['Close'], color='#00d2ff', alpha=0.1)
        
        # 標註最新價格
        last_price = data['Close'].iloc[-1]
        ax.axhline(last_price, color='red', linestyle='--', alpha=0.5)
        ax.text(data.index[0], last_price, f' Latest: {last_price:.0f}', color='red', fontweight='bold')

        ax.set_title(f"Nickel Price (LME) 1-Year Trend", fontsize=14, pad=20)
        ax.set_ylabel("USD / Ton")
        ax.grid(True, linestyle=':', alpha=0.3)
        
        # 移除多餘邊框
        for spine in ax.spines.values():
            spine.set_visible(False)

        # 存入記憶體
        img_objs = io.BytesIO()
        plt.savefig(img_objs, format='png', facecolor='#2c2f33', bbox_inches='tight')
        img_objs.seek(0)
        plt.close()
        return img_objs
    except Exception as e:
        print(f"圖表生成失敗: {e}")
        return None

def send_discord_message(content, image_file=None):
    """ 支援文字與圖片同時發送的 Discord Webhook """
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ 未設定 Discord Webhook URL")
        return
    
    payload = {"content": content, "username": "不銹鋼戰情室"}
    
    try:
        if image_file:
            # 同時傳送檔案時，文字內容需包在 payload_json 中
            files = {'file': ('nickel_chart.png', image_file, 'image/png')}
            res = requests.post(
                DISCORD_WEBHOOK_URL, 
                data={'payload_json': json.dumps(payload)}, 
                files=files
            )
        else:
            res = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        res.raise_for_status()
        print("Discord 發送成功")
    except Exception as err:
        print(f"Discord 發送失敗: {err}")

def get_nickel_price():
    """ 抓取即時鎳價 (Business Insider) """
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
    except Exception as e:
        print(f"爬取鎳價失敗: {e}")
        return None

def get_market_trend():
    """ 計算 DBB ETF 趨勢指標 """
    try:
        etf = yf.Ticker(TREND_PROXY_TICKER)
        hist = etf.history(period="4mo")
        if len(hist) < 60: return None
        price = hist['Close'].iloc[-1]
        ma20 = hist['Close'].tail(20).mean()
        ma60 = hist['Close'].tail(60).mean()
        
        status = "盤整中 ⚖️"
        if price > ma20 and ma20 > ma60: status = "多頭排列 (強勢) 🚀"
        elif price > ma20 and ma20 < ma60: status = "站上月線 (反彈) 📈"
        elif price < ma20 and ma20 < ma60: status = "空頭排列 (弱勢) 🐻"
        elif price < ma20 and ma20 > ma60: status = "跌破月線 (整理) 📉"
        return {"status": status}
    except: return None

def get_tw_stocks_status():
    """ 獲取台股個股表現表格 """
    table_lines = []
    header = f"{'代號':<5} {'名稱':<4} {'現價':>6} {'漲跌%':>7} {'特性'}"
    table_lines.append(header)
    table_lines.append("-" * 42)
    for stock_info in STOCK_LIST:
        try:
            stock = yf.Ticker(stock_info['id'])
            data = stock.history(period="2d")
            if not data.empty:
                price = data['Close'].iloc[-1]
                change_str = "0.00%"
                if len(data) >= 2:
                    prev = data['Close'].iloc[-2]
                    change = ((price - prev) / prev) * 100
                    change_str = f"{'+' if change > 0 else ''}{change:.2f}%"
                table_lines.append(f"{stock_info['id'].split('.')[0]:<5} {stock_info['name']:<4} {price:>6.2f} {change_str:>7}  {stock_info['tag']}")
        except: continue
    return "\n".join(table_lines)

# --- 主程式 ---

def main():
    print("開始執行策略分析...")
    nickel_data = get_nickel_price()
    market_trend = get_market_trend()
    chart_img = generate_nickel_chart()
    
    # 組合訊息內容
    message = f"📊 **不銹鋼產業戰情室** ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"
    if nickel_data:
        pct_sign = "🔺" if nickel_data['change_pct'] > 0 else "🔻"
        message += f"**🔩 LME 鎳價 (Spot)**\n> 現價: `{nickel_data['price']:,.0f}` USD\n> 漲跌: `{pct_sign} {nickel_data['change_pct']}%`\n"
    if market_trend:
        message += f"**🌊 趨勢判斷**: **{market_trend['status']}**\n"
    
    message += f"\n**🏭 不銹鋼個股表現**\n```yaml\n{get_tw_stocks_status()}\n```"
    
    # 執行發送 (包含圖片)
    send_discord_message(message, image_file=chart_img)

if __name__ == "__main__":
    main()
