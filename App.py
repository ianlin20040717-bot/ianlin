import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.graph_objects as go
import urllib.parse
from datetime import datetime, timedelta

# ==========================================
# 🔑 在此設定你的 FinMind VIP Token
# ==========================================
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiaWFubGluIiwiZW1haWwiOiJpYW5saW4yMDA0MDcxN0BnbWFpbC5jb20iLCJ0b2tlbl92ZXJzaW9uIjowfQ.G5jm2LKIg3BaZUIt7SIpqS1V1eZwzZg4ojuK2Naq2-8"  # 記得補上你加了雙引號的 Token！

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
            for item in res.json().get('data', []):
                code = item.get('stock_id', '')
                name = item.get('stock_name', '')
                market = item.get('type', '')
                if len(code) == 4 and code.isdigit():
                    suffix = ".TW" if market == 'twse' else ".TWO"
                    mapping[f"{code} {name}"] = f"{code}{suffix}"
    except: pass

    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        res_tse = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", headers=headers, timeout=5)
        if res_tse.status_code == 200:
            for item in res_tse.json():
                if len(item['Code']) == 4 and item['Code'].isdigit(): mapping[f"{item['Code']} {item['Name']}"] = f"{item['Code']}.TW"
        
        res_otc = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", headers=headers, timeout=5)
        if res_otc.status_code == 200:
            for item in res_otc.json():
                if len(item['SecuritiesCompanyCode']) == 4 and item['SecuritiesCompanyCode'].isdigit(): mapping[f"{item['SecuritiesCompanyCode']} {item['CompanyName']}"] = f"{item['SecuritiesCompanyCode']}.TWO"
    except: pass 
    return mapping

def extract_match_time(text):
    if "二十分" in text or "20分" in text: return "🛑 20分鐘撮合"
    elif "五分" in text or "5分" in text: return "⚠️ 5分鐘撮合"
    elif "十分" in text or "10分" in text: return "⚠️ 10分鐘撮合"
    else: return "🔍 特殊人工撮合"

def fetch_with_proxy(url):
    """防彈機制：繞過政府 API 阻擋"""
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=3)
        if r.status_code == 200: return r.json()
    except: pass
    
    proxies = [
        f"https://api.allorigins.win/raw?url={urllib.parse.quote(url)}",
        f"https://corsproxy.io/?{urllib.parse.quote(url)}"
    ]
    for proxy in proxies:
        try:
            r = requests.get(proxy, headers=headers, timeout=5)
            if r.status_code == 200: return r.json()
        except: pass
    return None

@st.cache_data(ttl=600)
def get_finmind_disposal_list(token):
    """抓取官方處置名單 (目前進行中)"""
    disposal_dict = {}
    api_success = False 
    
    if not token or token == "YOUR_FINMIND_TOKEN_HERE":
        return disposal_dict, False

    try:
        today_str = datetime.now().strftime("%Y-%m-%d")
        start_str = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        url = "https://api.finmindtrade.com/api/v4/data"
        params = {"dataset": "TaiwanStockDispositionSecuritiesPeriod", "start_date": start_str, "end_date": today_str, "token": token}
        res = requests.get(url, params=params, timeout=10)
        data = res.json()
        
        if data.get("msg") == "success":
            api_success = True
            df = pd.DataFrame(data["data"])
            if not df.empty:
                df['period_end_dt'] = pd.to_datetime(df['period_end'])
                active_df = df[df['period_end_dt'] >= pd.Timestamp.today().normalize()]
                for _, row in active_df.iterrows():
                    code = str(row['stock_id'])
                    measure_text = str(row['measure'])
                    disposal_dict[code] = {
                        'period': f"{row['period_start']} ~ {row['period_end']}",
                        'measure': measure_text,
                        'match_time': extract_match_time(measure_text)
                    }
    except: pass
    return disposal_dict, api_success

