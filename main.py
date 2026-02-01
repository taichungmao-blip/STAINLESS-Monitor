import yfinance as yf
import requests
import os
import io
import matplotlib
matplotlib.use('Agg') # 強制非交互模式
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
from datetime import datetime
import json

# --- 設定區 ---
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK')
NICKEL_URL = "https://markets.businessinsider.com/commodities/nickel-price"
TREND_PROXY_TICKER = "DBB"  
NICKEL_TICKER = "NI=F"      

STOCK_LIST = [
    {"id": "2025.TW", "name": "千興", "tag": "小型飆股"},
    {"id": "2030.TW", "name": "彰源", "tag": "庫存利得"},
    {"id": "1605.TW", "name": "華新", "tag": "鎳礦資源"},
    {"id": "2034.TW", "name": "允強", "tag": "製造龍頭"},
    {"id": "2027.TW", "name": "大成鋼", "tag": "美鋁通路"},
    {"id": "2035.TW", "name": "唐榮", "tag": "官股代表"},
    {"id": "9957.TW", "name": "燁聯", "tag": "不銹鋼龍頭"}
]

def generate_nickel_chart():
    """ 生成深色專業風格走勢圖 """
    try:
        data = yf.download(NICKEL_TICKER, period="1y", interval="1d", progress=False)
        if data.empty:
            print("無法抓取歷史數據")
            return None

        plt.style.use('dark_background')
        fig, ax = plt.subplots(figsize=(10, 5))
        
        ax.plot(data.index, data['Close'], color='#00d2ff', linewidth=2)
        ax.fill_between(data.index, data['Close'], color='#00d2ff', alpha=0.1)
        
        last_price = data['Close'].iloc[-1]
        ax.axhline(last_price, color='red', linestyle='--', alpha=0.5)
        
        ax.set_title(f"Nickel Price (LME) 1-Year Trend", fontsize=14, pad=20)
        ax.grid(True, linestyle=':', alpha=0.3)
        
        for spine in ax.spines.values():
            spine.set_visible(False)

        img_objs = io.BytesIO()
        # 設定背景色與 Discord 深色模式一致
        plt.savefig(img_objs, format='png', facecolor='#2c2f33', bbox_inches='tight')
        img_objs.seek(0)
        plt.close()
        return img_objs
    except Exception as e:
        print(f"圖表生成失敗: {e}")
        return None

def send_discord_message(content, image_file=None):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ 未設定 Discord Webhook URL")
        return
    
    # 同時傳送文字與圖片的標準格式
    payload = {"content": content, "username": "不銹鋼戰情室"}
    
    try:
        if image_file:
            # 檔案參數名稱設為 'file'，文字包在 payload_json
            files = {'file': ('nickel_chart.png', image_file, 'image/png')}
            res = requests.post(
                DISCORD_WEBHOOK_URL, 
                data={'payload_json': json.dumps(payload)}, 
                files=files
            )
        else:
            res = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        res.raise_for_status()
        print("Discord 訊息與圖表發送成功")
    except Exception as err:
        print(f"Discord 發送失敗: {err}")

# (其餘 get_nickel_price, get_market_trend, get_tw_stocks_status 函數保持不變)
# ... [省略中間函數以節省空間，請沿用上一版本] ...

def main():
    print("開始執行策略分析...")
    nickel_data = get_nickel_price()
    market_trend = get_market_trend()
    chart_img = generate_nickel_chart() # 嘗試生成圖片
    
    message = f"📊 **不銹鋼產業戰情室** ({datetime.now().strftime('%Y-%m-%d %H:%M')})\n\n"
    if nickel_data:
        pct_sign = "🔺" if nickel_data['change_pct'] > 0 else "🔻"
        message += f"**🔩 LME 鎳價 (Spot)**\n> 現價: `{nickel_data['price']:,.0f}` USD\n> 漲跌: `{pct_sign} {nickel_data['change_pct']}%`\n"
    if market_trend:
        message += f"**🌊 趨勢判斷**: **{market_trend['status']}**\n"
    
    message += f"\n**🏭 不銹鋼個股表現**\n```yaml\n{get_tw_stocks_status()}\n```"
    
    # 執行發送
    send_discord_message(message, image_file=chart_img)

if __name__ == "__main__":
    main()
