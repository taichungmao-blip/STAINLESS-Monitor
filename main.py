import yfinance as yf
import requests
import pandas as pd
import os

# --- 設定區 ---

DISCORD_WEBHOOK_URL = os.environ.get('DISCORD_WEBHOOK')

# 改用 StockQ，它的 HTML 結構非常簡單，適合程式讀取
# 這是 LME 鎳的專屬頁面
NICKEL_URL = "https://www.stockq.org/raw/nickel.php"

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

def get_nickel_price_from_stockq():
    """
    從 StockQ 讀取 LME 鎳價 (使用 pandas read_html 強力解析)
    """
    try:
        # 偽裝成瀏覽器，避免被擋
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 1. 下載網頁內容
        response = requests.get(NICKEL_URL, headers=headers, timeout=15)
        response.raise_for_status()
        
        # 2. 使用 pandas 自動尋找網頁裡的所有表格
        # StockQ 的編碼有時是 utf-8 有時是 big5，pandas 通常能自動處理，若亂碼需調整 encoding
        dfs = pd.read_html(response.text)
        
        # 3. 尋找包含數據的那個表格
        # StockQ 這個頁面的主要數據通常在第一個或第二個表格
        # 我們直接取長度夠長的那個
        target_df = None
        for df in dfs:
            # 檢查表格欄位是否有 "收盤價" 或 "Close"
            if len(df) > 1 and df.shape[1] >= 5: # 至少要有幾列幾行
                target_df = df
                break
        
        if target_df is None:
            print("找不到合適的價格表格")
            return None

        # StockQ 的表格通常長這樣：
        # Header: 日期 | 收盤價 | 漲跌 | 漲跌幅 | 開盤 | 最高 ...
        # Row 0: 2024/05/xx | 19500 | -50 | -0.25% ...
        
        # 重新整理欄位名稱 (有些表格第一列是 Header)
        target_df.columns = target_df.iloc[0] # 設定第一列為標題
        target_df = target_df[1:] # 刪除第一列資料 (避免重複)

        # 取得最新一筆資料 (通常是第一行)
        latest_row = target_df.iloc[0]
        
        # 解析數據 (欄位名稱可能會變，我們用索引比較保險)
        # index 0: 日期, 1: 收盤價, 2: 漲跌, 3: 漲跌幅
        date_str = str(latest_row.iloc[0])
        price_str = str(latest_row.iloc[1])
        change_val_str = str(latest_row.iloc[2])
        change_pct_str = str(latest_row.iloc[3]).replace('%', '')
        
        current_price = float(price_str.replace(',', ''))
        change_pct = float(change_pct_str)
        
        # 判斷趨勢
        trend_icon = "➖ 盤整"
        if change_pct > 1.0: trend_icon = "📈 轉強"
        if change_pct > 2.0: trend_icon = "🔥 大漲"
        if change_pct < -1.0: trend_icon = "📉 轉弱"
        
        return {
            "source": "LME Nickel (StockQ)",
            "price": current_price,
            "change_pct": change_pct,
            "change_val": change_val_str,
            "date": date_str,
            "trend": trend_icon
        }

    except Exception as e:
        print(f"爬取 StockQ 失敗: {e}")
        # 如果 StockQ 失敗，這裡可以考慮 failover 到其他來源，目前先回報錯誤
        return None

def get_tw_stocks_status():
    """ 獲取台股狀態 (維持不變) """
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
    
    # 1. 抓取 StockQ
    nickel_data = get_nickel_price_from_stockq()
    
    if not nickel_data:
        print("❌ 無法抓取鎳價")
        send_discord_message("⚠️ 錯誤報告: StockQ 爬蟲失敗，請檢查網頁結構。")
        return

    # 2. 判斷訊號
    is_bullish = nickel_data['change_pct'] > 1.0 # 漲幅超過 1%
    
    # 3. 組合訊息
    title_emoji = "🔥" if is_bullish else "⚖️"
    
    message = f"{title_emoji} **倫敦鎳價追蹤日報** ({nickel_data['date']})\n\n"
    
    message += f"**🔩 LME 鎳期貨 (StockQ)**\n"
    message += f"> 收盤價: `{nickel_data['price']:,.0f}` USD/Ton\n"
    message += f"> 漲跌幅: `{nickel_data['change_pct']}%` ({nickel_data['change_val']})\n"
    message += f"> 狀態: **{nickel_data['trend']}**\n"
    message += f"> [查看 StockQ 原圖]({NICKEL_URL})\n\n"
    
    message += f"**🏭 台灣不銹鋼族群**\n"
    message += "```yaml\n"
    message += get_tw_stocks_status()
    message += "\n```"
    
    if is_bullish:
        message = "@here **🔔 鎳價上漲！不銹鋼留意！**\n" + message

    send_discord_message(message)

if __name__ == "__main__":
    main()