@st.cache_data(ttl=3600)
def get_historical_records(pure_code, is_twse, token):
    """取得個股歷史注意與處置紀錄 (回傳兩個 DataFrame)"""
    attn_records = []
    disp_records = []

    if is_twse:
        # 上市：直接調用 TWSE 歷史 API (透過 Proxy 防擋)
        url_notice = f"https://www.twse.com.tw/announcement/notice?response=json&stockNo={pure_code}"
        notice_data = fetch_with_proxy(url_notice)
        if notice_data and 'data' in notice_data:
            for item in notice_data['data']:
                attn_records.append({"日期": item[0], "原因": item[3]})

        url_punish = f"https://www.twse.com.tw/announcement/punish?response=json&stockNo={pure_code}"
        punish_data = fetch_with_proxy(url_punish)
        if punish_data and 'data' in punish_data:
            for item in punish_data['data']:
                disp_records.append({"處置期間": item[6], "處置內容": item[7]})
    else:
        # 上櫃：處置紀錄使用 FinMind API
        if token and token != "YOUR_FINMIND_TOKEN_HERE":
            try:
                start_str = (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d")
                today_str = datetime.now().strftime("%Y-%m-%d")
                url = "https://api.finmindtrade.com/api/v4/data"
                params = {"dataset": "TaiwanStockDispositionSecuritiesPeriod", "start_date": start_str, "end_date": today_str, "data_id": pure_code, "token": token}
                res = requests.get(url, params=params, timeout=5)
                data = res.json()
                if data.get("msg") == "success" and data.get("data"):
                    for item in data["data"]:
                        if str(item['stock_id']) == pure_code:
                            disp_records.append({"處置期間": f"{item['period_start']} ~ {item['period_end']}", "處置內容": item['measure']})
            except: pass
        
        # 坦白說，上櫃注意股缺乏單一查詢 API，加入提示框
        attn_records = [{"日期": "系統提示", "原因": "上櫃股票之歷史注意紀錄，受限於櫃買中心老舊系統，暫不支援直接顯示。請點擊按鈕前往官方查詢。"}]

    return pd.DataFrame(attn_records), pd.DataFrame(disp_records)

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
            # 🚀 修復 NaN 問題：移除股票代碼中可能出現的 * 號 (如 6531 愛普*)
            pure_code = ticker.split('.')[0].replace('*', '') 
            
        is_twse = ticker.endswith('.TW') if ticker else True
        # 強制整理乾淨的 yfinance 抓取代碼
        clean_ticker = f"{pure_code}.TW" if is_twse else f"{pure_code}.TWO"

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
            
        # ==========================================
        # 📊 歷史數據內嵌區塊 (取代原有的外部連結)
        # ==========================================
        st.markdown("---")
        df_attn, df_disp = get_historical_records(pure_code, is_twse, FINMIND_TOKEN)
        
        hist_col1, hist_col2 = st.columns(2)
        with hist_col1:
            attn_count = 0 if '系統提示' in df_attn.values else len(df_attn)
            with st.expander(f"📜 歷史【注意股】紀錄 (共 {attn_count} 次)"):
                if not df_attn.empty:
                    st.dataframe(df_attn, hide_index=True, use_container_width=True)
                else:
                    st.write("近期無注意股紀錄。")
                if not is_twse: # 上櫃特別處理
                    st.link_button("前往櫃買中心手動查詢", "https://www.tpex.org.tw/web/bulletin/notice/notice_result.php?l=zh-tw")
                    
        with hist_col2:
            with st.expander(f"🛑 歷史【處置股】紀錄 (共 {len(df_disp)} 次)"):
                if not df_disp.empty:
                    st.dataframe(df_disp, hide_index=True, use_container_width=True)
                else:
                    st.write("近期無處置股紀錄。")
        st.markdown("---")
        
        with st.spinner('正在載入最新價量資料與運算...'):
            df = pd.DataFrame()
            try:
                df = yf.download(clean_ticker, period="120d", progress=False)
            except: pass
        
        # 🚀 修復 NaN 問題：濾除掉沒有收盤價的無效天數
        if not df.empty and 'Close' in df:
            closes = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
            closes = closes.dropna() 
            
            if len(closes) >= 90:
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
                st.error("歷史資料不足 90 天，無法運算。")
        else:
            st.error("歷史資料抓取失敗，請確認代碼是否正確。")

    with col2:
        st.subheader("風險監控儀表板")
        if 'closes' in locals() and len(closes) >= 90:
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
