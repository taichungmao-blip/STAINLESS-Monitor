import yfinance as yf
import requests
import os
from bs4 import BeautifulSoup
from datetime import datetime

# --- 設定區 ---

DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK')
NICKEL_URL = "https://markets.businessinsider.com/commodities/nickel-price"

# 趨勢判斷代理：DBB (Invesco DB Base Metals Fund)
# 用它來計算 MA20, MA60，判斷原物料大趨勢
TREND_PROXY_TICKER = "DBB"

STOCK_LIST = [
    {"id": "2025.TW", "name": "千興", "tag": "小型飆股"},
    {"id": "2030.TW", "name": "彰源", "tag": "庫存利得"},
    {"id": "1605.TW", "name": "華新", "tag": "鎳礦資源"},
    {"id": "2034.TW", "name": "允強", "tag": "製造龍頭"},
    {"id": "2027.TW", "name": "大成鋼", "tag": "美鋁通路"},
]

# --- 函數區 ---

def send_discord_message(content):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ 未設定 Discord Webhook URL")
        return
    data = {"content": content, "username": "不銹鋼戰情室"}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data).raise_for_status()
        print("Discord 發送成功")
    except Exception as err:
        print(f"Discord 發送失敗: {err}")

def get_nickel_price():
    """ 抓取即時鎳價 (Business Insider) """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        response = requests.get(NICKEL_URL, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        price_div = soup.find('span', class_='price-section__current-value')
        if not price_div: price_div = soup.find('span', class_='push-data')
        if not price_div: return None
            
        current_price = float(price_div.text.replace(',', ''))
        
        change_pct = 0.0
        try:
            pct_div = soup.find('span', class_='price-section__relative-value')
            if pct_div: change_pct = float(pct_div.text.replace('%', '').strip())
        except: pass 

        return {
            "price": current_price,
            "change_pct": change_pct,
            "date": datetime.now().strftime('%Y-%m-%d')
        }
    except Exception as e:
        print(f"爬取鎳價失敗: {e}")
        return None

def get_market_trend():
    """ 
    使用 DBB ETF 計算技術指標 (均線)
    回傳: 趨勢狀態字串, MA20數值, MA60數值
    """
    try:
        # 抓取過去 4 個月的資料來算 MA60
        etf = yf.Ticker(TREND_PROXY_TICKER)
        hist = etf.history(period="4mo")
        
        if len(hist) < 60:
            return "資料不足", 0, 0

        # 計算均線
        price = hist['Close'].iloc[-1]
        ma5 = hist['Close'].tail(5).mean()
        ma20 = hist['Close'].tail(20).mean() # 月線
        ma60 = hist['Close'].tail(60).mean() # 季線
        
        # 趨勢邏輯判斷
        trend_status = "盤整中"
        trend_emoji = "⚖️"
        
        # 1. 多頭排列 (最強): 價格 > 月線 > 季線
        if price > ma20 and ma20 > ma60:
            trend_status = "多頭排列 (強勢)"
            trend_emoji = "🚀"
        # 2. 短多 (反彈): 價格 > 月線，但 月線 < 季線
        elif price > ma20 and ma20 < ma60:
            trend_status = "站上月線 (反彈)"
            trend_emoji = "📈"
        # 3. 空頭排列 (最弱): 價格 < 月線 < 季線
        elif price < ma20 and ma20 < ma60:
            trend_status = "空頭排列 (弱勢)"
            trend_emoji = "🐻"
        # 4. 跌破月線 (回檔): 價格 < 月線，但 月線 > 季線
        elif price < ma20 and ma20 > ma60:
            trend_status = "跌破月線 (整理)"
            trend_emoji = "📉"
            
        return {
            "status": f"{trend_emoji} {trend_status}",
            "ma20": ma20,
            "ma60": ma60,
            "price": price
        }
    except Exception as e:
        print(f"趨勢計算失敗: {e}")
        return None

def get_tw_stocks_status():
    """ 獲取台股狀態 (含特性標籤) """
    table_lines = []
    header = f"{'代號':<5} {'名稱':<4} {'現價':>6} {'漲跌%':>7} {'張數':>5}  {'特性'}"
    table_lines.append(header)
    table_lines.append("-" * 42)

    for stock_info in STOCK_LIST:
        symbol = stock_info['id']
        name = stock_info['name']
        tag = stock_info['tag']
        
        try:
            stock = yf.Ticker(symbol)
            data = stock.history(period="5d")
            
            if len(data) >= 1:
                price = data['Close'].iloc[-1]
                volume = 0
                if 'Volume' in data.columns: volume = int(data['Volume'].iloc[-1] / 1000)
                
                stock_code = symbol.replace('.TW', '')
                change_str = "0.00%"
                if len(data) >= 2:
                    prev = data['Close'].iloc[-2]
                    change = ((price - prev) / prev) * 100
                    sign = "+" if change > 0 else ""
                    change_str = f"{sign}{change:.2f}%"
                
                line = f"{stock_code:<5} {name:<4} {price:>6.2f} {change_str:>7} {volume:>5}  {tag}"
                table_lines.append(line)
            else:
                table_lines.append(f"{symbol} 無資料")
        except:
            table_lines.append(f"{symbol} 讀取錯誤")
            
    return "\n".join(table_lines)

# --- 主程式 ---

def main():
    print("開始執行策略分析...")
    
    nickel_data = get_nickel_price()
    market_trend = get_market_trend()
    
    message = ""
    
    # 判斷整體氣氛 (結合 鎳價漲跌 + 市場均線)
    is_bullish_price = nickel_data and nickel_data['change_pct'] > 1.0
    is_bullish_trend = market_trend and "多頭" in market_trend['status']
    
    title_emoji = "🔥" if (is_bullish_price and is_bullish_trend) else "📊"
    
    message += f"{title_emoji} **鎳價策略戰情室** ({datetime.now().strftime('%Y-%m-%d')})\n\n"

    # --- 1. 即時報價區 ---
    if nickel_data:
        # 簡單判斷漲跌符號
        pct_sign = "🔺" if nickel_data['change_pct'] > 0 else "🔻"
        message += f"**🔩 LME 鎳價 (Spot)**\n"
        message += f"> 現價: `{nickel_data['price']:,.0f}` USD\n"
        message += f"> 漲跌: `{pct_sign} {nickel_data['change_pct']}%`\n"
    else:
        message += f"**🔩 LME 鎳價**: `讀取失敗` (請檢查 Business Insider)\n"

    # --- 2. 技術趨勢區 (新功能) ---
    if market_trend:
        message += f"**🌊 原物料趨勢 (DBB ETF)**\n"
        message += f"> 狀態: **{market_trend['status']}**\n"
        message += f"> 均線: 月線 {market_trend['ma20']:.2f} | 季線 {market_trend['ma60']:.2f}\n"
        message += f"> 策略: "
        
        # 根據均線給出簡單策略建議
        if "多頭" in market_trend['status']:
            message += "`順勢做多，拉回找買點` ✅\n"
        elif "站上月線" in market_trend['status']:
            message += "`反彈行情，短線操作` ⚠️\n"
        elif "空頭" in market_trend['status']:
            message += "`空頭走勢，保守觀望` ⛔\n"
        else:
            message += "`區間震盪，低買高賣` 🔄\n"
    message += "\n"

    # --- 3. 台股區 ---
    message += f"**🏭 不銹鋼個股表現**\n"
    message += "```yaml\n"
    message += get_tw_stocks_status()
    message += "\n```"
    
    # --- 4. 訊號總結 ---
    if is_bullish_price and is_bullish_trend:
        message = "@here **🚀 強力訊號：鎳價大漲 + 趨勢多頭！全力留意！**\n" + message
    elif is_bullish_price and not is_bullish_trend:
        message = "@here **⚠️ 注意：鎳價反彈，但大趨勢仍偏空 (搶短請小心)**\n" + message

    send_discord_message(message)

if __name__ == "__main__":
    main()
