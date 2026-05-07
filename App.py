import streamlit as st
import yfinance as yf
import pandas as pd
import requests
import urllib.parse
from datetime import datetime, timedelta

# ==========================================
# 🔑 在此設定你的 FinMind VIP Token
# ==========================================
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiaWFubGluIiwiZW1haWwiOiJpYW5saW4yMDA0MDcxN0BnbWFpbC5jb20iLCJ0b2tlbl92ZXJzaW9uIjowfQ.G5jm2LKIg3BaZUIt7SIpqS1V1eZwzZg4ojuK2Naq2-8" 

# 設定網頁標題與圖示
st.set_page_config(page_title="台股處置預警雷達", layout="wide")

# ==========================================
# 🎨 自訂 CSS (打造高級深色卡片介面)
# ==========================================
st.markdown("""
<style>
    .card-container { background-color: #262730; border-radius: 10px; padding: 20px; margin-bottom: 15px; border: 1px solid #333; }
    .metric-label { color: #a0a0a5; font-size: 14px; margin-bottom: 5px; }
    .metric-value { color: #ffffff; font-size: 24px; font-weight: 600; }
    .metric-sub { font-size: 14px; }
    .tag { display: inline-block; padding: 4px 10px; border: 1px solid #555; border-radius: 4px; font-size: 12px; color: #ccc; margin-left: 6px; }
    .tag-yellow { background-color: #f5c518; color: #000; border: none; font-weight: bold; }
    .red-text { color: #ff4b4b; }
    .green-text { color: #00ff00; }
    .title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 20px; }
    .title-text { font-size: 32px; font-weight: bold; color: #fff; }
</style>
""", unsafe_allow_html=True)

@st.cache_data(ttl=86400)
def get_stock_dict():
    """獲取全市場代碼、名稱與產業類別"""
    mapping = {}
    try:
        url = "https://api.finmindtrade.com/api/v4/data?dataset=TaiwanStockInfo"
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            for item in res.json().get('data', []):
                code = item.get('stock_id', '')
                name = item.get('stock_name', '')
                market = item.get('type', '')
                industry = item.get('industry_category', '一般業')
                if len(code) == 4 and code.isdigit():
                    suffix = ".TW" if market == 'twse' else ".TWO"
                    market_name = "上市" if market == 'twse' else "上櫃"
                    mapping[f"{code} {name}"] = {"ticker": f"{code}{suffix}", "market_name": market_name, "industry": industry}
    except: pass
    return mapping

def extract_match_time(text):
    if "二十分" in text or "20分" in text: return "🛑 20分鐘撮合"
    elif "五分" in text or "5分" in text: return "⚠️ 5分鐘撮合"
    elif "十分" in text or "10分" in text: return "⚠️ 10分鐘撮合"
    else: return "🔍 特殊人工撮合"

def extract_match_time_short(text):
    if "二十分" in text or "20分" in text: return "20分盤"
    elif "五分" in text or "5分" in text: return "5分盤"
    elif "十分" in text or "10分" in text: return "10分盤"
    else: return "人工盤"

def fetch_with_proxy(url):
    """🛡️ 防彈機制：強制繞過政府雲端封鎖"""
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
def get_combined_disposal_list(token):
    """雙引擎：同時抓取官方即時與 FinMind 資料，確保不漏接"""
    disposal_dict = {}
    
    # 引擎 1：官方即時 Proxy (補足 FinMind 的時間差)
    tse_data = fetch_with_proxy("https://www.twse.com.tw/announcement/punish?response=json")
    if tse_data and 'data' in tse_data:
        for item in tse_data['data']:
            if len(item) >= 9:
                code = item[2].replace('*', '')
                measure_text = f"{item[7]}：\n{item[8]}"
                disposal_dict[code] = {'period': item[6], 'measure': measure_text, 'match_time': extract_match_time(measure_text), 'match_time_short': extract_match_time_short(measure_text)}
                
    otc_data = fetch_with_proxy("https://www.tpex.org.tw/openapi/v1/tpex_disposal_information")
    if otc_data and isinstance(otc_data, list):
        for item in otc_data:
            code = item.get('SecuritiesCompanyCode', '').replace('*', '')
            if code:
                measure_text = item.get('PunishmentMeasure', '')
                if item.get('PunishmentContent'): measure_text += f"：\n{item.get('PunishmentContent')}"
                disposal_dict[code] = {'period': item.get('PunishmentPeriod', '未知期間'), 'measure': measure_text, 'match_time': extract_match_time(measure_text), 'match_time_short': extract_match_time_short(measure_text)}

    # 引擎 2：FinMind VIP (最穩定歷史備份)
    if token and token != "YOUR_FINMIND_TOKEN_HERE":
        try:
            today_str = datetime.now().strftime("%Y-%m-%d")
            start_str = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
            url = "https://api.finmindtrade.com/api/v4/data"
            params = {"dataset": "TaiwanStockDispositionSecuritiesPeriod", "start_date": start_str, "end_date": today_str, "token": token}
            res = requests.get(url, params=params, timeout=5)
            data = res.json()
            if data.get("msg") == "success":
                df = pd.DataFrame(data["data"])
                if not df.empty:
                    df['period_end_dt'] = pd.to_datetime(df['period_end'])
                    active_df = df[df['period_end_dt'] >= pd.Timestamp.today().normalize()]
                    for _, row in active_df.iterrows():
                        code = str(row['stock_id']).replace('*', '')
                        if code not in disposal_dict:
                            measure_text = str(row['measure'])
                            disposal_dict[code] = {
                                'period': f"{row['period_start']} ~ {row['period_end']}", 'measure': measure_text,
                                'match_time': extract_match_time(measure_text), 'match_time_short': extract_match_time_short(measure_text)
                            }
        except: pass
        
    return disposal_dict

