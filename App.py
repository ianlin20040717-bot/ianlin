import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# ==========================================
# 🔑 100% FinMind VIP Token 設定
# ==========================================
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiaWFubGluIiwiZW1haWwiOiJpYW5saW4yMDA0MDcxN0BnbWFpbC5jb20iLCJ0b2tlbl92ZXJzaW9uIjowfQ.G5jm2LKIg3BaZUIt7SIpqS1V1eZwzZg4ojuK2Naq2-8" 

# 設定網頁標題與圖示
st.set_page_config(page_title="台股處置預警雷達 (FinMind 旗艦版)", layout="wide")

# ==========================================
# 🎨 自訂 CSS (包含動態標籤與紅綠字體)
# ==========================================
st.markdown("""
<style>
    .card-container { background-color: #1e1e26; border-radius: 12px; padding: 20px; margin-bottom: 15px; border: 1px solid #333; box-shadow: 2px 2px 10px rgba(0,0,0,0.3); }
    .metric-label { color: #88888e; font-size: 14px; margin-bottom: 8px; }
    .metric-value { color: #ffffff; font-size: 24px; font-weight: 700; }
    .metric-sub { font-size: 14px; font-weight: 500; }
    
    /* 頂部標籤列排版 */
    .tags-container { display: flex; gap: 8px; flex-wrap: wrap; align-items: center; justify-content: flex-end; height: 100%; padding-bottom: 5px; }
    
    /* 標籤樣式 */
    .tag-base { padding: 4px 12px; border-radius: 4px; font-size: 13px; font-weight: 600; border: 1px solid #444; }
    .t-market { background-color: #2e2e38; color: #ddd; }
    .t-warn { background-color: #ffc107; color: #000; border: none; }
    .t-on { background-color: #3b3b4f; color: #fff; border-color: #666; }
    .t-off { background-color: #1a1a21; color: #555; border-color: #333; }
    
    .red-text { color: #ff4b4b !important; }
    .green-text { color: #00ff00 !important; }
    .title-text { font-size: 32px; font-weight: 800; color: #fff; margin-bottom: 25px; }
</style>
""", unsafe_allow_html=True)

# ==========================================
# 📡 FinMind 資料抓取模組
# ==========================================
@st.cache_data(ttl=3600)
def api_request(dataset, data_id=None, start=None, token=FINMIND_TOKEN):
    url = "https://api.finmindtrade.com/api/v4/data"
    params = {"dataset": dataset, "token": token}
    if data_id: params["data_id"] = data_id
    if start: params["start_date"] = start
    try:
        res = requests.get(url, params=params, timeout=10).json()
        return pd.DataFrame(res.get('data', []))
    except: return pd.DataFrame()

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

# --- 核心風險邏輯 ---
def calc_risk(prices):
    if len(prices) < 90: return False
    now = prices[-1]
    return (abs(now / prices[-6] - 1) > 0.25) or (now / prices[-30] - 1 > 1.0) or (now / prices[-60] - 1 > 1.3)

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

# 🎯 第一列：搜尋框與標籤列
top_col1, top_col2 = st.columns([1, 1])

with top_col1:
    search = st.selectbox("🔍 搜尋標的", options=list(stock_list.keys()), index=list(stock_list.keys()).index("2454 聯發科") if "2454 聯發科" in stock_list else 0)

info = stock_list[search]
sid = info['id']
start_str = (datetime.now() - timedelta(days=120)).strftime("%Y-%m-%d")

