import yfinance as yf
import requests
import os
import io  # 用於在記憶體中處理圖片，不需產生實體檔案
import matplotlib.pyplot as plt
from bs4 import BeautifulSoup
from datetime import datetime

# --- 設定區 ---
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK')
NICKEL_URL = "https://markets.businessinsider.com/commodities/nickel-price"
TREND_PROXY_TICKER = "DBB"
# 鎳價期貨代號，Yahoo Finance 通常使用 'NI=F' (LME Nickel)
NICKEL_TICKER = "NI=F" 

STOCK_LIST = [
    {"id": "2025.TW", "name": "千興", "tag": "小型飆股"},
    {"id": "2030.TW", "name": "彰源", "tag": "庫存利得"},
    {"id": "1605.TW", "name": "華新", "tag": "鎳礦資源"},
    {"id": "2034.TW", "name": "允強", "tag": "製造龍頭"},
    {"id": "2027.TW", "name": "大成鋼", "tag": "美鋁通路"},
]

# --- 函數區 ---

def generate_nickel_chart():
    """ 抓取一年鎳價並生成走勢圖 (回傳 BytesIO 物件) """
    try:
        # 下載一年資料
        data = yf.download(NICKEL_TICKER, period="1y", interval="1d", progress=False)
        if data.empty:
            return None

        plt.figure(figsize=(10, 5))
        plt.plot(data.index, data['Close'], color='#2ecc71', linewidth=2)
        plt.title(f"Nickel Price (LME) - Last 12 Months", fontsize=14)
        plt.xlabel("Date")
        plt.ylabel("USD / Ton")
        plt.grid(True, linestyle='--', alpha=0.7)
        plt.tight_layout()

        # 將圖片儲存在記憶體中，避免產生臨時檔案
        img_objs = io.BytesIO()
        plt.savefig(img_objs, format='png')
        img_objs.seek(0)
        plt.close()
        return img_objs
    except Exception as e:
        print(f"圖表生成失敗: {e}")
        return None

def send_discord_message(content, image_file=None):
    """ 修改後的發送函數：支援同時發送文字與圖片 """
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ 未設定 Discord Webhook URL")
        return
    
    payload = {"content": content, "username": "不銹鋼戰情室"}
    
    try:
        if image_file:
            # 如果有圖片，使用 multipart/form-data 格式
            files = {
                'file': ('nickel_chart.png', image_file, 'image/png')
            }
            # 注意：發送檔案時 payload 需放入 'payload_json'
            import json
            res = requests.post(DISCORD_WEBHOOK_URL, data={'payload_json': json.dumps(payload)}, files=files)
        else:
            res = requests.post(DISCORD_WEBHOOK_URL, json=payload)
            
        res.raise_for_status()
        print("Discord 發送成功")
    except Exception as err:
        print(f"Discord 發送失敗: {err}")

# (其餘 get_nickel_price, get_market_trend, get_tw_stocks_status 保持不變)
# ... [保留你原本的 get_nickel_price, get_market_trend, get_tw_stocks_status] ...

def main():
    print("開始執行策略分析...")
    
    nickel_data = get_nickel_price()
    market_trend = get_market_trend()
    chart_img = generate_nickel_chart() # 生成圖表
    
    message = ""
    # 判斷整體氣氛
    is_bullish_price = nickel_data and nickel_data['change_pct'] > 1.0
    is_bullish_trend = market_trend and "多頭" in market_trend['status']
    
    title_emoji = "🔥" if (is_bullish_price and is_bullish_trend) else "📊"
    message += f"{title_emoji} **鎳價策略戰情室** ({datetime.now().strftime('%Y-%m-%d')})\n\n"

    # --- 1. 即時報價區 ---
    if nickel_data:
        pct_sign = "🔺" if nickel_data['change_pct'] > 0 else "🔻"
        message += f"**🔩 LME 鎳價 (Spot)**\n"
        message += f"> 現價: `{nickel_data['price']:,.0f}` USD\n"
        message += f"> 漲跌: `{pct_sign} {nickel_data['change_pct']}%`\n"
    else:
        message += f"**🔩 LME 鎳價**: `讀取失敗`\n"

    # --- 2. 技術趨勢區 ---
    if market_trend:
        message += f"**🌊 原物料趨勢 (DBB ETF)**\n"
        message += f"> 狀態: **{market_trend['status']}**\n"
        message += f"> 策略: "
        if "多頭" in market_trend['status']: message += "`順勢做多` ✅\n"
        elif "站上月線" in market_trend['status']: message += "`反彈行情` ⚠️\n"
        elif "空頭" in market_trend['status']: message += "`保守觀望` ⛔\n"
        else: message += "`區間震盪` 🔄\n"
    message += "\n"

    # --- 3. 台股區 ---
    message += f"**🏭 不銹鋼個股表現**\n"
    message += "```yaml\n"
    message += get_tw_stocks_status()
    message += "\n```"
    
    # --- 4. 訊號總結 ---
    if is_bullish_price and is_bullish_trend:
        message = "@here **🚀 強力訊號：鎳價大漲 + 趨勢多頭！**\n" + message
    elif is_bullish_price and not is_bullish_trend:
        message = "@here **⚠️ 注意：鎳價反彈，但大趨勢仍偏空**\n" + message

    # 發送訊息與圖表
    send_discord_message(message, image_file=chart_img)

if __name__ == "__main__":
    main()
