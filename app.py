import streamlit as st
import pandas as pd
import json
import requests
import time
import re
from datetime import datetime

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

PORTFOLIO_FILE = "portfolio.json"
CASH_FILE = "client_cash.json"

def load_portfolio():
    try:
        with open(PORTFOLIO_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_portfolio(portfolio):
    with open(PORTFOLIO_FILE, 'w') as f:
        json.dump(portfolio, f, indent=2)

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

def get_stock_price_twelvedata(symbol, api_key):
    try:
        # Try quote endpoint first - it has more data
        url = f"https://api.twelvedata.com/quote?symbol={symbol}&apikey={api_key}"
        response = requests.get(url)
        data = response.json()
        
        if 'close' in data:
            price = float(data['close'])
            return price
        
        # Fallback to time_series
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1day&outputsize=1&apikey={api_key}"
        response = requests.get(url)
        data = response.json()
        
        if 'values' in data and len(data['values']) > 0:
            latest = data['values'][0]
            price = float(latest['close'])
            return price
            
        return None
    except Exception as e:
        return None

def get_key_data_points(symbol, api_key):
    try:
        # Get 90 days of data to extract key points
        url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval=1day&outputsize=90&apikey={api_key}"
        response = requests.get(url, timeout=10)
        data = response.json()
        
        if 'values' in data and len(data['values']) > 0:
            prices = [float(v['close']) for v in data['values']]
            # Extract key points: today (index 0), day 5, day 30, day 90
            key_points = {}
            key_points['today'] = prices[0] if len(prices) > 0 else None
            key_points['day5'] = prices[4] if len(prices) > 4 else None
            key_points['day30'] = prices[29] if len(prices) > 29 else None
            key_points['day90'] = prices[89] if len(prices) > 89 else None
            return key_points
        return {}
    except:
        return {}

def calculate_percentile_linear(current_price, key_points, period='all'):
    print(f"DEBUG calculate_percentile: current_price={current_price}, key_points={key_points}, period={period}")
    
    if not key_points or not key_points.get('today'):
        print(f"DEBUG: Missing key points or today price")
        return None
    
    # Simulate price distribution using linear interpolation between key points
    simulated_prices = []
    
    if period == '5d' and key_points.get('day5'):
        # Linear interpolation between day5 and today
        for i in range(5):
            weight = i / 4  # 0 to 1
            price = key_points['day5'] * (1 - weight) + key_points['today'] * weight
            simulated_prices.append(price)
    elif period == '1month' and key_points.get('day30'):
        # Linear interpolation between day30 and today
        for i in range(30):
            weight = i / 29  # 0 to 1
            price = key_points['day30'] * (1 - weight) + key_points['today'] * weight
            simulated_prices.append(price)
    elif period == 'all' and key_points.get('day90'):
        # Linear interpolation between day90 and today
        for i in range(90):
            weight = i / 89  # 0 to 1
            price = key_points['day90'] * (1 - weight) + key_points['today'] * weight
            simulated_prices.append(price)
    else:
        print(f"DEBUG: Missing required key point for period {period}")
        return None
    
    if not simulated_prices:
        print(f"DEBUG: No simulated prices generated")
        return None
    
    simulated_prices.sort()
    percentile = (sum(1 for p in simulated_prices if p <= current_price) / len(simulated_prices)) * 100
    print(f"DEBUG: Calculated percentile: {percentile}")
    return percentile

def get_stock_price_yahoo(symbol):
    try:
        url = f"https://finance.yahoo.com/quote/{symbol}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            price_match = re.search(r'"regularMarketPrice":{"raw":([0-9.]+)', response.text)
            if price_match:
                price = float(price_match.group(1))
                if price > 0 and price < 5000:
                    return price
        return None
    except:
        return None
    try:
        url = f"https://finance.yahoo.com/quote/{symbol}"
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            price_match = re.search(r'"regularMarketPrice":{"raw":([0-9.]+)', response.text)
            if price_match:
                price = float(price_match.group(1))
                if price > 0 and price < 5000:
                    return price
        return None
    except:
        return None

def get_stock_price(symbol, api_key):
    # Try Twelve Data - quote endpoint first, then basic price endpoint
    try:
        url = f"https://api.twelvedata.com/quote?symbol={symbol}&apikey={api_key}"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        # Handle rate limiting
        if data.get('code') == 429:
            # Skip rate limited stocks instead of waiting
            print(f"Rate limited for {symbol}, skipping")
            return None
        
        if 'close' in data:
            price = float(data['close'])
            return price
    except Exception as e:
        print(f"DEBUG {symbol} quote error: {e}")
    
    try:
        url = f"https://api.twelvedata.com/price?symbol={symbol}&apikey={api_key}"
        response = requests.get(url, timeout=5)
        data = response.json()
        
        # Handle rate limiting
        if data.get('code') == 429:
            print(f"Rate limited for {symbol} (price), skipping")
            return None
        
        if 'price' in data:
            price = float(data['price'])
            return price
    except Exception as e:
        print(f"DEBUG {symbol} price error: {e}")
    
    return None

def main():
    st.markdown('<h1 style="color: #1f77b4; font-size: 1.4rem; font-weight: bold; margin: 0;">📈 Smart Portfolio</h1>', unsafe_allow_html=True)
    
    portfolio = load_portfolio()
    client_cash = load_client_cash()
    
    exchange_rates = get_exchange_rates()
    usd_to_cny = exchange_rates['usd_to_cny']
    hkd_to_usd = exchange_rates['hkd_to_usd']
    
    api_key = "8f411860976c4166a4dc51dafb992dd8"
    
    # Fetch real-time prices for all stocks
    stocks_usd = 0
    for position in portfolio:
        symbol = position['symbol']
        price = get_stock_price(symbol, api_key)
        if price:
            position['price'] = price
        else:
            position['price'] = 0  # Fallback if API fails
        
        # Calculate values
        shares = position['shares']
        avg_cost = position['avg_cost']
        position['market_value'] = shares * position['price']
        position['total_cost'] = shares * avg_cost
        position['profit_loss'] = position['market_value'] - position['total_cost']
        position['inc_percent'] = (position['profit_loss'] / position['total_cost']) * 100 if position['total_cost'] > 0 else 0
        
        stocks_usd += position['market_value']
    
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
                    existing['shares'] += new_shares
                    existing['avg_cost'] = (existing['avg_cost'] * existing['shares'] + new_cost * new_shares) / (existing['shares'] + new_shares)
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
            st.info("Force updating all prices...")
            updated_count = 0
            for position in portfolio:
                symbol = position['symbol']
                price = get_stock_price(symbol, api_key)
                if price:
                    position['price'] = price
                    position['last_updated'] = filetime.time()
                    updated_count += 1
                else:
                    st.warning(f"Failed to fetch price for {symbol}")
                time.sleep(0.2)
            
            if updated_count > 0:
                for position in portfolio:
                    position['market_value'] = position['shares'] * position['price']
                    position['total_cost'] = position['shares'] * position['avg_cost']
                    position['profit_loss'] = position['market_value'] - position['total_cost']
                    position['inc_percent'] = (position['profit_loss'] / position['total_cost']) * 100 if position['total_cost'] > 0 else 0
                
                save_portfolio(portfolio)
                st.success(f"Updated {updated_count} prices!")
                st.rerun()
            else:
                st.warning("No prices updated")
    
    with col2:
        # Combined status message
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()
        
        if weekday >= 0 and weekday <= 4:
            if 21 <= hour or hour < 4:
                market_status = "🌞 Regular Hours"
            elif 4 <= hour < 9:
                market_status = "🌙 Pre-Market"
            elif 16 <= hour < 21:
                market_status = "🌙 After-Hours"
            else:
                market_status = "🌙 24H Trading"
        else:
            market_status = "🌙 24H Trading"
        
        if auto_updated_count > 0:
            status_text = f"🔄 Auto-updated {auto_updated_count} symbols | 🌐 {market_status}"
        else:
            status_text = f"✅ All prices current | 🌐 {market_status}"
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
    portfolio_sorted = sorted(portfolio, key=lambda x: x['market_value'] / total_value, reverse=True)
    
    portfolio_data = []
    
    for position in portfolio_sorted:
        symbol = position['symbol']
        current_price = position['price']
        value_percent = (position['market_value'] / total_value * 100) if total_value > 0 else 0
        
        # Skip percentile calculation for now to speed up startup
        p5d = None
        p30d = None
        p3m = None
        
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
    totals_text = f"💰 Total: ${grand_total_usd:,.0f} USD (¥{grand_total_cny:,.0f} CNY) | 📊 Stocks: {stocks_pct:.0f}% Cash: {cash_pct:.0f}%"
    st.info(totals_text)

if __name__ == "__main__":
    main()