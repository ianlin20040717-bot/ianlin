import streamlit as st
import pandas as pd
import requests
import time
import plotly.graph_objects as go
import datetime
import os

# ==========================================
# ⚙️ 戰情室 UI 與版面設定
# ==========================================
st.set_page_config(page_title="台股時光機雷達", layout="wide", page_icon="⏳")
st.title("⏳ 台股時光機 - 盤後逐筆還原系統")
st.markdown("輸入股票代號與日期，完美還原當日盤中主力每一筆敲單的節奏！")

# ==========================================
# 📡 數據中樞：對接 FinMind API (安全裝甲版)
# ==========================================
@st.cache_data
def fetch_tick_data(stock_id, date_str, token=""):
    url = "https://api.finmindtrade.com/api/v4/data"
    parameter = {
        "dataset": "TaiwanStockPriceTick",
        "data_id": stock_id,
        "start_date": date_str,
        "end_date": date_str
    }
    
    # 優先序：使用者輸入 > Streamlit Secrets > 環境變數
    final_token = token
    if not final_token and "FINMIND_TOKEN" in st.secrets:
        final_token = st.secrets["FINMIND_TOKEN"]
    if not final_token:
        final_token = os.getenv("FINMIND_TOKEN", "")
        
    if final_token:
        parameter["token"] = final_token
        
    try:
        response = requests.get(url, params=parameter)
        data = response.json()
        
        if data.get("status") == 200:
            if len(data.get("data", [])) > 0:
                df = pd.DataFrame(data["data"])
                
                # 🛡️ 確認欄位結構，防止半夜維護時當機
                if 'Close' in df.columns and 'Volume' in df.columns and 'Time' in df.columns:
                    df = df[['Time', 'Close', 'Volume']]
                    df.columns = ['時間', '成交價', '單量']
                    return df, "success"
                else:
                    error_columns = list(df.columns)
                    return pd.DataFrame(), f"攔截到異常格式！伺服器目前高機率正在【半夜結算維護中】。\n實際收則欄位僅有：{error_columns}"
            else:
                return pd.DataFrame(), "API 伺服器回傳成功，但裡面「沒有任何資料」。(可能當日台股未開盤，或該日期太久遠)"
        else:
            error_msg = data.get("msg", "未知錯誤")
            return pd.DataFrame(), f"遭 API 伺服器拒絕！錯誤代碼: {data.get('status')}，原因: {error_msg}"
            
    except Exception as e:
        return pd.DataFrame(), f"網路連線異常: {str(e)}"

# ==========================================
# 🎛️ 控制面板：側邊欄設定
# ==========================================
with st.sidebar:
    st.header("🎯 狙擊參數設定")
    stock_input = st.text_input("股票代號 (如: 2330)", value="2330")
    
    # 預設日期設定為昨天
    default_date = datetime.date.today() - datetime.timedelta(days=1)
    date_input = st.date_input("回測日期", value=default_date)
    
    st.markdown("---")
    st.header("🔑 權限設定")
    token_input = st.text_input(
        "FinMind Token (選填)", 
        value="", 
        type="password",
        help="輸入你的 FinMind Token 以突破免費版流量限制。若已配置環境變數則可留空。"
    )
    
    st.markdown("---")
    st.header("⏩ 重播速度設定")
    speed = st.slider("每筆更新間隔 (秒)", min_value=0.01, max_value=2.0, value=0.1, step=0.05)
    
    start_btn = st.button("🚀 啟動時光機", use_container_width=True)

# ==========================================
# 📺 戰術儀表板：動態渲染區塊
# ==========================================
if start_btn:
    date_str = date_input.strftime("%Y-%m-%d")
    with st.spinner(f"正在調閱 {stock_input} 於 {date_str} 的逐筆資料..."):
        df, status_msg = fetch_tick_data(stock_input, date_str, token_input)
        
    if df.empty:
        st.error(f"⚠️ 雷達掃描失敗！\n\n系統診斷報告：{status_msg}")
    else:
        st.success(f"✅ 數據載入完成！總計 {len(df)} 筆成交紀錄，準備開始重播...")
        
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("📈 即時走勢圖")
            chart_placeholder = st.empty()
        with col2:
            st.subheader("📝 逐筆明細")
            table_placeholder = st.empty()

        replay_data = pd.DataFrame(columns=df.columns)
        
        for i in range(len(df)):
            current_tick = df.iloc[[i]]
            replay_data = pd.concat([replay_data, current_tick], ignore_index=True)
            
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=replay_data['時間'], 
                y=replay_data['成交價'], 
                mode='lines', 
                name='成交價',
                line=dict(color='#00BFFF', width=2)
            ))
            y_min = replay_data['成交價'].min() * 0.995
            y_max = replay_data['成交價'].max() * 1.005
            
            fig.update_layout(
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis_title="時間",
                yaxis_title="價格",
                yaxis=dict(tickformat=".2f", range=[y_min, y_max])
            )
            chart_placeholder.plotly_chart(fig, use_container_width=True)
            
            display_table = replay_data.tail(15).iloc[::-1]
            table_placeholder.dataframe(display_table, use_container_width=True, hide_index=True)
            
            time.sleep(speed)
