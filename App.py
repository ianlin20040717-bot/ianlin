import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# ==========================================
# 🔑 FinMind VIP Token 設定
# ==========================================
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiaWFubGluIiwiZW1haWwiOiJpYW5saW4yMDA0MDcxN0BnbWFpbC5jb20iLCJ0b2tlbl92ZXJzaW9uIjowfQ.G5jm2LKIg3BaZUIt7SIpqS1V1eZwzZg4ojuK2Naq2-8"

st.set_page_config(page_title="台股處置預警雷達 (FinMind 旗艦版)", layout="wide")

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
</style>
""", unsafe_allow_html=True)

# ==========================================
# 📡 資料抓取模組
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

# ==========================================
# 🧠 核心：本地端法規判定引擎 (新增第三款、第四款15%閥值)
# ==========================================
def calculate_local_attention(df_price, df_day, df_taiex, total_sheets, is_twse):
    records = []
    if df_price.empty or len(df_price) < 7:
        return pd.DataFrame()

    day_dict = {}
    if not df_day.empty:
        vol_cols = [c for c in df_day.columns if 'volume' in c.lower() or 'lots' in c.lower()]
        pct_cols = [c for c in df_day.columns if 'percent' in c.lower() or 'ratio' in c.lower()]
        for _, r in df_day.iterrows():
            dt_str = pd.to_datetime(r['date']).strftime('%Y-%m-%d')
            dt_vol = r[vol_cols[0]] if vol_cols else 0
            dt_pct = r[pct_cols[0]] if pct_cols else 0
            if dt_pct < 1 and dt_pct > 0: dt_pct *= 100
            day_dict[dt_str] = {'vol': dt_vol, 'pct': dt_pct}

    taiex_dict = {}
    if not df_taiex.empty:
        df_taiex['date'] = pd.to_datetime(df_taiex['date'])
        for _, r in df_taiex.iterrows():
            dt_str = r['date'].strftime('%Y-%m-%d')
            taiex_dict[dt_str] = r['close']

    # 官方防呆系統：紀錄上一次觸發的 Index (第10、11、13款適用6日冷卻期)
    last_trigger = {
        "rule1": -999,
        "rule10": -999,
        "rule11": -999,
        "rule13": -999
    }

    scan_range = min(30, len(df_price) - 6)
    for i in range(len(df_price) - scan_range, len(df_price)):
        curr_date = df_price.index[i]
        c_close = df_price['close'].iloc[i]
        dt_str_curr = curr_date.strftime('%Y-%m-%d')
        reasons = []

        if i >= 6:
            p_close_6 = df_price['close'].iloc[i-6]
            p_close_5 = df_price['close'].iloc[i-5]
            
            ret_6d_raw = (c_close / p_close_6 - 1) * 100 if p_close_6 > 0 else 0
            diff_5d = c_close - p_close_5
            
            if total_sheets > 0:
                vol_6d_lots = df_price['Trading_Volume'].iloc[i-5:i+1].sum() / 1000
                turnover_6d = (vol_6d_lots / total_sheets * 100) 
                daily_vol_lots = df_price['Trading_Volume'].iloc[i] / 1000
                daily_turnover = (daily_vol_lots / total_sheets * 100)
            else:
                turnover_6d = 0
                daily_turnover = 0

            # --- 第一款：純價格極端異常 ---
            if is_twse:
                dt_str_p6 = df_price.index[i-6].strftime('%Y-%m-%d')
                taiex_c = taiex_dict.get(dt_str_curr, 0)
                taiex_p6 = taiex_dict.get(dt_str_p6, 0)
                taiex_ret_6d = (taiex_c / taiex_p6 - 1) * 100 if taiex_p6 > 0 else 0
                if abs(ret_6d_raw) >= 25 and abs(ret_6d_raw - taiex_ret_6d) >= 20: 
                    if (i - last_trigger["rule1"]) >= 6:
                        word = "漲幅" if ret_6d_raw > 0 else "跌幅"
                        reasons.append(f"最近六個營業日(含當日)累積之最後成交價{word}達{abs(ret_6d_raw):.2f}% (第一款)")
                        last_trigger["rule1"] = i
            else:
                if abs(ret_6d_raw) >= 25 and abs(diff_5d) >= 50:
                    if (i - last_trigger["rule1"]) >= 6:
                        word = "漲幅" if ret_6d_raw > 0 else "跌幅"
                        reasons.append(f"最近六個營業日(含當日)累積之最後成交價{word}達{abs(ret_6d_raw):.2f}%且最近六個營業日(含當日)起迄兩個營業日之最後成交價價差達新臺幣{abs(diff_5d):.1f}元(第一款)")
                        last_trigger["rule1"] = i

            # --- 🔥 第三款：價格 + 成交量異常放大 ---
            if i >= 60:
                avg_vol_60d = df_price['Trading_Volume'].iloc[i-60:i].mean() / 1000
                daily_vol = df_price['Trading_Volume'].iloc[i] / 1000
                vol_ratio = (daily_vol / avg_vol_60d) if avg_vol_60d > 0 else 0
                # 實戰門檻：漲跌幅達25% 且成交量較60日均量放大5倍以上
                if abs(ret_6d_raw) >= 25 and vol_ratio >= 5:
                    word = "漲幅" if ret_6d_raw > 0 else "跌幅"
                    reasons.append(f"最近六個營業日(含當日)累積之最後成交價{word}達{abs(ret_6d_raw):.2f}%，當日之成交量較最近六十個營業日日平均成交量放大{vol_ratio:.2f}倍(第三款)")
            
            # --- 🔥 第四款：價格 + 週轉率 (完美 15% 門檻) ---
            if abs(ret_6d_raw) >= 25 and daily_turnover >= 15:
                word = "漲幅" if ret_6d_raw > 0 else "跌幅"
                reasons.append(f"當日週轉率達{daily_turnover:.1f}%(第四款)" if "第三款" in "".join(reasons) else f"最近六個營業日(含當日)累積之最後成交價{word}達{abs(ret_6d_raw):.2f}%，當日週轉率達{daily_turnover:.1f}%(第四款)")

            # --- 第十款：累積週轉率異常 (80% / 20% 門檻) ---
            if turnover_6d >= 80 and daily_turnover >= 20: 
                if (i - last_trigger["rule10"]) >= 6:
                    reasons.append(f"最近六個營業日(含當日)之累積週轉率為{turnover_6d:.2f}%，當日週轉率達{daily_turnover:.2f}%(第十款)")
                    last_trigger["rule10"] = i

        # --- 第十一款：絕對價差異常 ---
        if i >= 5:
            p_close_5 = df_price['close'].iloc[i-5]
            diff_5d_11 = c_close - p_close_5
            abs_diff_11 = abs(diff_5d_11)
            
            tier_11 = int(c_close // 500)
            threshold_11 = 100 + tier_11 * 25
            
            if abs_diff_11 >= threshold_11:
                six_day_prices = df_price['close'].iloc[i-5:i+1]
                if diff_5d_11 > 0 and c_close == six_day_prices.max():
                    if (i - last_trigger["rule11"]) >= 6:
                        reasons.append(f"六個營業日起迄兩個營業日收盤價價差達{abs_diff_11:.2f}元且當日收盤價為最近六個營業日收盤價最高者 ﹝第十一款﹞")
                        last_trigger["rule11"] = i
                elif diff_5d_11 < 0 and c_close == six_day_prices.min():
                    if (i - last_trigger["rule11"]) >= 6:
                        reasons.append(f"六個營業日起迄兩個營業日收盤價價差達{abs_diff_11:.2f}元且當日收盤價為最近六個營業日收盤價最低者 ﹝第十一款﹞")
                        last_trigger["rule11"] = i

        # --- 第十三款：當沖異常 ---
        total_vol_6d = df_price['Trading_Volume'].iloc[i-5:i+1].sum()
        dt_vol_6d = sum(day_dict.get(df_price.index[j].strftime('%Y-%m-%d'), {}).get('vol', 0) for j in range(i-5, i+1))
        dt_pct_6d = (dt_vol_6d / total_vol_6d * 100) if total_vol_6d > 0 else 0
        
        daily_dt_pct = day_dict.get(dt_str_curr, {}).get('pct', 0)
        if daily_dt_pct == 0 and day_dict.get(dt_str_curr, {}).get('vol', 0) > 0:
            daily_vol = df_price['Trading_Volume'].iloc[i]
            daily_dt_pct = (day_dict[dt_str_curr]['vol'] / daily_vol) * 100 if daily_vol > 0 else 0
        
        if dt_pct_6d >= 60 and daily_dt_pct >= 60:
            if (i - last_trigger["rule13"]) >= 6:
                reasons.append(f"最近六個營業日(含當日)之當沖成交量占總成交量達{dt_pct_6d:.2f}%，當日當沖比達{daily_dt_pct:.2f}%(第十三款)")
                last_trigger["rule13"] = i

        unique_reasons = list(dict.fromkeys(reasons))
        if unique_reasons:
            records.append({
                "date": curr_date,
                "年月日": dt_str_curr,
                "觸發條款": " \n".join(unique_reasons)
            })

    df = pd.DataFrame(records)
    if not df.empty:
        df = df.sort_values('date', ascending=False).reset_index(drop=True)
        counts = []
        for i in range(len(df)):
            curr = df.loc[i, 'date']
            start_win = curr - timedelta(days=30)
            c = len(df[(df['date'] <= curr) & (df['date'] > start_win)])
            counts.append(f"第 {c} 次")
        df['近20日累計次數'] = counts
        return df[['年月日', '近20日累計次數', '觸發條款']]

    return pd.DataFrame()

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

def calc_risk(prices):
    l = len(prices)
    if l < 7: return False
    now = prices[-1]
    c1 = (abs(now / prices[-7] - 1) > 0.25) if l >= 7 else False
    c2 = (now / prices[-31] - 1 > 1.0) if l >= 31 else False
    c3 = (now / prices[-61] - 1 > 1.3) if l >= 61 else False
    c4 = (now / prices[-91] - 1 > 1.6) if l >= 91 else False
    return c1 or c2 or c3 or c4

def simulate(prices, streak):
    sim = list(prices)
    for day in range(1, 11):
        next_p = sim[-1] * 1.099
        sim.append(next_p)
        if calc_risk(sim): streak += 1
        else: streak = 0
        if streak >= 3: return day, next_p
    return None, None

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

with st.spinner("正在啟動全天條覆蓋之極致推演引擎..."):
    df_price = api_request("TaiwanStockPrice", sid, start_str)
    df_taiex = api_request("TaiwanStockPrice", "TAIEX", start_str)
    df_inst = api_request("TaiwanStockInstitutionalInvestorsBuySell", sid, safe_start_str)
    df_margin = api_request("TaiwanStockMarginPurchaseShortSale", sid, safe_start_str)
    df_day = api_request("TaiwanStockDayTrading", sid, start_str)
    df_disp = api_request("TaiwanStockDispositionSecuritiesPeriod", start=(datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"))
    
    total_sheets = get_outstanding_shares(sid)
    if total_sheets == 0 and not df_margin.empty and 'MarginPurchaseLimit' in df_margin.columns:
        limit = df_margin['MarginPurchaseLimit'].max()
        if pd.notna(limit) and limit > 0:
            total_sheets = int((limit * 4) / 1000 if limit >= 1000000 else (limit * 4))

is_punished = False
disp_info = {}
if not df_disp.empty and 'period_end' in df_disp.columns:
    df_disp['stock_id'] = df_disp['stock_id'].astype(str).str.strip() 
    df_disp['period_end_dt'] = pd.to_datetime(df_disp['period_end'])
    active_disp = df_disp[(df_disp['stock_id'] == sid) & (df_disp['period_end_dt'] >= pd.Timestamp.today().normalize())]
    if not active_disp.empty:
        is_punished = True
        latest = active_disp.sort_values('period_end_dt').iloc[-1]
        measure = latest['measure']
        disp_info = {
            "period": f"{latest['period_start']} ~ {latest['period_end']}", 
            "measure": measure, 
            "match": extract_match_type(measure) 
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

df_notice_local = calculate_local_attention(df_price, df_day, df_taiex, total_sheets, is_twse)

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
tag_day = "t-on" if is_day_trade_eligible and not is_punished else "t-off" 

large_caps = ['2330', '2454', '2317', '2603', '3231', '3481', '2382', '2881', '2891', '2609', '2615', '3008', '2303', '1101']
tag_future = "t-on" if sid in large_caps or today_vol > 10000000 else "t-off"
tag_warrant = "t-on" if sid in large_caps or today_vol > 3000000 else "t-off"

with top_col2:
    tags_html = '<div class="tags-container">'
    tags_html += f'<span class="tag-base t-market">{market_name}</span>'
    tags_html += f'<span class="tag-base t-market">{info["industry"]}</span>'
    if is_punished: 
        tags_html += f'<span class="tag-base t-warn">處置中</span>'
        tags_html += f'<span class="tag-base t-warn">{disp_info["match"]}</span>'
    tags_html += f'<span class="tag-base {tag_margin}">資</span>'
    tags_html += f'<span class="tag-base {tag_short}">券</span>'
    tags_html += f'<span class="tag-base {tag_day}">沖</span>'
    tags_html += f'<span class="tag-base {tag_future}">期</span>'
    tags_html += f'<span class="tag-base {tag_warrant}">權</span>'
    tags_html += '</div>'
    st.markdown(tags_html, unsafe_allow_html=True)

st.markdown(f'<div class="title-text">{search} 盤後籌碼與風險分析</div>', unsafe_allow_html=True)

if not df_notice_local.empty and price_date_str_full != "":
    latest_notice_row = df_notice_local.iloc[0]
    if latest_notice_row['年月日'] == price_date_str_full:
        banner_html = f"""
        <div class="notice-banner">
            <div class="notice-banner-header">
                <div class="notice-banner-title">⚠️ 注意交易資訊公告</div>
                <div class="notice-banner-date">{latest_notice_row['年月日'].replace('-', '/')}</div>
            </div>
            <div class="notice-banner-content">
                {latest_notice_row['觸發條款'].replace(' \n', '<br>')}
            </div>
        </div>
        """
        st.markdown(banner_html, unsafe_allow_html=True)

# ------------------------------
# 🚀 異常爆量警戒倒推模型
# ------------------------------
turnover_warn_str = ""
if not df_price.empty and len(closes) >= 60:
    avg_vol_60d_lots = vols.tail(60).mean() / 1000
    warn_volume = avg_vol_60d_lots * 5 
    if warn_volume > 0:
        turnover_warn_str = f"約 {warn_volume:,.0f} 張"
    else:
        turnover_warn_str = "均量過低無法估算"
else:
    turnover_warn_str = "無法估算 (資料未滿60日)"

if total_sheets == 0:
    st.warning("⚠️ 無法從資料庫精確取得股本資料，週轉率相關天條可能無法正常觸發！")

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
        if is_punished:
            html_content = (
                '<div class="top-card">'
                '<div class="metric-label">風險預測</div>'
                f'<div class="metric-value" style="color:#ffc107;">🚨 已在處置中 ({disp_info["match"]})</div>'
                f'<div class="metric-sub">處置期間：{disp_info["period"]}</div>'
                f'<div class="metric-sub" style="color:#888; margin-top:8px;">(處置期間無須計算量能紅線)</div>'
                '<div style="width:100%; background-color:#333; border-radius:5px; margin-top:12px;">'
                '<div style="width:100%; background-color:#ffc107; height:6px; border-radius:5px;"></div>'
                '</div></div>'
            )
            st.markdown(html_content, unsafe_allow_html=True)
        else:
            streak = 0
            tmp = list(closes)
            for _ in range(5):
                if calc_risk(tmp): streak += 1; tmp.pop()
                else: break
            
            d, p = simulate(list(closes), streak)
            p_warn = closes.iloc[-6] * 1.25 if len(closes) >= 7 else 0
            
            if d:
                risk_width = max(0, min(100, 100 - (d * 10)))
                html_content = (
                    '<div class="top-card">'
                    '<div class="metric-label">風險預測</div>'
                    f'<div class="metric-value" style="color:#ffc107;">🔥 最快 {d} 天內進入處置 (或再次處置)</div>'
                    f'<div class="metric-sub">明日絕對注意價：{p_warn:.2f} ｜ 處置預估觸發價：{p:.2f}</div>'
                    f'<div class="metric-sub" style="color:#ff4b4b; margin-top:8px;">🚨 異常爆量警戒(60日均量5倍)：{turnover_warn_str}</div>'
                    '<div style="width:100%; background-color:#333; border-radius:5px; margin-top:12px;">'
                    f'<div style="width:{risk_width}%; background-color:#ffc107; height:6px; border-radius:5px;"></div>'
                    '</div></div>'
                )
                st.markdown(html_content, unsafe_allow_html=True)
            else:
                html_content = (
                    '<div class="top-card">'
                    '<div class="metric-label">風險預測</div>'
                    '<div class="metric-value" style="color:#00ff00;">✅ 短期內無處置風險</div>'
                    f'<div class="metric-sub">明日絕對注意價：{p_warn:.2f} ｜ 連拉10根漲停亦安全</div>'
                    f'<div class="metric-sub" style="color:#f5c518; margin-top:8px;">📊 異常爆量警戒(60日均量5倍)：{turnover_warn_str}</div>'
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
    # 📜 對稱雙塔：本機引擎自算 vs 官方處置
    # ==========================================
    st.markdown("---")
    h_col1, h_col2 = st.columns(2, gap="medium")
    
    with h_col1:
        notice_count = len(df_notice_local) if not df_notice_local.empty else 0
        with st.expander(f"📜 系統推演【注意股】歷史紀錄 (共 {notice_count} 次)"):
            if not df_notice_local.empty:
                st.dataframe(df_notice_local, hide_index=True, use_container_width=True)
            else: 
                st.write("近 30 交易日內未觸發系統嚴格注意標準")
                
    with h_col2:
        start_60d = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        h_df = api_request("TaiwanStockDispositionSecuritiesPeriod", sid, start_60d)
        with st.expander(f"🛑 近 30 交易日官方【處置股】紀錄 (共 {len(h_df) if not h_df.empty else 0} 次)"):
            if not h_df.empty:
                h_df['盤別'] = h_df['measure'].apply(extract_match_type)
                h_df = h_df[['period_start', 'period_end', '盤別', 'measure']]
                st.dataframe(h_df.rename(columns={'period_start':'起始日', 'period_end':'結束日', 'measure':'條款與措施'}), hide_index=True, use_container_width=True)
            else: 
                st.write("近 30 交易日內無處置紀錄")

else:
    st.error("查無此標的或歷史報價抓取失敗。")
