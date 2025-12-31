import yfinance as yf
import requests
import os
from bs4 import BeautifulSoup
from datetime import datetime

# --- 設定區 ---

DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK')

# 改用 Business Insider (Markets Insider)
# 這是國際通用的原物料報價頁面，結構相對穩定
NICKEL_URL = "https://markets.businessinsider.com/commodities/nickel-price"

STOCK_MAP = {
    '2027.TW': '大成鋼',
    '2034.TW': '允強',
    '2030.TW': '彰源',
    '2015.TW': '豐興',
    '2025.TW': '千興'
}

# --- 函數區 ---

def send_discord_message(content):
    if not DISCORD_WEBHOOK_URL:
        print("⚠️ 未設定 Discord Webhook URL")
        return
    
    data = {"content": content, "username": "不銹鋼策略機器人"}
    try:
        requests.post(DISCORD_WEBHOOK_URL, json=data).raise_for_status()
        print("Discord 發送成功")
    except Exception as err:
        print(f"Discord 發送失敗: {err}")

def get_nickel_price():
    """
    從 Business Insider 爬取鎳價
    """
    try:
        # 偽裝成一般瀏覽器 (非常重要)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        }
        
        response = requests.get(NICKEL_URL, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # --- 解析邏輯 (針對 Business Insider) ---
        # 價格通常在 class="price-section__current-value" 或類似結構
        # 這是目前 Markets Insider 的常見結構
        price_div = soup.find('span', class_='price-section__current-value')
        
        # 如果找不到，嘗試備用 Class (網站有時會變)
        if not price_div:
            price_div = soup.find('span', class_='push-data')
            
        if not price_div:
            print("❌ 找不到價格元素 (HTML 結構可能改變)")
            return None
            
        current_price = float(price_div.text.replace(',', ''))
        
        # 抓漲跌幅
        # 通常在 price-section__absolute-value 或 relative-value
        # 這裡簡化處理：如果抓不到漲跌幅，就只回傳價格
        change_pct = 0.0
        try:
            # 嘗試抓取百分比
            pct_div = soup.find('span', class_='price-section__relative-value')
            if pct_div:
                # 格式通常是 "-0.45%" 或 "0.45%"
                pct_text = pct_div.text.replace('%', '').strip()
                change_pct = float(pct_text)
        except:
            pass # 抓不到漲跌幅就算了，不影響主程式

        # 判斷趨勢
        trend_icon = "➖ 盤整"
        if change_pct > 1.0: trend_icon = "📈 轉強"
        if change_pct > 2.0: trend_icon = "🔥 大漲"
        if change_pct < -1.0: trend_icon = "📉 轉弱"
        
        return {
            "price": current_price,
            "change_pct": change_pct,
            "trend": trend_icon,
            "date": datetime.now().strftime('%Y-%m-%d')
        }

    except Exception as e:
        print(f"爬取 Business Insider 失敗: {e}")
        return None

def get_tw_stocks_status():
    """ 獲取台股狀態 (保持不變) """
    table_lines = []
    header = f"{'代號':<5} {'名稱':<4} {'現價':>6}  {'漲跌幅':>7}  {'張數':>5}"
    table_lines.append(header)
    table_lines.append("-" * 35)

    for symbol, name in STOCK_MAP.items():
        try:
            stock = yf.Ticker(symbol)
            data = stock.history(period="5d")
            
            if len(data) >= 1:
                price = data['Close'].iloc[-1]
                # 容錯：如果有成交量資料才處理
                volume = 0
                if 'Volume' in data.columns:
                    volume = int(data['Volume'].iloc[-1] / 1000)
                
                stock_code = symbol.replace('.TW', '')
                
                change_str = "0.00%"
                if len(data) >= 2:
                    prev = data['Close'].iloc[-2]
                    change = ((price - prev) / prev) * 100
                    sign = "+" if change > 0 else ""
                    change_str = f"{sign}{change:.2f}%"
                
                line = f"{stock_code:<5} {name:<4} {price:>6.2f}  {change_str:>7}  {volume:>5}"
                table_lines.append(line)
            else:
                table_lines.append(f"{symbol} 無資料")
        except:
            table_lines.append(f"{symbol} 讀取錯誤")
            
    return "\n".join(table_lines)

# --- 主程式 ---

def main():
    print("開始執行策略分析...")
    
    # 1. 抓取鎳價 (Business Insider)
    nickel_data = get_nickel_price()
    
    # 2. 準備訊息內容
    # 就算鎳價失敗，我們也要發送不銹鋼股價，不能直接 return
    
    message = ""
    is_bullish = False
    
    if nickel_data:
        # 成功抓到鎳價
        is_bullish = nickel_data['change_pct'] > 1.0
        title_emoji = "🔥" if is_bullish else "⚖️"
        
        message += f"{title_emoji} **國際鎳價 & 不銹鋼日報** ({nickel_data['date']})\n\n"
        message += f"**🔩 LME 鎳價 (Business Insider)**\n"
        message += f"> 現價: `{nickel_data['price']:,.0f}` USD\n"
        message += f"> 漲跌: `{nickel_data['change_pct']}%`\n"
        message += f"> 狀態: **{nickel_data['trend']}**\n"
        message += f"> [查看來源]({NICKEL_URL})\n\n"
    else:
        # 抓取失敗 (容錯模式)
        message += f"⚠️ **不銹鋼日報** (鎳價讀取失敗)\n\n"
        message += f"**🔩 LME 鎳價**\n"
        message += f"> 狀態: `暫時無法讀取` (來源網站可能阻擋)\n"
        message += f"> 建議直接查看: [MoneyDJ鎳價]({NICKEL_URL})\n\n"

    # 3. 抓取台股 (這部分最穩定，一定會顯示)
    message += f"**🏭 台灣不銹鋼族群**\n"
    message += "```yaml\n"
    message += get_tw_stocks_status()
    message += "\n```"
    
    # 4. 只有在鎳價真的大漲時才 @here
    if is_bullish:
        message = "@here **🔔 鎳價轉強訊號！**\n" + message

    send_discord_message(message)

if __name__ == "__main__":
    main()
