import yfinance as yf
import requests
import pandas as pd
import os

# --- 設定區 ---

# Discord Webhook URL
DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK')

# 1. 金屬趨勢代理 (原 JJN 下市)
# 改用 DBB (Invesco DB Base Metals Fund)
# 它是工業基礎金屬(銅/鋅/鋁)的 ETF，與不銹鋼原物料行情高度正相關，且數據穩定。
METAL_ETF_TICKER = "DBB" 

# 2. 台股不銹鋼概念股
STAINLESS_STOCKS = ['2027.TW', '2034.TW', '2030.TW', '2015.TW', '2025.TW']

# --- 函數區 ---

def send_discord_message(content):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ 未設定 Discord Webhook URL，跳過發送。")
        print(content)
        return
    
    data = {
        "content": content,
        "username": "不銹鋼策略機器人"
    }
    try:
        result = requests.post(DISCORD_WEBHOOK_URL, json=data)
        result.raise_for_status()
    except Exception as err:
        print(f"Discord 發送失敗: {err}")
    else:
        print("Discord 發送成功")

def get_metal_trend():
    """
    分析金屬 ETF (DBB) 走勢
    """
    try:
        etf = yf.Ticker(METAL_ETF_TICKER)
        # 抓取 30 天資料
        hist = etf.history(period="1mo")
        
        if hist.empty or len(hist) < 20:
            print(f"錯誤: {METAL_ETF_TICKER} 資料不足或無法讀取")
            return None # 明確回傳 None

        current_price = hist['Close'].iloc[-1]
        prev_price = hist['Close'].iloc[-2]
        
        # 計算 20日均線 (月線)
        ma20 = hist['Close'].tail(20).mean()
        
        change_pct = ((current_price - prev_price) / prev_price) * 100
        
        trend_icon = "➖"
        trend_text = "盤整"
        
        if current_price > ma20:
            trend_icon = "📈"
            trend_text = "多頭 (價 > MA20)"
        else:
            trend_icon = "📉"
            trend_text = "空頭 (價 < MA20)"
            
        return {
            "symbol": METAL_ETF_TICKER,
            "price": current_price,
            "change_pct": change_pct,
            "ma20": ma20,
            "trend": f"{trend_icon} {trend_text}",
            "date": hist.index[-1].strftime('%Y-%m-%d')
        }
    except Exception as e:
        print(f"獲取金屬資料時發生例外錯誤: {e}")
        return None

def get_tw_stocks_status():
    """
    獲取不銹鋼股今日表現
    """
    msg = ""
    for symbol in STAINLESS_STOCKS:
        try:
            stock = yf.Ticker(symbol)
            # 抓取 5 天資料以防假日
            data = stock.history(period="5d")
            
            if len(data) >= 1:
                price = data['Close'].iloc[-1]
                stock_name = symbol.replace('.TW', '')
                
                change_str = "0.00%"
                icon = "➖"
                
                if len(data) >= 2:
                    prev_close = data['Close'].iloc[-2]
                    change = ((price - prev_close) / prev_close) * 100
                    if change > 0:
                        icon = "🔺"
                    elif change < 0:
                        icon = "🔻"
                    change_str = f"{change:.2f}%"
                
                msg += f"• **{stock_name}**: {price} ({icon} {change_str})\n"
            else:
                msg += f"• {symbol}: 無近期資料\n"
        except Exception as e:
            msg += f"• {symbol}: 讀取錯誤\n"
    return msg

# --- 主程式 ---

def main():
    print("開始執行策略分析...")
    metal_data = get_metal_trend()
    
    # 這裡的判斷式修正了：如果 metal_data 是 None，就不會執行下面的程式
    if not metal_data:
        print("❌ 無法獲取金屬趨勢資料，程式終止。")
        # 即使失敗也可以發個通知給自己 debug (選用)
        # send_discord_message("⚠️ GitHub Action 執行警告: 無法獲取金屬報價資料")
        return

    # 組合訊息
    message = f"**📊 金屬原物料 & 不銹鋼日報** ({metal_data['date']})\n"
    message += "----------------------------------\n"
    message += f"**🔩 工業金屬趨勢 ({metal_data['symbol']} ETF)**\n"
    message += f"現價: {metal_data['price']:.2f} USD\n"
    message += f"漲跌: {metal_data['change_pct']:.2f}%\n"
    message += f"趨勢: {metal_data['trend']}\n"
    message += "----------------------------------\n"
    message += f"**🏭 台灣不銹鋼概念股**\n"
    message += get_tw_stocks_status()
    message += "\n*策略邏輯: 追蹤 DBB (基本金屬) 判斷原物料多空*"

    # 簡單策略觸發：大漲 > 1.5% 或 站上月線
    is_bullish = metal_data['change_pct'] > 1.5 or "多頭" in metal_data['trend']
    
    if is_bullish:
        # 特別標註
        header = "@here **🔔 原物料轉強訊號！不銹鋼留意！**\n\n"
        message = header + message

    send_discord_message(message)

if __name__ == "__main__":
    main()
