import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.graph_objects as go
from datetime import datetime, timedelta

# ==========================================
# 🔑 在此設定你的 FinMind VIP Token
# ==========================================
# 請將下方引號內的文字替換為你專屬的 Token
FINMIND_TOKEN =eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiaWFubGluIiwiZW1haWwiOiJpYW5saW4yMDA0MDcxN0BnbWFpbC5jb20iLCJ0b2tlbl92ZXJzaW9uIjowfQ.G5jm2LKIg3BaZUIt7SIpqS1V1eZwzZg4ojuK2Naq2-8

# 設定網頁標題與圖示
st.set_page_config(page_title="台股處置預警雷達", layout="wide")

@st.cache_data(ttl=86400)
def get_stock_dict():
    """全市場代碼與名稱 (FinMind TaiwanStockInfo)"""
    mapping = {}
    try:
        url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json().get('data', [])
            for item in data:
                code = item.get('stock_id', '')
                name = item.get('stock_name', '')
                market = item.get('type', '')
                if len(code) == 4 and code.isdigit():
                    suffix = ".TW" if market == 'twse' else ".TWO"
                    mapping[f"{code} {name}"] = f"{code}{suffix}"
    except Exception as e:
        st.error("無法連線至 FinMind 獲取股票清單。")
    return mapping

def extract_match_time(text):
    if "二十分" in text or "20分" in text: return "🛑 20分鐘撮合"
    elif "五分" in text or "5分" in text: return "⚠️ 5分鐘撮合"
    elif "十分" in text or "10分" in text: return "⚠️ 10分鐘撮合"
    else: return "🔍 特殊人工撮合"

@st.cache_data(ttl=600)
def get_finmind_disposal_list(token):
    """使用 FinMind VIP 權限抓取官方處置名單"""
    disposal_dict = {}
    api_success = False 
    
    if not token or token == "YOUR_FINMIND_TOKEN_HERE":
        return disposal_dict, False

    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        # 往回抓 30 天，確保涵蓋目前所有正在處置中的股票
        start_str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {
            "dataset": "TaiwanStockDispositionSecuritiesPeriod",
            "start_date": start_str,
            "end_date": today_str,
            "token": token
        }
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        
        if data.get("msg") == "success":
            api_success = True
            df = pd.DataFrame(data["data"])
            if not df.empty:
                df['period_end_dt'] = pd.to_datetime(df['period_end'])
                # 嚴格過濾：只留下「今天」仍處於處置期間內的股票
                active_df = df[df['period_end_dt'] >= pd.Timestamp.today().normalize()]
                
                for _, row in active_df.iterrows():
                    code = str(row['stock_id'])
                    measure_text = str(row['measure'])
                    period = f"{row['period_start']} ~ {row['period_end']}"
                    disposal_dict[code] = {
                        'period': period,
                        'measure': measure_text,
                        'match_time': extract_match_time(measure_text)
                    }
        else:
            st.sidebar.error(f"FinMind API 錯誤: {data.get('msg')}")
    except Exception as e:
        st.sidebar.error("FinMind 連線失敗，請檢查網路狀態。")
                
    return disposal_dict, api_success

# 核心計算邏輯
def check_attention(prices_list):
    if len(prices_list) < 90: return False
    p_now = prices_list[-1]
    return (abs((p_now / prices_list[-6]) - 1) > 0.25) or ((p_now / prices_list[-30]) - 1 > 1.0) or ((p_now / prices_list[-60]) - 1 > 1.3) or ((p_now / prices_list[-90]) - 1 > 1.6)

def simulate_future(prices, current_streak, direction='up'):
    sim_prices = prices.copy()
    streak = current_streak
    for day in range(1, 11):
        next_p = sim_prices[-1] * 1.099 if direction == 'up' else sim_prices[-1] * 0.901
        sim_prices.append(next_p)
        if check_attention(sim_prices): streak += 1
        else: streak = 0
        if streak >= 3: return day, next_p
    return None, None

# --- UI 介面 ---
st.title("🎯 台股處置風險預警雷達 (FinMind PRO 版)")
st.markdown("已串接 FinMind 專業資料庫，提供最穩定之歷史溯源與未來情境推演。")

mode = st.sidebar.selectbox("選擇模式", ["個股深度診斷", "全市場掃描 (建置中)"])

st.sidebar.markdown("---")
st.sidebar.success("🟢 FinMind 專屬通道已啟用")

stock_dict = get_stock_dict()
official_disposal, api_success = get_finmind_disposal_list(FINMIND_TOKEN)