@st.cache_data(ttl=3600)
def get_historical_records(pure_code, is_twse, token):
    """完美抓取歷史紀錄 (使用 Proxy 突破雲端封鎖)"""
    attn_records, disp_records = [], []
    
    if is_twse:
        # 上市：必須使用 Proxy 防擋
        url_notice = f"https://www.twse.com.tw/announcement/notice?response=json&stockNo={pure_code}"
        notice_data = fetch_with_proxy(url_notice)
        if notice_data and 'data' in notice_data:
            for item in notice_data['data']: attn_records.append({"日期": item[0], "原因": item[3]})

        url_punish = f"https://www.twse.com.tw/announcement/punish?response=json&stockNo={pure_code}"
        punish_data = fetch_with_proxy(url_punish)
        if punish_data and 'data' in punish_data:
            for item in punish_data['data']: disp_records.append({"處置期間": item[6], "處置內容": item[7]})
            
    # 處置紀錄：用 FinMind 補足 (支援上市與上櫃)
    if token and token != "YOUR_FINMIND_TOKEN_HERE":
        try:
            url = "https://api.finmindtrade.com/api/v4/data"
            params = {"dataset": "TaiwanStockDispositionSecuritiesPeriod", "start_date": (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"), "end_date": datetime.now().strftime("%Y-%m-%d"), "data_id": pure_code, "token": token}
            res = requests.get(url, params=params, timeout=5)
            data = res.json()
            if data.get("msg") == "success" and data.get("data"):
                for item in data["data"]:
                    if str(item['stock_id']).replace('*', '') == pure_code:
                        period_str = f"{item['period_start']} ~ {item['period_end']}"
                        if not any(d.get("處置期間") == period_str for d in disp_records):
                            disp_records.append({"處置期間": period_str, "處置內容": item['measure']})
        except: pass
        
    if not is_twse:
        attn_records = [{"日期": "系統提示", "原因": "上櫃股票歷史注意紀錄目前不支援單一 API 查詢，請點擊連結前往官方查詢。"}]

    return pd.DataFrame(attn_records), pd.DataFrame(disp_records)

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

# --- UI 介面開始 ---
stock_dict = get_stock_dict()
official_disposal = get_combined_disposal_list(FINMIND_TOKEN)

# 頂部搜尋列
if not stock_dict:
    search_input = st.text_input("請輸入股票代碼", "2454")
    ticker_info = {"ticker": f"{search_input}.TW", "market_name": "上市櫃", "industry": "未知"}
    pure_code = search_input
    stock_name = search_input
else:
    search = st.selectbox("🔍 搜尋股票", options=list(stock_dict.keys()), index=list(stock_dict.keys()).index("2454 聯發科") if "2454 聯發科" in stock_dict else 0)
    ticker_info = stock_dict[search]
    pure_code = search.split()[0].replace('*', '') # 嚴格濾除星號
    stock_name = search.split()[1] if len(search.split()) > 1 else pure_code

is_twse = ticker_info['market_name'] == "上市"
clean_ticker = ticker_info['ticker']
is_disposal_now = pure_code in official_disposal

# 🚀 強制消滅 NaN：抓取價量並嚴格清洗
df = pd.DataFrame()
try:
    df = yf.download(clean_ticker, period="120d", progress=False)
except: pass

today_close, yesterday_close, volume = 0, 0, 0
price_change, price_pct = 0, 0
color_class = ""

if not df.empty and 'Close' in df:
    # 嚴格拋棄所有包含 NaN 的無效日期
    df = df.dropna(subset=['Close', 'Volume'])
    if len(df) >= 2:
        closes = df['Close'].iloc[:, 0] if isinstance(df['Close'], pd.DataFrame) else df['Close']
        vols = df['Volume'].iloc[:, 0] if isinstance(df['Volume'], pd.DataFrame) else df['Volume']
        today_close = closes.iloc[-1]
        yesterday_close = closes.iloc[-2]
        volume = vols.iloc[-1]
        price_change = today_close - yesterday_close
        price_pct = (price_change / yesterday_close) * 100
        color_class = "red-text" if price_change > 0 else "green-text" if price_change < 0 else ""

# 組合右上角標籤
tags_html = f'<div class="tag">{ticker_info["market_name"]}</div><div class="tag">{ticker_info["industry"]}</div>'
if is_disposal_now:
    tags_html += f'<div class="tag tag-yellow">{official_disposal[pure_code]["match_time_short"]}</div>'
tags_html += '<div class="tag">資</div><div class="tag">券</div><div class="tag">沖</div>'

# 繪製頭部標題區塊
st.markdown(f"""
<div class="title-row">
    <div class="title-text">{stock_name} — {pure_code} 處置風險與籌碼分析</div>
    <div>{tags_html}</div>
</div>
""", unsafe_allow_html=True)

# ==========================================
# 📊 兩大核心看板：報價區 & 風險天數區
# ==========================================
top_col1, top_col2 = st.columns(2)

with top_col1:
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    if is_disposal_now:
        st.markdown(f'<div class="tag tag-yellow" style="margin-bottom:10px;">本日處置中</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="tag" style="margin-bottom:10px; background:#444;">正常交易</div>', unsafe_allow_html=True)
        
    st.markdown(f'<div class="metric-value {color_class}" style="font-size:36px;">{today_close:.2f}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="metric-sub {color_class}">{"▲" if price_change>0 else "▼" if price_change<0 else ""} {abs(price_change):.2f} ({price_pct:+.2f}%)</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

with top_col2:
    st.markdown('<div class="card-container">', unsafe_allow_html=True)
    st.markdown('<div class="metric-label">風險天數分析</div>', unsafe_allow_html=True)
    
    if is_disposal_now:
        period = official_disposal[pure_code]['period']
        st.markdown(f'<div class="metric-value">處置期間：{period}</div>', unsafe_allow_html=True)
        st.progress(100) # 顯示全滿代表正在處置
    elif 'closes' in locals() and len(closes) >= 90:
        history_prices = closes.tolist()
        current_consecutive = 0
        test_list = history_prices.copy()
        for _ in range(5):
            if check_attention(test_list):
                current_consecutive += 1; test_list.pop()
            else: break
            
        days_up, price_up = simulate_future(history_prices, current_consecutive, direction='up')
        
        if days_up:
            st.markdown(f'<div class="metric-value">🔥 最快 {days_up} 日後再次處置</div>', unsafe_allow_html=True)
            risk_pct = max(0, min(100, 100 - (days_up * 33))) 
            st.progress(int(risk_pct))
            st.caption(f"預估漲停觸發價：{price_up:.2f} | 目前連 {current_consecutive} 日注意")
        else:
            st.markdown(f'<div class="metric-value">✅ 近期無處置風險</div>', unsafe_allow_html=True)
            st.progress(0)
    else:
        st.markdown(f'<div class="metric-value">資料不足無法運算</div>', unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

# ==========================================
# 📊 九宮格籌碼與數據區 (UI 框架)
# ==========================================
col_a, col_b, col_c, col_d = st.columns(4)

def metric_card(col, label, value, color="white"):
    col.markdown(f"""
    <div class="card-container" style="padding: 15px;">
        <div class="metric-label">{label}</div>
        <div class="metric-value" style="color:{color}; font-size:20px;">{value}</div>
    </div>
    """, unsafe_allow_html=True)

metric_card(col_a, "成交張數", f"{volume/1000:.1f} 萬張" if volume > 0 else "N/A")
metric_card(col_b, "預估成交值", f"{(volume * today_close)/100000000:.1f} 億" if volume > 0 else "N/A")
metric_card(col_c, "週轉率", "N/A")
metric_card(col_d, "券資比", "N/A")

metric_card(col_a, "當沖率", "N/A", color="#f5c518")
metric_card(col_b, "當沖獲利", "N/A")
metric_card(col_c, "當沖獲利率", "N/A")
metric_card(col_d, "當沖成交量", "N/A")

metric_card(col_a, "三大法人買賣超", "N/A")
metric_card(col_b, "外資買賣", "N/A")
metric_card(col_c, "投信買賣", "N/A")
metric_card(col_d, "自營商買賣", "N/A")

# ==========================================
# 📜 歷史查詢模組 (完整表格展開)
# ==========================================
st.markdown("<br><h5>想查詢注意股或處置股歷史公告？</h5>", unsafe_allow_html=True)
df_attn, df_disp = get_historical_records(pure_code, is_twse, FINMIND_TOKEN)

hist_col1, hist_col2 = st.columns(2)
with hist_col1:
    attn_count = 0 if '系統提示' in df_attn.values else len(df_attn)
    with st.expander(f"📜 歷史【注意股】紀錄 (共 {attn_count} 次)"):
        if not df_attn.empty: st.dataframe(df_attn, hide_index=True, use_container_width=True)
        else: st.write("近期無紀錄。")
        if not is_twse: st.link_button("前往櫃買官方查詢", "https://www.tpex.org.tw/web/bulletin/notice/notice_result.php?l=zh-tw")
            
with hist_col2:
    with st.expander(f"🛑 歷史【處置股】紀錄 (共 {len(df_disp)} 次)"):
        if not df_disp.empty: st.dataframe(df_disp, hide_index=True, use_container_width=True)
        else: st.write("近期無紀錄。")
