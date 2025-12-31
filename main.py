import yfinance as yf
import requests
import pandas as pd
from datetime import datetime
import os

# --- 設定區 ---

# Discord Webhook URL (請從環境變數讀取，以保安全)
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK')

# 追蹤標的
# 1. 鎳價代理：因為 LME 即時數據通常要付費，我們使用 JJN (iPath Series B Bloomberg Nickel Subindex Total Return ETN) 
# 或者倫敦鎳期貨的相關數據。JJN 與鎳價連動性極高。
NICKEL_TICKER = "JJN" 

# 2. 台股不銹鋼概念股 (可自行增減)
# 2027: 大成鋼, 2034: 允強, 9957: 燁聯(興櫃較難抓，先略過), 2030: 彰源, 2015: 豐興, 2025: 千興
STAINLESS_STOCKS = ['2027.TW', '2034.TW', '2030.TW', '2015.TW', '2025.TW']

# --- 函數區 ---

def send_discord_message(content):
    if not DISCORD_WEBHOOK_URL:
        print("未設定 Discord Webhook URL，跳過發送。")
        print(content)
        return
    
    data = {
        "content": content,
        "username": "鎳價 & 不銹鋼策略機器人"
    }
    result = requests.post(DISCORD_WEBHOOK_URL, json=data)
    try:
        result.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print(f"Discord 發送失敗: {err}")
    else:
        print("Discord 發送成功")

def get_nickel_trend():
    """
    分析鎳價走勢
    策略：比較當前價格與 20日均線 (月線)，判斷多空
    """
    nickel = yf.Ticker(NICKEL_TICKER)
    # 抓取過去 30 天資料以計算 MA20
    hist = nickel.history(period="1mo")
    
    if len(hist) < 20:
        return None, "資料不足"

    current_price = hist['Close'].iloc[-1]
    prev_price = hist['Close'].iloc[-2]
    ma20 = hist['Close'].tail(20).mean()
    
    change_pct = ((current_price - prev_price) / prev_price) * 100
    
    trend = "---"
    if current_price > ma20:
        trend = "📈 多頭排列 (價 > MA20)"
    else:
        trend = "📉 空頭排列 (價 < MA20)"
        
    return {
        "price": current_price,
        "change_pct": change_pct,
        "ma20": ma20,
        "trend": trend,
        "date": hist.index[-1].strftime('%Y-%m-%d')
    }

def get_tw_stocks_status():
    """
    獲取不銹鋼股今日表現
    """
    msg = ""
    for symbol in STAINLESS_STOCKS:
        try:
            stock = yf.Ticker(symbol)
            # 抓取 2 天資料來算漲跌
            data = stock.history(period="2d")
            if len(data) >= 1:
                price = data['Close'].iloc[-1]
                stock_name = symbol.replace('.TW', '') # 簡化代號
                
                change_str = ""
                if len(data) >= 2:
                    prev_close = data['Close'].iloc[-2]
                    change = ((price - prev_close) / prev_close) * 100
                    icon = "🔺" if change > 0 else "🔻" if change < 0 else "➖"
                    change_str = f"{icon} {change:.2f}%"
                
                msg += f"• **{stock_name}**: {price} ({change_str})\n"
        except Exception as e:
            msg += f"• {symbol}: 讀取失敗\n"
    return msg

# --- 主程式 ---

def main():
    nickel_data = get_nickel_trend()
    
    if not nickel_data:
        print("無法獲取鎳價資料")
        return

    # 組合訊息
    message = f"**📊 鎳價 & 不銹鋼追蹤日報** ({nickel_data['date']})\n"
    message += "----------------------------------\n"
    message += f"**🔩 國際鎳價 (JJN ETF 代理)**\n"
    message += f"現價: {nickel_data['price']:.2f} USD\n"
    message += f"漲跌: {nickel_data['change_pct']:.2f}%\n"
    message += f"趨勢: {nickel_data['trend']}\n"
    message += "----------------------------------\n"
    message += f"**🏭 台灣不銹鋼概念股**\n"
    message += get_tw_stocks_status()
    message += "\n*資料來源: Yahoo Finance, 僅供程式交易練習參考*"

    # 簡單策略觸發邏輯：如果鎳價大漲 > 1% 或 站上均線，特別標註
    if nickel_data['change_pct'] > 1 or "多頭" in nickel_data['trend']:
        message = "@here **🔔 注意！鎳價轉強，留意不銹鋼族群！**\n\n" + message

    send_discord_message(message)

if __name__ == "__main__":
    main()
