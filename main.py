import yfinance as yf
import requests
import pandas as pd
from bs4 import BeautifulSoup
import os

# --- 設定區 ---

DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK')

# MoneyDJ 倫敦鎳價網址
NICKEL_URL = "https://www.moneydj.com/z/ze/zeq/zeqa_D0200990.djhtm"

# 台股不銹鋼概念股
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

def get_nickel_price_from_moneydj():
    """
    從 MoneyDJ 爬取倫敦鎳期貨價
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(NICKEL_URL, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'lxml')
        
        # --- 解析 MoneyDJ 網頁結構 (這部分若網站改版可能會失效) ---
        # 尋找包含價格的表格
        # MoneyDJ 的即時報價通常在 id="z_table" 或特定的 class 裡
        # 這裡我們嘗試抓取頁面上最明顯的報價欄位
        
        # 根據 MoneyDJ 結構，報價通常在 t01 類的表格中
        # 我們直接抓取頁面標題下方的報價數據
        # 假設結構：<td class="t3n1">16,250.00</td>
        
        # 抓取最新價格 (通常是第一個 t3n1 紅色 或 t3n2 綠色)
        price_element = soup.find('td', class_=['t3n1', 't3n2']) # 嘗試抓取漲或跌的樣式
        
        # 為了保險，我們抓取表格中的具體位置
        # MoneyDJ 頁面表格結構通常固定
        table = soup.find('table', {'id': 'Ctl00_ContentPlaceHolder1_dt_1'})
        if not table:
             # 如果找不到特定 ID，嘗試通用表格
             print("找不到特定 ID 表格，嘗試通用解析...")
             return None

        rows = table.find_all('tr')
        if len(rows) < 2:
            return None
            
        # 第二行通常是最新數據: 日期 | 收盤 | 漲跌 | 漲跌幅
        cols = rows[1].find_all('td')
        
        # 資料解析
        date_str = cols[0].text.strip()
        price_str = cols[1].text.strip().replace(',', '')
        change_val_str = cols[2].text.strip().replace(',', '')
        change_pct_str = cols[3].text.strip().replace('%', '')
        
        current_price = float(price_str)
        change_pct = float(change_pct_str)
        
        # 判斷趨勢圖示
        trend_icon = "➖ 盤整"
        if change_pct > 0.5: trend_icon = "📈 轉強"
        if change_pct > 1.5: trend_icon = "🔥 大漲"
        if change_pct < -0.5: trend_icon = "📉 轉弱"
        
        return {
            "source": "LME Nickel (MoneyDJ)",
            "price": current_price,
            "change_pct": change_pct,
            "change_val": change_val_str,
            "date": date_str,
            "trend": trend_icon
        }

    except Exception as e:
        print(f"爬取 MoneyDJ 失敗: {e}")
        return None

def get_tw_stocks_status():
    """ 獲取台股狀態 (維持原樣) """
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
    
    # 1. 嘗試爬取 MoneyDJ
    nickel_data = get_nickel_price_from_moneydj()
    
    # 2. 如果爬蟲失敗，我們可能需要一個備案，或直接報錯
    if not nickel_data:
        print("❌ 無法抓取鎳價，請檢查 MoneyDJ 網頁結構是否改變")
        send_discord_message("⚠️ 錯誤報告: 無法爬取 MoneyDJ 鎳價資料，請檢查程式。")
        return

    # 3. 判斷訊號
    is_bullish = nickel_data['change_pct'] > 1.0 # 漲幅超過 1% 視為強勢
    
    # 4. 組合訊息
    title_emoji = "🔥" if is_bullish else "⚖️"
    
    message = f"{title_emoji} **倫敦鎳價追蹤日報** ({nickel_data['date']})\n\n"
    
    message += f"**🔩 LME 鎳期貨 (MoneyDJ)**\n"
    message += f"> 收盤價: `{nickel_data['price']:,.0f}` USD/Ton\n" # 加千分位
    message += f"> 漲跌幅: `{nickel_data['change_pct']}%` ({nickel_data['change_val']})\n"
    message += f"> 狀態: **{nickel_data['trend']}**\n"
    message += f"> [查看圖表]({NICKEL_URL})\n\n"
    
    message += f"**🏭 台灣不銹鋼族群**\n"
    message += "```yaml\n"
    message += get_tw_stocks_status()
    message += "\n```"
    
    if is_bullish:
        message = "@here **🔔 鎳價上漲！不銹鋼留意！**\n" + message

    send_discord_message(message)

if __name__ == "__main__":
    main()
