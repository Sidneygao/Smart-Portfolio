import streamlit as st
import pandas as pd
import json
import os
import requests
import time
import yfinance as yf
from datetime import datetime
from zoneinfo import ZoneInfo

st.set_page_config(page_title="Smart Portfolio", page_icon="📈", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    .stMetric { padding: 0px 2px; margin: 0px; }
    .stMetric label { font-size: 11px; font-weight: bold; }
    .stMetric [data-testid="stMetricValue"] { font-size: 14px; font-weight: bold; }
    .stMetric [data-testid="stMetricDelta"] { font-size: 12px; }
    div[data-testid="stHorizontalBlock"] > div { padding: 0px; }
    h1 { font-size: 1.4rem !important; margin-bottom: 0.2rem !important; margin-top: 0 !important; }
    h2 { font-size: 1.3rem !important; margin-top: 0.2rem !important; margin-bottom: 0.2rem !important; }
    .stDataFrame { font-size: 13px; }
    div[data-testid="stVerticalBlock"] > div { padding: 0.02rem 0; }
    .stButton button { font-size: 13px; padding: 2px 8px; }
    .stTextInput input, .stNumberInput input { font-size: 13px; }
    .stSidebar { font-size: 13px; }
    .stSidebar .stSelectbox, .stSidebar .stNumberInput, .stSidebar .stButton, .stSidebar .stTextInput {
        margin-bottom: 0.05rem !important;
    }
    .stSidebar h3 {
        margin-top: 0.02rem !important;
        margin-bottom: 0.02rem !important;
        font-size: 0.75rem !important;
    }
    .stSidebar h2 {
        margin-top: 0.05rem !important;
        margin-bottom: 0.03rem !important;
        font-size: 0.85rem !important;
    }
</style>
""", unsafe_allow_html=True)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio.json")
CASH_FILE = os.path.join(BASE_DIR, "client_cash.json")
CACHE_FILE = os.path.join(BASE_DIR, "stock_cache.json")
CACHE_TTL_SECONDS = 3600
TWELVE_DATA_API_KEY = os.environ.get("TWELVE_DATA_API_KEY", "")
PERIOD_TRADING_DAYS = {"5d": 5, "1m": 21, "3m": 63}

def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_portfolio(portfolio):
    """Persist only the essential fields; prices and derived values are always re-fetched."""
    essentials = [
        {
            'symbol': p['symbol'],
            'shares': p['shares'],
            'avg_cost': p['avg_cost'],
            'currency': p.get('currency', 'USD'),
            'fx': p.get('fx', 1),
        }
        for p in portfolio
    ]
    with open(PORTFOLIO_FILE, 'w') as f:
        json.dump(essentials, f, indent=2)

def load_client_cash():
    try:
        with open(CASH_FILE, 'r') as f:
            return json.load(f)
    except:
        return {"azhu": {"name": "AZHU", "usd": 0, "hkd": 0}, "aniu": {"name": "ANIU", "usd": 0, "hkd": 0}}

def save_client_cash(cash_data):
    with open(CASH_FILE, 'w') as f:
        json.dump(cash_data, f, indent=2)

def get_exchange_rates():
    try:
        response = requests.get('https://api.exchangerate-api.com/v4/latest/USD')
        data = response.json()
        return {'usd_to_cny': data['rates']['CNY'], 'usd_to_hkd': data['rates']['HKD'], 'hkd_to_usd': 1 / data['rates']['HKD']}
    except:
        return {'usd_to_cny': 7.2, 'usd_to_hkd': 7.8, 'hkd_to_usd': 0.128}

def get_market_data(symbols):
    """Fetch latest prices and 3-month close history for all symbols in one batched request."""
    data = {}
    if not symbols:
        return data
    try:
        raw = yf.download(symbols, period="3mo", interval="1d", group_by="ticker",
                          threads=True, progress=False, auto_adjust=False)
    except Exception:
        raw = None

    for symbol in symbols:
        closes = []
        try:
            if raw is not None and len(symbols) > 1:
                closes = raw[symbol]["Close"].dropna().tolist()
            elif raw is not None:
                closes = raw["Close"].dropna().tolist()
        except (KeyError, TypeError):
            closes = []
        if closes:
            data[symbol] = {"price": closes[-1], "history": closes}
    return data

def get_price_twelvedata(symbol, api_key):
    if not api_key:
        return None
    for variant in (symbol, f"{symbol}.US", f"{symbol}.NASDAQ", f"{symbol}.NYSE"):
        try:
            url = f"https://api.twelvedata.com/quote?symbol={variant}&apikey={api_key}"
            payload = requests.get(url, timeout=5).json()
            if payload.get("code") == 429:
                continue
            if "close" in payload:
                price = float(payload["close"])
                if 0 < price < 10000:
                    return price
        except (requests.RequestException, ValueError):
            continue
    return None

def calculate_percentile(current_price, history, period):
    """Rank of the current price within the closes of the given trailing period."""
    window = PERIOD_TRADING_DAYS.get(period)
    if not window or not history:
        return None
    prices = history[-window:]
    if len(prices) < 2:
        return None
    return sum(1 for p in prices if p <= current_price) / len(prices) * 100

def load_cache():
    try:
        with open(CACHE_FILE, 'r') as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}

def save_cache(cache):
    with open(CACHE_FILE, 'w') as f:
        json.dump(cache, f)

def get_market_status():
    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:
        return "🌙 Market Closed"
    minutes = now.hour * 60 + now.minute
    if 4 * 60 <= minutes < 9 * 60 + 30:
        return "🌅 Pre-Market"
    if 9 * 60 + 30 <= minutes < 16 * 60:
        return "🌞 Regular Hours"
    if 16 * 60 <= minutes < 20 * 60:
        return "🌆 After-Hours"
    return "🌙 Market Closed"

def populate_market_data(portfolio, force=False):
    """Fill each position with a price, close history and derived values.

    Returns the symbols with no data at all and those served from an expired cache.
    """
    cache = load_cache()
    now = time.time()
    outdated = [
        p['symbol'] for p in portfolio
        if force or now - cache.get(p['symbol'], {}).get('timestamp', 0) >= CACHE_TTL_SECONDS
    ]
    fetched = get_market_data(outdated)

    for symbol in outdated:
        entry = fetched.get(symbol)
        if entry is None:
            price = get_price_twelvedata(symbol, TWELVE_DATA_API_KEY)
            if price is None:
                continue
            entry = {'price': price, 'history': cache.get(symbol, {}).get('history', [])}
        cache[symbol] = {'price': entry['price'], 'history': entry['history'], 'timestamp': now}
    save_cache(cache)

    failed, from_stale_cache = [], []
    for position in portfolio:
        entry = cache.get(position['symbol'])
        if entry is None:
            position['price'] = 0
            position['history'] = []
            failed.append(position['symbol'])
        else:
            position['price'] = entry['price']
            position['history'] = entry.get('history', [])
            if now - entry.get('timestamp', 0) >= CACHE_TTL_SECONDS:
                from_stale_cache.append(position['symbol'])
        position['market_value'] = position['shares'] * position['price']
        position['total_cost'] = position['shares'] * position['avg_cost']
        position['profit_loss'] = position['market_value'] - position['total_cost']
        position['inc_percent'] = (position['profit_loss'] / position['total_cost'] * 100) if position['total_cost'] > 0 else 0
    return failed, from_stale_cache

def main():
    st.markdown('<h1 style="color: #1f77b4; font-size: 1.4rem; font-weight: bold; margin: 0;">📈 Smart Portfolio</h1>', unsafe_allow_html=True)
    
    portfolio = load_portfolio()
    client_cash = load_client_cash()
    
    exchange_rates = get_exchange_rates()
    usd_to_cny = exchange_rates['usd_to_cny']
    hkd_to_usd = exchange_rates['hkd_to_usd']
    
    failed_symbols, cached_symbols = populate_market_data(portfolio, force=st.session_state.pop("force_update", False))
    stocks_usd = sum(p['market_value'] for p in portfolio)
    
    if cached_symbols:
        st.warning(f"⚠️ Using cached prices for: {', '.join(cached_symbols)}")
    if failed_symbols:
        st.error(f"❌ No price data for: {', '.join(failed_symbols)}")
    
    # Sidebar with editing functions (compact)
    with st.sidebar:
        st.header("Edit Stock")
        selected_symbol = st.selectbox("Symbol", [p['symbol'] for p in portfolio])
        
        if selected_symbol:
            position = next((p for p in portfolio if p['symbol'] == selected_symbol), None)
            if position:
                col1, col2 = st.columns(2)
                with col1:
                    new_shares = st.number_input("Shares", value=float(position['shares']), min_value=0.01, step=0.01, key=f"sidebar_shares_{selected_symbol}")
                with col2:
                    new_cost = st.number_input("Avg Cost", value=float(position['avg_cost']), min_value=0.01, step=0.01, key=f"sidebar_cost_{selected_symbol}")
                
                if st.button("Update Stock", key=f"sidebar_update_{selected_symbol}"):
                    position['shares'] = new_shares
                    position['avg_cost'] = new_cost
                    save_portfolio(portfolio)
                    st.success("Updated!")
                    st.rerun()
        
        st.divider()
        
        st.header("Edit Cash")
        selected_client = st.selectbox("Account", ["AZHU", "ANIU"])
        
        if selected_client:
            client_key = selected_client.lower()
            st.subheader(f"{selected_client}")
            col1, col2 = st.columns(2)
            with col1:
                new_usd = st.number_input("USD", value=float(client_cash[client_key]['usd']), min_value=0.0, step=100.0, key=f"sidebar_cash_usd_{selected_client}")
            with col2:
                new_hkd = st.number_input("HKD", value=float(client_cash[client_key]['hkd']), min_value=0.0, step=100.0, key=f"sidebar_cash_hkd_{selected_client}")
            
            if st.button("Update Cash", key=f"sidebar_update_cash_{selected_client}"):
                client_cash[client_key]['usd'] = new_usd
                client_cash[client_key]['hkd'] = new_hkd
                save_client_cash(client_cash)
                st.success("Updated!")
                st.rerun()
        
        st.divider()
        
        st.header("Add New Stock")
        new_symbol = st.text_input("Symbol", key="add_symbol").upper()
        new_shares = st.number_input("Shares", min_value=0.01, step=0.01, key="add_shares")
        new_cost = st.number_input("Avg Cost", min_value=0.01, step=0.01, key="add_cost")
        
        if st.button("Add Stock", key="add_stock_button"):
            if new_symbol and new_shares > 0 and new_cost > 0:
                existing = next((p for p in portfolio if p['symbol'] == new_symbol), None)
                if existing:
                    total_shares = existing['shares'] + new_shares
                    existing['avg_cost'] = (existing['avg_cost'] * existing['shares'] + new_cost * new_shares) / total_shares
                    existing['shares'] = total_shares
                    save_portfolio(portfolio)
                    st.success(f"Updated {new_symbol}")
                else:
                    new_position = {
                        'symbol': new_symbol,
                        'shares': new_shares,
                        'avg_cost': new_cost,
                        'currency': 'USD',
                        'fx': 1
                    }
                    portfolio.append(new_position)
                    save_portfolio(portfolio)
                    st.success(f"Added {new_symbol}")
                st.rerun()
    
    if not portfolio:
        st.info("No positions. Add first position in sidebar.")
        return
    
    # Manual price update button and market status - combined single row
    col1, col2 = st.columns([1, 4])
    with col1:
        if st.button("🔄 Force Update All"):
            st.session_state["force_update"] = True
            st.rerun()
    
    with col2:
        priced = len(portfolio) - len(failed_symbols)
        status_text = f"📊 {priced}/{len(portfolio)} priced | 🌐 {get_market_status()} | 🕒 {datetime.now(ZoneInfo('America/New_York')):%H:%M ET}"
        st.info(status_text)
    
    stocks_cost = sum(p['total_cost'] for p in portfolio)
    stocks_profit = stocks_usd - stocks_cost
    
    azhu_usd_total = client_cash['azhu']['usd'] + (client_cash['azhu']['hkd'] * hkd_to_usd)
    aniu_usd_total = client_cash['aniu']['usd'] + (client_cash['aniu']['hkd'] * hkd_to_usd)
    total_cash_usd = azhu_usd_total + aniu_usd_total
    grand_total_usd = stocks_usd + total_cash_usd
    grand_total_cny = grand_total_usd * usd_to_cny
    
    st.markdown('### Portfolio Holdings')
    
    # Calculate total value for percentage calculation
    total_stocks_value = sum(p['market_value'] for p in portfolio)
    total_value = total_stocks_value + total_cash_usd
    
    # Sort by market value percentage (largest first)
    portfolio_sorted = sorted(portfolio, key=lambda x: x['market_value'], reverse=True)
    
    portfolio_data = []
    
    for position in portfolio_sorted:
        symbol = position['symbol']
        current_price = position['price']
        value_percent = (position['market_value'] / total_value * 100) if total_value > 0 else 0
        
        history = position.get('history', [])
        p5d = calculate_percentile(current_price, history, '5d')
        p30d = calculate_percentile(current_price, history, '1m')
        p3m = calculate_percentile(current_price, history, '3m')
        
        # Color coding for percentiles
        def color_pct(pct_val):
            if pct_val is None:
                return "N/A"
            if pct_val > 45:
                return f"<span style='color: red; font-weight: bold;'>{pct_val:.0f}%</span>"
            elif pct_val > 40:
                return f"<span style='color: orange; font-weight: bold;'>{pct_val:.0f}%</span>"
            elif pct_val < 35:
                return f"<span style='color: green; font-weight: bold;'>{pct_val:.0f}%</span>"
            else:
                return f"{pct_val:.0f}%"
        
        p5d = color_pct(p5d)
        p30d = color_pct(p30d)
        p3m = color_pct(p3m)
        
        portfolio_data.append({
            'Symbol': symbol,
            'Shares': int(position['shares']),
            'Cost': f"${position['avg_cost']:.2f}",
            'Price': f"${current_price:.2f}",
            '% of Total': f"{value_percent:.1f}%",
            'Ret': f"{position['inc_percent']:.1f}%",
            '5D %': p5d,
            '30D %': p30d,
            '3M %': p3m
        })
    
    df = pd.DataFrame(portfolio_data)
    html_table = df.to_html(escape=False, index=False)
    html_table = html_table.replace('<table', '<table style="border-collapse: collapse; width: 100%; font-size: 13px; table-layout: fixed;"')
    html_table = html_table.replace('<th', '<th style="padding: 1px 3px; text-align: center; border-bottom: 1px solid #ddd;"')
    html_table = html_table.replace('<td', '<td style="padding: 1px 3px; text-align: center; border-bottom: 1px solid #eee;"')
    st.markdown(html_table, unsafe_allow_html=True)
    
    st.markdown('### Cash Holdings')
    
    cash_data = [
        {'Client': 'AZHU', 'USD': f"${client_cash['azhu']['usd']:,.0f}", 'HKD': f"${client_cash['azhu']['hkd']:,.0f}", 'Total': f"${azhu_usd_total:,.0f}"},
        {'Client': 'ANIU', 'USD': f"${client_cash['aniu']['usd']:,.0f}", 'HKD': f"${client_cash['aniu']['hkd']:,.0f}", 'Total': f"${aniu_usd_total:,.0f}"},
        {'Client': 'TOTAL', 'USD': '-', 'HKD': '-', 'Total': f"${total_cash_usd:,.0f}"}
    ]
    
    cash_df = pd.DataFrame(cash_data)
    html_cash = cash_df.to_html(escape=False, index=False)
    html_cash = html_cash.replace('<table', '<table style="border-collapse: collapse; width: 100%; font-size: 13px; table-layout: fixed;"')
    html_cash = html_cash.replace('<th', '<th style="padding: 1px 3px; text-align: center; border-bottom: 1px solid #ddd;"')
    html_cash = html_cash.replace('<td', '<td style="padding: 1px 3px; text-align: center; border-bottom: 1px solid #eee;"')
    st.markdown(html_cash, unsafe_allow_html=True)
    
    # Final totals - compact single row
    cash_pct = (total_cash_usd / grand_total_usd * 100) if grand_total_usd > 0 else 0
    stocks_pct = (stocks_usd / grand_total_usd * 100) if grand_total_usd > 0 else 0
    stocks_return_pct = (stocks_profit / stocks_cost * 100) if stocks_cost > 0 else 0
    totals_text = (
        f"💰 Total: ${grand_total_usd:,.0f} USD (¥{grand_total_cny:,.0f} CNY) | "
        f"📊 Stocks: {stocks_pct:.0f}% Cash: {cash_pct:.0f}% | "
        f"📈 Unrealized P/L: ${stocks_profit:,.0f} ({stocks_return_pct:+.1f}%)"
    )
    st.info(totals_text)

if __name__ == "__main__":
    main()