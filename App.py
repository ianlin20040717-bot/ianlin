import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# ==========================================
# 🔑 FinMind VIP Token 設定
# ==========================================
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiaWFubGluIiwiZW1haWwiOiJpYW5saW4yMDA0MDcxN0BnbWFpbC5jb20iLCJ0b2tlbl92ZXJzaW9uIjowfQ.G5jm2LKIg3BaZUIt7SIpqS1V1eZwzZg4ojuK2Naq2-8"

st.set_page_config(page_title="台股處置預警雷達 (全官方數據版)", layout="wide")

# ==========================================
# 🎨 專業版自訂 CSS (結合漲跌停底色與橫幅)
# ==========================================
st.markdown("""
<style>
    .top-card { 
        background-color: #1e1e26; border-radius: 12px; padding: 20px 25px; 
        margin-bottom: 15px; border: 1px solid #333; 
        box-shadow: 2px 2px 10px rgba(0,0,0,0.3); 
        height: 140px; 
        display: flex; flex-direction: column; justify-content: center;
    }
    .metric-card { 
        background-color: #1e1e26; border-radius: 12px; padding: 15px 20px; 
        margin-bottom: 15px; border: 1px solid #333; 
        box-shadow: 2px 2px 10px rgba(0,0,0,0.3); 
        height: 120px; 
        display: flex; flex-direction: column; justify-content: center;
    }
    
    .metric-label { color: #88888e; font-size: 14px; margin-bottom: 8px; font-weight: 500;}
    .metric-value { color: #ffffff; font-size: 26px; font-weight: 700; line-height: 1.2;}
    .metric-sub { font-size: 13px; font-weight: 500; margin-top: 6px; color: #888; }
    
    .price-value { font-size: 38px; font-weight: 800; line-height: 1.2; margin-bottom: 4px;}
    .limit-up { background-color: #ff4b4b; color: #ffffff !important; padding: 2px 10px; border-radius: 6px; display: inline-block; }
    .limit-down { background-color: #00ff00; color: #000000 !important; padding: 2px 10px; border-radius: 6px; display: inline-block; }
    
    .notice-banner {
        border: 1px solid #5a4b1c;
        border-radius: 10px;
        background-color: #1f1b10;
        padding: 20px 25px;
        margin-bottom: 20px;
        box-shadow: 0px 4px 12px rgba(255, 193, 7, 0.1);
    }
    .notice-banner-header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #443c24; padding-bottom: 12px; margin-bottom: 12px; }
    .notice-banner-title { color: #ffc107; font-size: 22px; font-weight: 800; display: flex; align-items: center; gap: 8px;}
    .notice-banner-date { color: #aaaaaa; font-size: 16px; font-weight: 600;}
    .notice-banner-content { color: #e0e0e0; font-size: 16px; line-height: 1.6; font-weight: 500;}
    
    .tags-container { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; justify-content: flex-end; height: 100%; padding-bottom: 5px; }
    .tag-base { padding: 4px 12px; border-radius: 4px; font-size: 13px; font-weight: 600; border: 1px solid #444; }
    .t-market { background-color: #2e2e38; color: #ddd; }
    .t-warn { background-color: #ffc107; color: #000; border: none; font-size: 14px; }
    .t-on { background-color: #3b3b4f; color: #fff; border-color: #666; }
    .t-off { background-color: #1a1a21; color: #555; border-color: #333; }
    
    .red-text { color: #ff4b4b !important; }
    .green-text { color: #00ff00 !important; }
    .title-text { font-size: 32px; font-weight: 800; color: #fff; margin-bottom: 25px; }
    
    .openapi-badge { background-color: #0056b3; color: white; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; margin-bottom: 8px; display: inline-block; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 📡 資料抓取模組 (FinMind + 上市櫃官方 OpenAPI)
# ==========================================
def api_request(dataset, data_id=None, start=None, token=FINMIND_TOKEN):
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {"dataset": dataset, "token": token}
    if data_id: 
        params["data_id"] = data_id
        params["stock_id"] = data_id
    if start: params["start_date"] = start
    try:
        res = requests.get(url, params=params, timeout=10).json()
        if 'data' in res and isinstance(res['data'], list):
            return pd.DataFrame(res['data'])
    except: 
        pass
    return pd.DataFrame()

@st.cache_data(ttl=600)
def fetch_official_status(sid, is_twse):
    """🏛️ 自動判斷上市櫃，串接官方 OpenAPI 取得即時處置/注意公告"""
    notice_data, disp_data = [], []
    sid_str = str(sid).strip()
    
    try:
        if is_twse:
            # TWSE 上市 API
            res_n = requests.get("https://openapi.twse.com.tw/v1/announcement/notice", timeout=5).json()
            for item in res_n:
                if str(item.get("Code", "")).strip() == sid_str: notice_data.append(item)
            
            res_d = requests.get("https://openapi.twse.com.tw/v1/announcement/disposition", timeout=5).json()
            for item in res_d:
                if str(item.get("Code", "")).strip() == sid_str: disp_data.append(item)
        else:
            # TPEx 上櫃 API
            res_n = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_notice_securities", timeout=5).json()
            for item in res_n:
                if str(item.get("SecCode", "")).strip() == sid_str or str(item.get("Code", "")).strip() == sid_str: 
                    notice_data.append(item)
                    
            res_d = requests.get("https://www.tpex.org.tw/openapi/v1/tpex_disposition_securities", timeout=5).json()
            for item in res_d:
                if str(item.get("SecCode", "")).strip() == sid_str or str(item.get("Code", "")).strip() == sid_str: 
                    disp_data.append(item)
    except: 
        pass
        
    return notice_data, disp_data

@st.cache_data(ttl=86400)
def get_all_info():
    df = api_request("TaiwanStockInfo")
    mapping = {}
    if not df.empty:
        for _, r in df.iterrows():
            code = str(r['stock_id']).strip()
            if len(code) == 4 and code.isdigit():
                mapping[f"{code} {r['stock_name']}"] = {"id": code, "market": r['type'], "industry": r['industry_category']}
    return mapping

@st.cache_data(ttl=86400)
def get_outstanding_shares(sid):
    start_date = (datetime.now() - timedelta(days=400)).strftime("%Y-%m-%d")
    df = api_request("TaiwanStockBalanceSheet", sid, start_date)
    if not df.empty and 'type' in df.columns and 'value' in df.columns:
        mask = df['type'].str.contains('普通股股本|股本', na=False)
        if any(mask):
            latest_capital = df[mask].sort_values('date').iloc[-1]['value']
            return int((latest_capital / 10) / 1000)
    return 0

def extract_match_type(measure):
    m = str(measure)
    if any(k in m for k in ["九十分", "90分"]): return "90分盤"
    if any(k in m for k in ["六十分", "60分"]): return "60分盤"
    if any(k in m for k in ["四十五分", "45分"]): return "45分盤"
    if any(k in m for k in ["二十五分", "25分"]): return "25分盤"
    if any(k in m for k in ["二十分", "20分"]): return "20分盤"
    if any(k in m for k in ["十分", "10分"]): return "10分盤"
    if any(k in m for k in ["五分", "5分"]): return "5分盤"
    if "第五次" in m: return "90分盤"
    if "第四次" in m: return "60分盤"
    if "第三次" in m: return "45分盤"
    if "第二次" in m: return "20分盤"
    if "第一次" in m: return "5分盤"
    return "5分盤"

# ==========================================
# 📊 UI 渲染開始
# ==========================================
stock_list = get_all_info()
if not stock_list:
    st.error("正在連線 FinMind 或 Token 無效，請確認網路與設定。")
    st.stop()

top_col1, top_col2 = st.columns([1, 1], gap="medium")

with top_col1:
    search = st.selectbox("🔍 搜尋標的", options=list(stock_list.keys()), index=list(stock_list.keys()).index("5425 台半") if "5425 台半" in stock_list else 0)

info = stock_list[search]
sid = info['id']
is_twse = (info['market'] == 'twse' or info['market'] == '上市')

start_str = (datetime.now() - timedelta(days=200)).strftime("%Y-%m-%d")
safe_start_str = (datetime.now() - timedelta(days=20)).strftime("%Y-%m-%d") 

with st.spinner("🚀 正在向證交所/櫃買中心官方伺服器請求即時公告..."):
    df_price = api_request("TaiwanStockPrice", sid, start_str)
    df_inst = api_request("TaiwanStockInstitutionalInvestorsBuySell", sid, safe_start_str)
    df_margin = api_request("TaiwanStockMarginPurchaseShortSale", sid, safe_start_str)
    df_day = api_request("TaiwanStockDayTrading", sid, start_str)
    df_disp = api_request("TaiwanStockDispositionSecuritiesPeriod", start=(datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"))
    
    # 呼叫官方 API
    official_notice, official_disp = fetch_official_status(sid, is_twse)
    
    total_sheets = get_outstanding_shares(sid)
    if total_sheets == 0 and not df_margin.empty and 'MarginPurchaseLimit' in df_margin.columns:
        limit = df_margin['MarginPurchaseLimit'].max()
        if pd.notna(limit) and limit > 0:
            total_sheets = int((limit * 4) / 1000 if limit >= 1000000 else (limit * 4))

is_punished_finmind = False
disp_info = {}
if not df_disp.empty and 'period_end' in df_disp.columns:
    df_disp['stock_id'] = df_disp['stock_id'].astype(str).str.strip() 
    df_disp['period_end_dt'] = pd.to_datetime(df_disp['period_end'])
    active_disp = df_disp[(df_disp['stock_id'] == sid) & (df_disp['period_end_dt'] >= pd.Timestamp.today().normalize())]
    if not active_disp.empty:
        is_punished_finmind = True
        latest = active_disp.sort_values('period_end_dt').iloc[-1]
        disp_info = {
            "period": f"{latest['period_start']} ~ {latest['period_end']}", 
            "measure": latest['measure'], 
            "match": extract_match_type(latest['measure']) 
        }

if not df_price.empty:
    df_price['date'] = pd.to_datetime(df_price['date'])
    df_price = df_price.set_index('date').sort_index()
    closes = df_price['close']
    vols = df_price['Trading_Volume']
    p_now = closes.iloc[-1]
    p_prev = closes.iloc[-2] if len(closes) > 1 else p_now
    diff = p_now - p_prev
    pct = (diff / p_prev) * 100 if p_prev > 0 else 0
    today_vol = vols.iloc[-1]
    price_date_str = pd.to_datetime(df_price.index[-1]).strftime('%m/%d')
    price_date_str_full = pd.to_datetime(df_price.index[-1]).strftime('%Y-%m-%d')
    
    is_limit_up = pct >= 9.5
    is_limit_down = pct <= -9.5
    if is_limit_up:
        c_class = "limit-up"
        arrow_sub_class = "white-text" 
    elif is_limit_down:
        c_class = "limit-down"
        arrow_sub_class = "black-text"
    else:
        c_class = "red-text" if diff > 0 else "green-text" if diff < 0 else ""
        arrow_sub_class = c_class
else:
    p_now, today_vol, price_date_str, price_date_str_full = 0, 0, "", ""
    c_class, arrow_sub_class = "", ""

# ==========================================
# 🚀 頂部標籤與橫幅渲染
# ==========================================
market_name = "上市" if is_twse else "上櫃"
can_margin = df_margin['MarginPurchaseLimit'].max() > 0 if not df_margin.empty and 'MarginPurchaseLimit' in df_margin.columns else False
can_short = df_margin['ShortSaleLimit'].max() > 0 if not df_margin.empty and 'ShortSaleLimit' in df_margin.columns else False

if not df_day.empty:
    vol_cols = [c for c in df_day.columns if 'volume' in c.lower() or 'lots' in c.lower()]
    if vol_cols:
        history_can_day = df_day[vol_cols[0]].max() > 0
    else:
        valid_cols = [c for c in df_day.columns if c not in ['date', 'stock_id']]
        history_can_day = df_day[valid_cols[0]].max() > 0 if valid_cols else True
else:
    history_can_day = False

is_day_trade_eligible = can_margin or can_short or history_can_day

tag_margin = "t-on" if can_margin else "t-off"
tag_short = "t-on" if can_short else "t-off"
tag_day = "t-on" if is_day_trade_eligible and not is_punished_finmind else "t-off" 

large_caps = ['2330', '2454', '2317', '2603', '3231', '3481', '2382', '2881', '2891', '2609', '2615', '3008', '2303', '1101']
tag_future = "t-on" if sid in large_caps or today_vol > 10000000 else "t-off"
tag_warrant = "t-on" if sid in large_caps or today_vol > 3000000 else "t-off"

with top_col2:
    tags_html = '<div class="tags-container">'
    tags_html += f'<span class="tag-base t-market">{market_name}</span>'
    tags_html += f'<span class="tag-base t-market">{info["industry"]}</span>'
    if is_punished_finmind or official_disp: 
        tags_html += f'<span class="tag-base t-warn">處置中</span>'
    tags_html += f'<span class="tag-base {tag_margin}">資</span>'
    tags_html += f'<span class="tag-base {tag_short}">券</span>'
    tags_html += f'<span class="tag-base {tag_day}">沖</span>'
    tags_html += f'<span class="tag-base {tag_future}">期</span>'
    tags_html += f'<span class="tag-base {tag_warrant}">權</span>'
    tags_html += '</div>'
    st.markdown(tags_html, unsafe_allow_html=True)

st.markdown(f'<div class="title-text">{search} 盤後籌碼與風險分析</div>', unsafe_allow_html=True)

# 🔥 動態公告橫幅 (100% 來自官方 API)
if official_notice:
    latest_detail = official_notice[0].get("Detail", "")
    banner_html = f"""
    <div class="notice-banner">
        <div class="notice-banner-header">
            <div class="notice-banner-title">⚠️ 官方注意交易資訊公告</div>
            <div class="notice-banner-date">{price_date_str_full.replace('-', '/')}</div>
        </div>
        <div class="notice-banner-content">
            {latest_detail.replace(' ', '<br>')}
        </div>
    </div>
    """
    st.markdown(banner_html, unsafe_allow_html=True)

if not df_price.empty:
    c1, c2 = st.columns([1, 1], gap="medium")
    with c1:
        p_html = (
            '<div class="top-card">'
            '<div class="metric-label">收盤價</div>'
            f'<div class="price-value {c_class}">{p_now:.2f}</div>'
            f'<div class="metric-sub {arrow_sub_class}">{"▲" if diff>0 else "▼" if diff<0 else ""} {abs(diff):.2f} ({pct:+.2f}%)</div>'
            '</div>'
        )
        st.markdown(p_html, unsafe_allow_html=True)
        
    with c2:
        # 右側看板改為「官方狀態公告」，不再做本地模擬預測
        if official_disp or is_punished_finmind:
            disp_desc = disp_info["match"] if is_punished_finmind else "官方處置中"
            disp_period = disp_info["period"] if is_punished_finmind else "詳見下方官方公告"
            html_content = (
                '<div class="top-card">'
                '<div class="metric-label">官方狀態指示</div>'
                f'<div class="metric-value" style="color:#ffc107;">🚨 已在處置中 ({disp_desc})</div>'
                f'<div class="metric-sub">處置期間：{disp_period}</div>'
                '<div style="width:100%; background-color:#333; border-radius:5px; margin-top:12px;">'
                '<div style="width:100%; background-color:#ffc107; height:6px; border-radius:5px;"></div>'
                '</div></div>'
            )
            st.markdown(html_content, unsafe_allow_html=True)
        elif official_notice:
            html_content = (
                '<div class="top-card">'
                '<div class="metric-label">官方狀態指示</div>'
                f'<div class="metric-value" style="color:#ffc107;">⚠️ 本日為注意股</div>'
                f'<div class="metric-sub">因價量異常觸發官方注意機制，請留意流動性風險</div>'
                '<div style="width:100%; background-color:#333; border-radius:5px; margin-top:12px;">'
                f'<div style="width:60%; background-color:#ffc107; height:6px; border-radius:5px;"></div>'
                '</div></div>'
            )
            st.markdown(html_content, unsafe_allow_html=True)
        else:
            html_content = (
                '<div class="top-card">'
                '<div class="metric-label">官方狀態指示</div>'
                '<div class="metric-value" style="color:#00ff00;">✅ 正常交易狀態</div>'
                f'<div class="metric-sub">今日無任何處置或注意通報，籌碼流動性正常</div>'
                '<div style="width:100%; background-color:#333; border-radius:5px; margin-top:12px;">'
                '<div style="width:0%; background-color:#00ff00; height:6px; border-radius:5px;"></div>'
                '</div></div>'
            )
            st.markdown(html_content, unsafe_allow_html=True)

    def m_card(c, l, v, clr="white", sub=""):
        card_html = (
            '<div class="metric-card">'
            f'<div class="metric-label">{l}</div>'
            f'<div class="metric-value" style="color:{clr};">{v}</div>'
            f'<div class="metric-sub">{sub}</div>'
            '</div>'
        )
        c.markdown(card_html, unsafe_allow_html=True)

    col_r1 = st.columns(4, gap="medium")
    vol_lots = today_vol / 1000 
    turnover = (vol_lots / total_sheets * 100) if total_sheets > 0 else 0
    short_ratio, margin_date_sub = 0, ""
    if not df_margin.empty and 'MarginPurchaseTodayBalance' in df_margin.columns:
        last_margin_row = df_margin.iloc[-1]
        margin_date_sub = f"({pd.to_datetime(last_margin_row['date']).strftime('%m/%d')})"
        margin_bal = last_margin_row['MarginPurchaseTodayBalance']
        short_bal = last_margin_row.get('ShortSaleTodayBalance', 0)
        short_ratio = (short_bal / margin_bal * 100) if margin_bal > 0 else 0

    m_card(col_r1[0], "成交張數", f"{vol_lots:,.0f} 張", sub=f"({price_date_str})")
    m_card(col_r1[1], "成交金額", f"{(p_now * today_vol)/100000000:.1f} 億", sub=f"({price_date_str})")
    m_card(col_r1[2], "週轉率", f"{turnover:.2f}%", sub="佔發行總張數")
    m_card(col_r1[3], "券資比", f"{short_ratio:.1f}%", sub=margin_date_sub)

    col_r2 = st.columns(4, gap="medium")
    day_pct, day_vol_lots, day_date_sub = 0, 0, ""
    if not df_day.empty:
        day_vol_cols = [c for c in df_day.columns if 'volume' in c.lower() or 'lots' in c.lower()]
        day_pct_cols = [c for c in df_day.columns if 'percent' in c.lower() or 'ratio' in c.lower()]
        last_day_row = df_day.iloc[-1]
        day_date_sub = f"({pd.to_datetime(last_day_row['date']).strftime('%m/%d')})"
        day_trade_vol = last_day_row[day_vol_cols[0]] if day_vol_cols else 0
        day_vol_lots = day_trade_vol / 1000 if day_trade_vol > 100 else day_trade_vol
        if day_pct_cols:
            day_pct = last_day_row[day_pct_cols[0]]
            if day_pct < 1: day_pct *= 100
        else:
            match_price = df_price[df_price.index == pd.to_datetime(last_day_row['date'])]
            match_vol = match_price['Trading_Volume'].iloc[0] if not match_price.empty else 0
            day_pct = (day_trade_vol / match_vol) * 100 if match_vol > 0 else 0

    m_card(col_r2[0], "當沖率", f"{day_pct:.1f}%", clr="#f5c518", sub=day_date_sub)
    m_card(col_r2[1], "當沖獲利", "N/A", clr="#555")       
    m_card(col_r2[2], "當沖獲利率", "N/A", clr="#555")     
    m_card(col_r2[3], "當沖成交張數", f"{day_vol_lots:,.0f} 張", sub=day_date_sub)

    col_r3 = st.columns(4, gap="medium")
    f_amt, t_amt, d_amt, total_amt = 0, 0, 0, 0
    inst_date_sub = ""
    if not df_inst.empty:
        last_inst_date = df_inst['date'].max()
        inst_date_sub = f"({pd.to_datetime(last_inst_date).strftime('%m/%d')})"
        daily_inst = df_inst[df_inst['date'] == last_inst_date]
        inst_net = daily_inst.groupby('name')['buy'].sum() - daily_inst.groupby('name')['sell'].sum()
        
        match_price = df_price[df_price.index == pd.to_datetime(last_inst_date)]
        target_price = match_price['close'].iloc[0] if not match_price.empty else p_now
        
        f_shares = inst_net.get('Foreign_Investor', 0) + inst_net.get('Foreign_Dealer_Self', 0)
        t_shares = inst_net.get('Investment_Trust', 0)
        d_shares = inst_net.get('Dealer_self', 0) + inst_net.get('Dealer_Hedging', 0)
        
        f_amt = f_shares * target_price
        t_amt = t_shares * target_price
        d_amt = d_shares * target_price
        total_amt = f_amt + t_amt + d_amt

    def format_inst_amt(val):
        if val == 0: return "0", "white"
        sign = "+" if val > 0 else ""
        clr = "#ff4b4b" if val > 0 else "#00ff00" 
        if abs(val) >= 100000000:
            return f"{sign}{val/100000000:.2f} 億", clr
        else:
            return f"{sign}{val/10000:,.0f} 萬", clr

    total_str, total_clr = format_inst_amt(total_amt)
    f_str, f_clr = format_inst_amt(f_amt)
    t_str, t_clr = format_inst_amt(t_amt)
    d_str, d_clr = format_inst_amt(d_amt)

    m_card(col_r3[0], "三大法人淨買賣金額", total_str, clr=total_clr, sub=inst_date_sub)
    m_card(col_r3[1], "外資買賣金額", f_str, clr=f_clr, sub=inst_date_sub)
    m_card(col_r3[2], "投信買賣金額", t_str, clr=t_clr, sub=inst_date_sub)
    m_card(col_r3[3], "自營商買賣金額", d_str, clr=d_clr, sub=inst_date_sub)

    # ==========================================
    # 📜 官方資訊驗證區
    # ==========================================
    st.markdown("---")
    st.markdown("### 🏛️ 官方公告資訊看板")
    h_col1, h_col2 = st.columns(2, gap="medium")
    
    with h_col1:
        with st.expander("🔔 今日證交所 / 櫃買中心即時注意公告", expanded=True):
            if official_notice:
                st.markdown('<div class="openapi-badge">官方 OpenAPI 即時連線</div>', unsafe_allow_html=True)
                # 轉成 DataFrame 並統一欄位名稱
                df_n = pd.DataFrame(official_notice)
                if 'SecCode' in df_n.columns: df_n = df_n.rename(columns={'SecCode': 'Code', 'SecName': 'Name'})
                st.dataframe(df_n[['Code', 'Name', 'Detail']], hide_index=True, use_container_width=True)
            else:
                st.write("✅ 今日無任何官方注意公告。")
                
    with h_col2:
        start_60d = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        h_df = api_request("TaiwanStockDispositionSecuritiesPeriod", sid, start_60d)
        
        with st.expander(f"🛑 歷史處置股紀錄 (FinMind 資料庫, 共 {len(h_df) if not h_df.empty else 0} 次)", expanded=True):
            if official_disp:
                st.markdown('<div class="openapi-badge">官方 OpenAPI 即時連線 (處置中)</div>', unsafe_allow_html=True)
                df_d = pd.DataFrame(official_disp)
                if 'SecCode' in df_d.columns: df_d = df_d.rename(columns={'SecCode': 'Code', 'SecName': 'Name'})
                display_cols = ['Code', 'Name', 'Period', 'Detail'] if 'Period' in df_d.columns else ['Code', 'Name', 'Detail']
                st.dataframe(df_d[display_cols], hide_index=True, use_container_width=True)
                st.markdown("---")
                
            if not h_df.empty:
                h_df['盤別'] = h_df['measure'].apply(extract_match_type)
                h_df = h_df[['period_start', 'period_end', '盤別', 'measure']]
                st.dataframe(h_df.rename(columns={'period_start':'起始日', 'period_end':'結束日', 'measure':'條款與措施'}), hide_index=True, use_container_width=True)
            else: 
                st.write("近 30 交易日內無處置紀錄")

else:
    st.error("查無此標的或歷史報價抓取失敗。")