if mode == "個股深度診斷":
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("參數設定與官方狀態")
        
        pure_code = ""
        ticker = ""
        
        if not stock_dict:
            st.warning("⚠️ 無法獲取股票清單，已切換為手動輸入模式。")
            user_input = st.text_input("請輸入 4 碼股票代碼 (例: 2454)", "2454").strip()
            pure_code = user_input
        else:
            search = st.selectbox(
                "🔍 搜尋股票 (可直接輸入代碼或中文名稱，系統會自動聯想)", 
                options=list(stock_dict.keys()), 
                index=list(stock_dict.keys()).index("2454 聯發科") if "2454 聯發科" in stock_dict else 0
            )
            ticker = stock_dict[search]
            pure_code = ticker.split('.')[0] 
            
        with st.spinner('正在載入最新價量資料與運算...'):
            df = pd.DataFrame()
            try:
                if not ticker:
                    test_ticker = f"{pure_code}.TW"
                    df = yf.download(test_ticker, period="120d", progress=False)
                    if df.empty or 'Close' not in df:
                        test_ticker = f"{pure_code}.TWO"
                        df = yf.download(test_ticker, period="120d", progress=False)
                    ticker = test_ticker 
                else:
                    df = yf.download(ticker, period="120d", progress=False)
            except: pass
            
        is_twse = ticker.endswith('.TW') if ticker else True
            
        is_disposal_now = pure_code in official_disposal
        
        if is_disposal_now:
            status_info = official_disposal[pure_code]
            st.error(f"### 🚨 本股目前為【官方處置股】\n## {status_info['match_time']}")
            st.info(f"**🗓️ 處置期間**：{status_info['period']}")
            with st.expander("📝 點此展開查看官方完整處置內容與規定"):
                st.markdown(status_info['measure'])
        elif not api_success:
            st.error("❌ FinMind Token 驗證失敗或無效。請確認程式碼最上方的 FINMIND_TOKEN 設定是否正確。")
        else:
            st.success("✅ 官方狀態：目前為正常交易 (非處置股)")
            
        st.markdown("---")
        st.markdown("**想查詢官方處置/注意歷史公告？**")
        hist_col1, hist_col2 = st.columns(2)
        if is_twse:
            with hist_col1: st.link_button("📜 歷史【注意股】查詢", "https://www.twse.com.tw/zh/announcement/notice.html")
            with hist_col2: st.link_button("🛑 歷史【處置股】查詢", "https://www.twse.com.tw/zh/announcement/punish.html")
        else:
            with hist_col1: st.link_button("📜 歷史【注意股】查詢", "https://www.tpex.org.tw/web/bulletin/notice/notice_result.php?l=zh-tw")
            with hist_col2: st.link_button("🛑 歷史【處置股】查詢", "https://www.tpex.org.tw/web/bulletin/disposal_information/disposal_information_result.php?l=zh-tw")
        
        st.markdown("---")
        
        if not df.empty and 'Close' in df and len(df) >= 90:
            closes = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
            today_close = closes.iloc[-1]
            st.metric("當前收盤價", f"{today_close:.2f}")
            
            ref_6d = closes.iloc[-5]
            danger_up = ref_6d * 1.25
            gap = ((danger_up / today_close) - 1) * 100
            
            st.warning(f"**明日漲幅門檻**: {danger_up:.2f} ({gap:+.2f}%)")
            st.caption("若明日收盤價超過此價位，將觸發注意股條件。")
            
            if not is_disposal_now:
                st.markdown("---")
                st.subheader("🔮 未來極端情境推演")
                history_prices = closes.tolist()
                current_consecutive = 0
                test_list = history_prices.copy()
                for _ in range(5):
                    if check_attention(test_list):
                        current_consecutive += 1; test_list.pop()
                    else: break
                
                st.write(f"目前狀態：已連續 **{current_consecutive}** 日列為注意股")
                days_up, price_up = simulate_future(history_prices, current_consecutive, direction='up')
                
                if days_up:
                    if days_up == 1: st.error(f"🚀 **若明日強勢漲停**：\n最快只需 **{days_up} 天 (T+{days_up})** 進入處置！\n*(預估觸發價：{price_up:.2f})*")
                    else: st.info(f"🚀 **若連續無腦拉漲停**：\n最快還需 **{days_up} 天 (T+{days_up})** 進入處置。\n*(預估觸發價：{price_up:.2f})*")
                else:
                    st.success("🚀 **即使連拉 10 根漲停**，短期內也不會進入處置。")
        else:
            st.error("歷史資料不足或抓取失敗，請確認代碼是否正確。")

    with col2:
        st.subheader("風險監控儀表板")
        if 'df' in locals() and not df.empty and len(df) >= 90:
            rets = {"6日累積": (today_close / closes.iloc[-6] - 1) * 100}
            gauge_color = "rgba(0,0,0,0.5)"
            title_text = "🚨 已在處置中，儀表板僅供參考" if is_disposal_now else "近 6 日累積漲跌幅 (%)<br><span style='font-size:0.8em;color:gray'>紅線為 25% 注意股門檻</span>"

            fig = go.Figure(go.Indicator(
                mode = "gauge+number", value = abs(rets["6日累積"]),
                domain = {'x': [0, 1], 'y': [0, 1]}, title = {'text': title_text},
                gauge = {
                    'axis': {'range': [0, 40]}, 'bar': {'color': gauge_color},
                    'steps': [{'range': [0, 15], 'color': "#8fce00"}, {'range': [15, 25], 'color': "#f1c232"}, {'range': [25, 40], 'color': "#cc0000"}], 
                    'threshold': {'line': {'color': "white", 'width': 4}, 'thickness': 0.75, 'value': 25}
                }
            ))
            st.plotly_chart(fig, use_container_width=True)
