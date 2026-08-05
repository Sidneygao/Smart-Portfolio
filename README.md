# Smart Portfolio Tracker

A personal portfolio tracking web application with real-time stock analysis, price alerts, and automatic cost calculations.

## Features

- **Real-time Stock Data**: Fetches current prices and 3 months of history for the whole portfolio in a single batched Yahoo Finance request (typically under a second)
- **Percentile Analysis**: Shows where the current price ranks within the actual closing prices of:
  - Past 5 trading days
  - Past month (21 trading days)
  - Past 3 months (63 trading days)
- **Price Alerts**: Automatic alerts for:
  - 5% price movements (up/down)
  - Volume spikes (2x average volume)
- **Portfolio Management**: 
  - Add new positions
  - Remove positions
  - Automatic average cost calculation when adding to existing positions
- **Multi-Currency Support**: 
  - Tracks portfolio in USD
  - Automatically converts total to CNY using current exchange rates
  - HKD cash holdings with automatic USD/CNY conversion
- **Multi-Client Cash Management**:
  - Track cash holdings for multiple clients
  - Support for USD and HKD currencies
  - Automatic currency conversion for total portfolio calculation
  - Per-client total asset breakdown
- **Auto-refresh**: Optional 30-second auto-refresh for real-time monitoring

## Setup Instructions

### Prerequisites

- Python 3.7 or higher
- pip (Python package manager)

### Installation

1. **Install Xcode Command Line Tools** (required for some Python packages):
   ```bash
   xcode-select --install
   ```

2. **Navigate to the project directory**:
   ```bash
   cd smart-portfolio
   ```

3. **Install required packages**:
   ```bash
   pip3 install -r requirements.txt
   ```

   Or install individually:
   ```bash
   pip3 install streamlit yfinance pandas numpy requests
   ```

### Optional: Twelve Data fallback

If Yahoo Finance has no data for a symbol, the app can try Twelve Data. Set your key
before starting the app; without it the symbol is simply reported as unavailable:

```bash
export TWELVE_DATA_API_KEY=your_key_here
```

### Running the Application

Start the Streamlit application:
```bash
streamlit run app.py
```

The application will open in your default web browser at `http://localhost:8501`

## Usage

### Initial Setup

The application comes pre-loaded with your portfolio data from `portfolio.json`. Your existing positions include:
- AAPL, TSM, QCOM, AMD, PLTR, ORCL, AVGO, NXPI, MU, COHR, MSFT, FN, SNPS

### Adding New Positions

1. In the sidebar, enter the stock symbol (e.g., "NVDA")
2. Enter the number of shares
3. Enter the purchase price
4. Click "Add Position"

**Note**: If the symbol already exists in your portfolio, the system will automatically calculate the new average cost basis.

### Removing Positions

1. In the sidebar, select the symbol you want to remove
2. Click "Remove Position"

### Managing Cash Holdings

1. In the sidebar, find the "Cash Holdings" section
2. For each client (AZHU and ANIU):
   - Enter USD cash amount
   - Enter HKD cash amount
3. Click "Save Cash Holdings" to update the data

The system automatically:
- Converts HKD to USD using current exchange rates
- Calculates total cash value in both USD and CNY
- Includes cash holdings in the grand total portfolio calculation
- Shows per-client asset breakdown assuming 50% stock allocation

### Monitoring Price Alerts

The system automatically displays alerts when:
- A stock moves 5% or more from the previous close
- Trading volume is 2x or higher than the 3-month average

### Understanding Percentile Analysis

The percentile columns show where the current price falls within the closing prices of the period:
- **0%**: Price is at the lowest point in the period
- **50%**: Price is at the median
- **100%**: Price is at the highest point in the period

For example, if "5D %" shows 75%, the current price is higher than 75% of the closes of the last 5 trading days.

## Total Portfolio Calculation

The grand total portfolio includes:

1. **Stock Holdings**: Sum of all stock market values
2. **Cash Holdings**: 
   - Client 1: USD + HKD (converted to USD)
   - Client 2: USD + HKD (converted to USD)
3. **Currency Conversion**:
   - HKD is automatically converted to USD using current exchange rates
   - All totals are shown in both USD and CNY

**Per-Client Breakdown**: The system assumes stocks are shared equally (50% each) and shows each client's total assets including their share of stocks plus their individual cash holdings.

## Understanding Percentile Analysis

The percentile columns show where the current price falls within the closing prices of the period:
- **0%**: Price is at the lowest point in the period
- **50%**: Price is at the median
- **100%**: Price is at the highest point in the period

For example, if "5D %" shows 75%, the current price is higher than 75% of the closes of the last 5 trading days.

## File Structure

```
smart-portfolio/
├── app.py              # Main Streamlit application
├── portfolio.json      # Stock portfolio data storage (symbol, shares, avg cost only)
├── stock_cache.json    # Local price/history cache, 1 hour TTL (git-ignored)
├── client_cash.json    # Client cash holdings data (USD & HKD)
├── requirements.txt    # Python dependencies
└── README.md          # This file
```

## Data Storage

**Stock Portfolio**: Stored in `portfolio.json`. Automatically updated when you:
- Add new positions
- Remove positions
- The application refreshes stock data

**Cash Holdings**: Stored in `client_cash.json`. Automatically updated when you:
- Modify cash amounts in the sidebar
- Click "Save Cash Holdings"

The cash file structure:
```json
{
  "azhu": {
    "name": "AZHU",
    "usd": 0,
    "hkd": 0
  },
  "aniu": {
    "name": "ANIU", 
    "usd": 0,
    "hkd": 0
  }
}
```

## Troubleshooting

### "No module named 'streamlit'" error
Make sure you installed the required packages:
```bash
pip3 install -r requirements.txt
```

### Stock data not loading
- Check your internet connection
- Some stocks may have limited data availability
- Try clicking the "Refresh Data" button

### Exchange rate not updating
The application uses a public API for USD to CNY conversion. If it fails, it falls back to a fixed rate of 7.2.

## Security Notes

- This application runs locally on your machine
- Portfolio data is stored locally in JSON format
- No data is sent to external servers except for:
  - Stock price data (Yahoo Finance API)
  - Exchange rates (public API)

## Future Enhancements

Potential features for future versions:
- Historical portfolio performance charts
- Dividend tracking
- Sector allocation analysis
- Export to Excel/CSV
- Mobile-responsive design improvements
- Custom alert thresholds
- Multiple portfolio support