# 一次性抓取所有必要資料
with st.spinner("正在載入盤後數據..."):
    df_price = api_request("TaiwanStockPrice", sid, start_str)
    df_inst = api_request("TaiwanStockInstitutionalInvestorsBuySell", sid, (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"))
    df_margin = api_request("TaiwanStockMarginPurchaseShortSale", sid, (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"))
    df_day = api_request("TaiwanStockDayTrading", sid, (datetime.now() - timedelta(days=5)).strftime("%Y-%m-%d"))
    df_disp = api_request("TaiwanStockDispositionSecuritiesPeriod", start=(datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"))

# 處理處置狀態
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
        match_time = "20分盤" if "二十分" in measure else "5分盤" if "五分" in measure else "10分盤" if "十分" in measure else "處置中"
        disp_info = {"period": f"{latest['period_start']} ~ {latest['period_end']}", "measure": measure, "match": match_time}

# 計算收盤價與基本數據
if not df_price.empty:
    df_price['date'] = pd.to_datetime(df_price['date'])
    df_price = df_price.set_index('date').sort_index()
    closes = df_price['close']
    vols = df_price['Trading_Volume']
    p_now = closes.iloc[-1]
    p_prev = closes.iloc[-2] if len(closes) > 1 else p_now
    diff = p_now - p_prev
    pct = (diff / p_prev) * 100 if p_prev > 0 else 0
    c_class = "red-text" if diff > 0 else "green-text" if diff < 0 else ""
    today_vol = vols.iloc[-1]
else:
    p_now, today_vol = 0, 0

# 準備標籤亮燈邏輯
market_name = "上市" if info['market'] == 'twse' else "上櫃"
margin_bal = df_margin['MarginPurchaseTodayBalance'].iloc[-1] if not df_margin.empty and 'MarginPurchaseTodayBalance' in df_margin.columns else 0
short_bal = df_margin['ShortSaleTodayBalance'].iloc[-1] if not df_margin.empty and 'ShortSaleTodayBalance' in df_margin.columns else 0
day_trade_vol = df_day['Buy_After_Day_Trading_Sell_Trade_Volume'].iloc[-1] if not df_day.empty and 'Buy_After_Day_Trading_Sell_Trade_Volume' in df_day.columns else 0

tag_margin = "t-on" if margin_bal > 0 else "t-off"
tag_short = "t-on" if short_bal > 0 else "t-off"
tag_day = "t-on" if day_trade_vol > 0 and not is_punished else "t-off" 

# 💡 智能期權標籤判定：大型權值股或高周轉熱門股自動亮燈
large_caps = ['2330', '2454', '2317', '2603', '3231', '3481', '2382', '2881', '2891', '2609', '2615', '3008', '2303', '1101']
tag_future = "t-on" if sid in large_caps or today_vol > 10000000 else "t-off"
tag_warrant = "t-on" if sid in large_caps or today_vol > 3000000 else "t-off"

with top_col2:
    tags_html = f"""
    <div class="tags-container">
        <span class="tag-base t-market">{market_name}</span>
        <span class="tag-base t-market">{info['industry']}</span>
    """
    if is_punished: tags_html += f'<span class="tag-base t-warn">{disp_info["match"]}</span>'
        
    tags_html += f"""
        <span class="tag-base {tag_margin}">資</span>
        <span class="tag-base {tag_short}">券</span>
        <span class="tag-base {tag_day}">沖</span>
        <span class="tag-base {tag_future}">期</span>
        <span class="tag-base {tag_warrant}">權</span>
    </div>
    """
    st.markdown(tags_html, unsafe_allow_html=True)

st.markdown(f'<div class="title-text">{search} 盤後籌碼與風險分析</div>', unsafe_allow_html=True)

if not df_price.empty:
    # --- 第一行看板 ---
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="card-container"><div class="metric-label">收盤價</div><div class="metric-value {c_class}">{p_now:.2f}</div><div class="metric-sub {c_class}">{"▲" if diff>0 else "▼" if diff<0 else ""} {abs(diff):.2f} ({pct:+.2f}%)</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="card-container">', unsafe_allow_html=True)
        if is_punished:
            st.markdown(f'<div class="metric-label">風險預測</div><div class="metric-value" style="color:#ffc107;">🚨 已在處置中</div><div class="metric-sub">處置期間：{disp_info["period"]}</div>', unsafe_allow_html=True)
        else:
            streak = 0
            tmp = list(closes)
            for _ in range(5):
                if calc_risk(tmp): streak += 1; tmp.pop()
                else: break
            d, p = simulate(list(closes), streak)
            if d:
                st.markdown(f'<div class="metric-label">風險預測</div><div class="metric-value" style="color:#ffc107;">🔥 T+{d} 可能處置</div><div class="metric-sub">預估門檻價：{p:.2f}</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div class="metric-label">風險分析</div><div class="metric-value" style="color:#00ff00;">✅ 目前風險等級：低</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    # --- 九宮格數據區 ---
    def m_card(c, l, v, clr="white", sub=""):
        c.markdown(f'<div class="card-container" style="padding:15px;"><div class="metric-label">{l}</div><div class="metric-value" style="font-size:22px; color:{clr};">{v}</div><div class="metric-sub" style="color:#888;">{sub}</div></div>', unsafe_allow_html=True)

    # 第一排：純粹的價量數據
    col_r1 = st.columns(4)
    vol_lots = today_vol / 1000 
    vol_5d_lots = vols.tail(5).mean() / 1000
    m_card(col_r1[0], "成交張數", f"{vol_lots:,.0f} 張")
    m_card(col_r1[1], "成交金額", f"{(p_now * today_vol)/100000000:.1f} 億")
    m_card(col_r1[2], "5日均量", f"{vol_5d_lots:,.0f} 張")
    m_card(col_r1[3], "明日注意門檻", f"{closes.iloc[-5]*1.25:.2f}" if len(closes) >= 6 else "N/A", clr="#ffc107")

    # 第二排：當沖與週轉
    col_r2 = st.columns(3)
    day_pct, day_vol_lots = 0, 0
    if day_trade_vol > 0:
        day_vol_lots = day_trade_vol / 1000
        day_pct = (day_trade_vol / today_vol) * 100 if today_vol > 0 else 0
    turnover = (today_vol / vols.mean()) if vols.mean() > 0 else 0

    m_card(col_r2[0], "當沖率", f"{day_pct:.1f}%", clr="#f5c518")
    m_card(col_r2[1], "當沖成交張數", f"{day_vol_lots:,.0f} 張")
    m_card(col_r2[2], "週轉率", f"{turnover:.2f} 倍均量")

    # 第三排：法人買賣超 (金額 + 智慧紅綠燈)
    col_r3 = st.columns(4)
    f_amt, t_amt, d_amt, total_amt = 0, 0, 0, 0
    if not df_inst.empty:
        last_date = df_inst['date'].max()
        daily_inst = df_inst[df_inst['date'] == last_date]
        inst_net = daily_inst.groupby('name')['buy'].sum() - daily_inst.groupby('name')['sell'].sum()
        
        f_shares = inst_net.get('Foreign_Investor', 0) + inst_net.get('Foreign_Dealer_Self', 0)
        t_shares = inst_net.get('Investment_Trust', 0)
        d_shares = inst_net.get('Dealer_self', 0) + inst_net.get('Dealer_Hedging', 0)
        
        f_amt = f_shares * p_now
        t_amt = t_shares * p_now
        d_amt = d_shares * p_now
        total_amt = f_amt + t_amt + d_amt

    # 💡 買賣超金額格式化器 (附加顏色)
    def format_inst_amt(val):
        if val == 0: return "0", "white"
        sign = "+" if val > 0 else ""
        clr = "#ff4b4b" if val > 0 else "#00ff00" # 紅買綠賣
        if abs(val) >= 100000000:
            return f"{sign}{val/100000000:.2f} 億", clr
        else:
            return f"{sign}{val/10000:,.0f} 萬", clr

    total_str, total_clr = format_inst_amt(total_amt)
    f_str, f_clr = format_inst_amt(f_amt)
    t_str, t_clr = format_inst_amt(t_amt)
    d_str, d_clr = format_inst_amt(d_amt)

    m_card(col_r3[0], "三大法人買賣超", total_str, clr=total_clr)
    m_card(col_r3[1], "外資買賣超", f_str, clr=f_clr)
    m_card(col_r3[2], "投信買賣超", t_str, clr=t_clr)
    m_card(col_r3[3], "自營商買賣超", d_str, clr=d_clr)

    # 📏 歷史紀錄 (版面平分設計)
    st.markdown("---")
    h_col1, h_col2 = st.columns(2)
    with h_col1:
        h_df = api_request("TaiwanStockDispositionSecuritiesPeriod", sid, (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"))
        with st.expander(f"📜 歷史處置紀錄分析 (共 {len(h_df)} 次)"):
            if not h_df.empty:
                st.table(h_df[['period_start', 'period_end', 'measure']].rename(columns={'period_start':'起始', 'period_end':'結束', 'measure':'措施'}))
            else: st.write("無歷史處置紀錄")

else:
    st.error("查無此標的或歷史報價抓取失敗。")
