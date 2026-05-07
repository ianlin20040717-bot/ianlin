import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import plotly.graph_objects as go

# 設定網頁標題與圖示
st.set_page_config(page_title="台股處置預警雷達", layout="wide")

@st.cache_data(ttl=3600)
def get_stock_dict():
    """自動獲取全市場代碼與名稱"""
    mapping = {}
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36"}
    try:
        res_tse = requests.get("https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL", headers=headers, timeout=10)
        if res_tse.status_code == 200:
            for item in res_tse.json():
                if len(item['Code']) == 4 and item['Code'].isdigit():
                    mapping[f"{item['Code']} {item['Name']}"] = f"{item['Code']}.TW"
        
        res_otc = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_mainboard_quotes", headers=headers, timeout=10)
        if res_otc.status_code == 200:
            for item in res_otc.json():
                if len(item['SecuritiesCompanyCode']) == 4 and item['SecuritiesCompanyCode'].isdigit():
                    mapping[f"{item['SecuritiesCompanyCode']} {item['CompanyName']}"] = f"{item['SecuritiesCompanyCode']}.TWO"
    except:
        st.error("無法連線至證交所 API (股票清單)")
    return mapping

def extract_match_time(text):
    """從官方落落長的公告中萃取出撮合時間"""
    if "二十分" in text or "20分" in text:
        return "🛑 20分鐘撮合 (流動性極度冰凍)"
    elif "五分" in text or "5分" in text:
        return "⚠️ 5分鐘撮合 (流動性較差)"
    elif "十分" in text or "10分" in text:
        return "⚠️ 10分鐘撮合"
    else:
        return "🔍 特殊人工撮合"

@st.cache_data(ttl=600)
def get_official_disposal_list():
    """連線政府 API，抓取官方目前正在處置中的名單與細節"""
    disposal_dict = {}
    headers = {"User-Agent": "Mozilla/5.0"}
    
    try:
        res_tse = requests.get("https://www.twse.com.tw/announcement/punish?response=json", headers=headers, timeout=5)
        if res_tse.status_code == 200:
            data = res_tse.json().get('data', [])
            for item in data:
                if len(item) >= 9:
                    code = item[2]
                    measure_text = f"{item[7]}：\n{item[8]}"
                    disposal_dict[code] = {
                        'period': item[6],
                        'measure': measure_text,
                        'match_time': extract_match_time(measure_text)
                    }
    except: pass
    
    try:
        res_otc = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_disposal_information", headers=headers, timeout=5)
        if res_otc.status_code == 200:
            for item in res_otc.json():
                code = item.get('SecuritiesCompanyCode', '')
                if code:
                    measure_text = item.get('PunishmentMeasure', '')
                    if item.get('PunishmentContent'):
                        measure_text += f"：\n{item.get('PunishmentContent')}"
                    disposal_dict[code] = {
                        'period': item.get('PunishmentPeriod', '未知期間'),
                        'measure': measure_text,
                        'match_time': extract_match_time(measure_text)
                    }
    except: pass
    
    return disposal_dict

@st.cache_data(ttl=3600)
def get_twse_history(stock_code):
    """抓取上市股票的【注意】與【處置】歷史紀錄"""
    headers = {"User-Agent": "Mozilla/5.0"}
    attn_list = []
    disp_list = []
    try:
        # 抓取歷史注意股
        r1 = requests.get(f"https://www.twse.com.tw/announcement/notice?response=json&stockNo={stock_code}", headers=headers, timeout=5)
        if r1.status_code == 200:
            data = r1.json().get('data', [])
            for item in data:
                attn_list.append({"公告日期": item[0], "累計/詳細原因": item[3]})
                
        # 抓取歷史處置股
        r2 = requests.get(f"https://www.twse.com.tw/announcement/punish?response=json&stockNo={stock_code}", headers=headers, timeout=5)
        if r2.status_code == 200:
            data = r2.json().get('data', [])
            for item in data:
                disp_list.append({"公告日期": item[0], "處置期間": item[6], "處置內容": item[7]})
    except:
        pass
    return pd.DataFrame(attn_list), pd.DataFrame(disp_list)

# ==========================================
# 核心計算邏輯區
# ==========================================
def check_attention(prices_list):
    if len(prices_list) < 90: return False
    p_now = prices_list[-1]
    ret_6d = abs((p_now / prices_list[-6]) - 1)
    ret_30d = (p_now / prices_list[-30]) - 1
    ret_60d = (p_now / prices_list[-60]) - 1
    ret_90d = (p_now / prices_list[-90]) - 1
    return (ret_6d > 0.25) or (ret_30d > 1.0) or (ret_60d > 1.3) or (ret_90d > 1.6)

def simulate_future(prices, current_streak, direction='up'):
    sim_prices = prices.copy()
    streak = current_streak
    
    for day in range(1, 11):
        last_p = sim_prices[-1]
        next_p = last_p * 1.099 if direction == 'up' else last_p * 0.901
        sim_prices.append(next_p)
        
        if check_attention(sim_prices):
            streak += 1
        else:
            streak = 0
            
        if streak >= 3:
            return day, next_p
    return None, None


# --- UI 介面 ---
st.title("🎯 台股處置風險預警雷達")
st.markdown("同步官方最新處置名單，並提供歷史違規溯源與未來情境推演。")

# 側邊欄
mode = st.sidebar.selectbox("選擇模式", ["個股深度診斷", "全市場掃描 (建置中)"])
stock_dict = get_stock_dict()
official_disposal = get_official_disposal_list()

