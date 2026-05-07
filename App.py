import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# ==========================================
# 🔑 100% FinMind VIP Token 設定
# ==========================================
FINMIND_TOKEN = "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJ1c2VyX2lkIjoiaWFubGluIiwiZW1haWwiOiJpYW5saW4yMDA0MDcxN0BnbWFpbC5jb20iLCJ0b2tlbl92ZXJzaW9uIjowfQ.G5jm2LKIg3BaZUIt7SIpqS1V1eZwzZg4ojuK2Naq2-8" 

# 設定網頁標題與圖示
st.set_page_config(page_title="台股處置預警雷達 (FinMind 盤後純淨版)", layout="wide")

# ==========================================
# 🎨 自訂 CSS (專業黑化介面)
# ==========================================
st.markdown("""
<style>
    .card-container { background-color: #1e1e26; border-radius: 12px; padding: 20px; margin-bottom: 15px; border: 1px solid #333; box-shadow: 2px 2px 10px rgba(0,0,0,0.3); }
    .metric-label { color: #88888e; font-size: 14px; margin-bottom: 8px; }
    .metric-value { color: #ffffff; font-size: 26px; font-weight: 700; }
    .metric-sub { font-size: 14px; font-weight: 500; }
    .tag { display: inline-block; padding: 4px 10px; border: 1px solid #444; border-radius: 6px; font-size: 12px; color: #bbb; margin-left: 8px; }
    .tag-yellow { background-color: #ffc107; color: #000; border: none; font-weight: 800; }
    .red-text { color: #ff4b4b; }
    .green-text { color: #00ff00; }
    .title-row { display: flex; align-items: center; justify-content: space-between; margin-bottom: 25px; }
    .title-text { font-size: 32px; font-weight: 800; color: #fff; }
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
            code = r['stock_id']
            if len(code) == 4 and code.isdigit():
                mapping[f"{code} {r['stock_name']}"] = {"id": code, "market": r['type'], "industry": r['industry_category']}
    return mapping

# --- 核心邏輯 ---
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
    df_disp = api_request("TaiwanStockDispositionSecuritiesPeriod", start=(datetime.now() - timedelta(days=45)).strftime("%Y-%m-%d"))

# 處理處置狀態
is_punished = False
if not df_disp.empty and 'period_end' in df_disp.columns:
    df_disp['period_end_dt'] = pd.to_datetime(df_disp['period_end'])
    active_disp = df_disp[df_disp['period_end_dt'] >= pd.Timestamp.today().normalize()]
    is_punished = sid in active_disp['stock_id'].values

st.markdown(f'<div class="title-row"><div class="title-text">{search} 盤後籌碼與風險分析</div></div>', unsafe_allow_html=True)

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

    # --- 第一行看板 ---
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(f'<div class="card-container"><div class="metric-label">收盤價</div><div class="metric-value {c_class}">{p_now:.2f}</div><div class="metric-sub {c_class}">{"▲" if diff>0 else "▼" if diff<0 else ""} {abs(diff):.2f} ({pct:+.2f}%)</div></div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="card-container">', unsafe_allow_html=True)
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
    col = st.columns(4)
    def m_card(c, l, v, clr="white", sub=""):
        c.markdown(f'<div class="card-container" style="padding:15px;"><div class="metric-label">{l}</div><div class="metric-value" style="font-size:20px; color:{clr};">{v}</div><div class="metric-sub" style="color:#888;">{sub}</div></div>', unsafe_allow_html=True)

    # 第一排：純粹的價量數據
    today_vol = vols.iloc[-1]
    vol_k = today_vol / 1000
    vol_5d_k = vols.tail(5).mean() / 1000
    m_card(col[0], "成交張數", f"{vol_k:.1f} 萬張")
    m_card(col[1], "成交金額", f"{(p_now * today_vol)/100000000:.1f} 億")
    m_card(col[2], "5日均量", f"{vol_5d_k:.1f} 萬張")
    m_card(col[3], "明日注意門檻", f"{closes.iloc[-5]*1.25:.2f}" if len(closes) >= 6 else "N/A", clr="#ffc107")

    # 第二排：當沖與法人 (自己計算精準比例)
    day_pct, day_vol_k = 0, 0
    if not df_day.empty and 'Buy_After_Day_Trading_Sell_Trade_Volume' in df_day.columns:
        # 當沖股數
        day_trade_shares = df_day['Buy_After_Day_Trading_Sell_Trade_Volume'].iloc[-1]
        day_vol_k = day_trade_shares / 1000
        # 自己算當沖率：當沖股數 / 總成交股數
        day_pct = (day_trade_shares / today_vol) * 100 if today_vol > 0 else 0

    m_card(col[0], "當沖率", f"{day_pct:.1f}%", clr="#f5c518")
    m_card(col[1], "當沖成交張數", f"{day_vol_k:.1f} 萬張")
    
    # 法人買賣超
    f_net, t_net = 0, 0
    if not df_inst.empty:
        # 只取最後一天的資料來計算
        last_date = df_inst['date'].max()
        daily_inst = df_inst[df_inst['date'] == last_date]
        inst_net = daily_inst.groupby('name')['buy'].sum() - daily_inst.groupby('name')['sell'].sum()
        f_net = inst_net.get('Foreign_Investor', 0) / 10000  # 換算成萬張或萬股(取決於API，通常是股，所以除以1萬是萬股/十張)
        t_net = inst_net.get('Investment_Trust', 0) / 10000
        
    m_card(col[2], "外資買賣超", f"{f_net:+.0f} 萬股", clr="white")
    m_card(col[3], "投信買賣超", f"{t_net:+.0f} 萬股")

    # 第三排：資券與比例 (使用正確的 TodayBalance 欄位)
    margin_bal, short_bal, short_ratio = 0, 0, 0
    if not df_margin.empty and 'MarginPurchaseTodayBalance' in df_margin.columns:
        margin_bal = df_margin['MarginPurchaseTodayBalance'].iloc[-1]
        short_bal = df_margin['ShortSaleTodayBalance'].iloc[-1]
        short_ratio = (short_bal / margin_bal * 100) if margin_bal > 0 else 0

    m_card(col[0], "融資餘額", f"{margin_bal/1000:.1f} 千張")
    m_card(col[1], "融券餘額", f"{short_bal/1000:.1f} 千張")
    m_card(col[2], "券資比", f"{short_ratio:.1f}%")
    turnover = (today_vol / vols.mean()) if vols.mean() > 0 else 0
    m_card(col[3], "週轉率", f"{turnover:.2f} 倍均量")

    # 歷史紀錄
    st.markdown("---")
    h_df = api_request("TaiwanStockDispositionSecuritiesPeriod", sid, (datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"))
    with st.expander(f"📜 歷史處置紀錄分析 (共 {len(h_df)} 次)"):
        if not h_df.empty:
            st.table(h_df[['period_start', 'period_end', 'measure']].rename(columns={'period_start':'起始', 'period_end':'結束', 'measure':'措施'}))
        else: st.write("無歷史處置紀錄")

else:
    st.error("查無此標的或歷史報價抓取失敗。")