if mode == "個股深度診斷":
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("參數設定與官方狀態")
        if not stock_dict:
            st.warning("正在載入股票清單中...")
        else:
            search = st.selectbox("搜尋股票 (支援代碼或名稱)", options=list(stock_dict.keys()))
            ticker = stock_dict[search]
            pure_code = ticker.split('.')[0] 
            
            # ==========================================
            # 官方處置狀態判定區塊
            # ==========================================
            is_disposal_now = pure_code in official_disposal
            
            if is_disposal_now:
                status_info = official_disposal[pure_code]
                st.error(f"### 🚨 本股目前為【官方處置股】\n## {status_info['match_time']}")
                st.info(f"**🗓️ 處置期間**：{status_info['period']}")
                with st.expander("📝 點此展開查看官方完整處置內容與規定"):
                    st.markdown(status_info['measure'])
            else:
                st.success("✅ 官方狀態：目前為正常交易 (非處置股)")
            
            # ==========================================
            # 🆕 新增：歷史公告查詢區塊 (對齊圖片需求)
            # ==========================================
            st.markdown("---")
            st.markdown("**想查詢注意股或處置股歷史公告？**")
            hist_col1, hist_col2 = st.columns(2)
            
            if ticker.endswith('.TW'):
                # 上市股票：直接抓取 API 資料顯示
                df_attn, df_disp = get_twse_history(pure_code)
                with hist_col1:
                    with st.expander("📜 歷史注意公告"):
                        if not df_attn.empty:
                            st.dataframe(df_attn, use_container_width=True, hide_index=True)
                        else:
                            st.write("近期無注意股紀錄。")
                with hist_col2:
                    with st.expander("🛑 歷史處置公告"):
                        if not df_disp.empty:
                            st.dataframe(df_disp, use_container_width=True, hide_index=True)
                        else:
                            st.write("近期無處置股紀錄。")
            else:
                # 上櫃股票：提供一鍵跳轉官方查詢按鈕
                with hist_col1:
                    st.link_button("📜 櫃買中心【注意股】查詢", "https://www.tpex.org.tw/web/bulletin/notice/notice_result.php?l=zh-tw")
                with hist_col2:
                    st.link_button("🛑 櫃買中心【處置股】查詢", "https://www.tpex.org.tw/web/bulletin/disposal_information/disposal_information_result.php?l=zh-tw")
            
            st.markdown("---")
            
            with st.spinner('正在載入歷史價量資料...'):
                try:
                    df = yf.download(ticker, period="120d", progress=False)
                except:
                    df = pd.DataFrame()
            
            if not df.empty and 'Close' in df and len(df) >= 90:
                closes = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
                today_close = closes.iloc[-1]
                st.metric("當前收盤價", f"{today_close:.2f}")
                
                # 計算明日門檻 (6日)
                ref_6d = closes.iloc[-5]
                danger_up = ref_6d * 1.25
                gap = ((danger_up / today_close) - 1) * 100
                
                st.warning(f"**明日漲幅門檻**: {danger_up:.2f} ({gap:+.2f}%)")
                st.caption("若明日收盤價超過此價位，將觸發注意股條件。")
                
                # ==========================================
                # 未來極端情境推演
                # ==========================================
                if not is_disposal_now:
                    st.markdown("---")
                    st.subheader("🔮 未來極端情境推演")
                    
                    history_prices = closes.tolist()
                    current_consecutive = 0
                    test_list = history_prices.copy()
                    
                    for _ in range(5):
                        if check_attention(test_list):
                            current_consecutive += 1
                            test_list.pop()
                        else:
                            break
                    
                    st.write(f"目前狀態：已連續 **{current_consecutive}** 日列為注意股")
                    
                    days_up, price_up = simulate_future(history_prices, current_consecutive, direction='up')
                    
                    if days_up:
                        if days_up == 1:
                            st.error(f"🚀 **若明日強勢漲停**：\n\n最快只需 **{days_up} 天 (T+{days_up})** 就會進入處置！\n\n*(預估觸發價：{price_up:.2f})*")
                        else:
                            st.info(f"🚀 **若連續無腦拉漲停**：\n\n最快還需 **{days_up} 天 (T+{days_up})** 才會進入處置。\n\n*(預估觸發價：{price_up:.2f})*")
                    else:
                        st.success("🚀 **即使連拉 10 根漲停**，短期內也不會進入處置。")
                        
            else:
                st.error("歷史資料不足或抓取失敗。")

    with col2:
        st.subheader("風險監控儀表板")
        if 'df' in locals() and not df.empty and len(df) >= 90:
            rets = {
                "6日累積": (today_close / closes.iloc[-6] - 1) * 100,
            }
            
            if is_disposal_now:
                gauge_color = "rgba(0,0,0,0.5)"
                title_text = "🚨 已在處置中，儀表板僅供參考"
            else:
                gauge_color = "rgba(0,0,0,0.5)"
                title_text = "近 6 日累積漲跌幅 (%)<br><span style='font-size:0.8em;color:gray'>紅線為 25% 注意股門檻</span>"

            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = abs(rets["6日累積"]),
                domain = {'x': [0, 1], 'y': [0, 1]},
                title = {'text': title_text},
                gauge = {
                    'axis': {'range': [0, 40]},
                    'bar': {'color': gauge_color},
                    'steps': [
                        {'range': [0, 15], 'color': "#8fce00"},   
                        {'range': [15, 25], 'color': "#f1c232"},  
                        {'range': [25, 40], 'color': "#cc0000"}], 
                    'threshold': {'line': {'color': "white", 'width': 4}, 'thickness': 0.75, 'value': 25}
                }
            ))
            st.plotly_chart(fig, use_container_width=True)