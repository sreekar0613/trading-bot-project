import os
import sys
import csv
import logging
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Setup logging
LOG_FILE = "logs/paper_trading.log"
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]
)

from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# Import indicators
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.append(str(REPO_ROOT))
from indicators.technical import (
    calculate_rsi, calculate_macd, calculate_bollinger, calculate_ema, calculate_atr
)

def load_sectors():
    sectors = {}
    csv_path = REPO_ROOT / 'reports' / 'universe_summary.csv'
    if csv_path.exists():
        with open(csv_path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sectors[row['symbol']] = row['sector']
    return sectors

def main():
    load_dotenv()
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    
    if not api_key or not secret_key:
        logging.error("Alpaca API keys missing in .env")
        return
        
    trading_client = TradingClient(api_key, secret_key, paper=True)
    data_client = StockHistoricalDataClient(api_key, secret_key)
    
    account = trading_client.get_account()
    equity = float(account.equity)
    logging.info(f"Dry Run Started. Current Equity: ${equity:,.2f}")
    
    tickers = ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "JPM", "V"]
    sectors = load_sectors()
    
    # Calculate current sector exposure
    positions = trading_client.get_all_positions()
    sector_exposure = {}
    for p in positions:
        sym = p.symbol
        val = float(p.market_value)
        sec = sectors.get(sym, 'UNKNOWN')
        sector_exposure[sec] = sector_exposure.get(sec, 0.0) + val
        
    # Fetch data (365 calendar days to ensure 250+ trading days for EMA200)
    end_time = datetime.now()
    start_time = end_time - timedelta(days=365)
    
    request = StockBarsRequest(
        symbol_or_symbols=tickers,
        timeframe=TimeFrame.Day,
        start=start_time,
        end=end_time
    )
    
    try:
        bars = data_client.get_stock_bars(request)
    except Exception as e:
        logging.error(f"Failed to fetch data: {e}")
        return
        
    if bars.df.empty:
        logging.error("No historical data returned.")
        return
        
    results = []
    
    for symbol in tickers:
        try:
            df = bars.df.loc[symbol].copy()
        except KeyError:
            results.append((symbol, "NO DATA", 0, "Not enough data"))
            continue
            
        if len(df) < 200:
            results.append((symbol, "NO SIGNAL", 0, "Not enough data for EMA200"))
            continue
            
        # Calculate indicators
        rsi = calculate_rsi(df['close'])
        macd_data = calculate_macd(df['close'])
        bb_data = calculate_bollinger(df['close'])
        ema200 = calculate_ema(df['close'], period=200)
        atr = calculate_atr(df['high'], df['low'], df['close'])
        
        df['rsi'] = rsi
        df['macd_hist'] = macd_data['histogram']
        df['bb_lower'] = bb_data['lower']
        df['ema200'] = ema200
        df['atr'] = atr
        
        if len(df) < 10:
            results.append((symbol, "NO SIGNAL", 0, "Not enough data for 10-day lookback"))
            continue
            
        last_10 = df.iloc[-10:]
        current = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Conditions
        macd_trigger = (current['macd_hist'] > 0) and (prev['macd_hist'] <= 0)
        rsi_context = (last_10['rsi'] < 35).any()
        bb_context = (last_10['close'] < last_10['bb_lower']).any()
        trend_filter = current['close'] > current['ema200']
        
        if not trend_filter:
            results.append((symbol, "NO SIGNAL", 0, "Price below EMA(200)"))
            continue
        if not rsi_context:
            results.append((symbol, "NO SIGNAL", 0, "RSI not < 35 in last 10 days"))
            continue
        if not bb_context:
            results.append((symbol, "NO SIGNAL", 0, "Price not < Lower BB in last 10 days"))
            continue
        if not macd_trigger:
            results.append((symbol, "NO SIGNAL", 0, "No MACD crossover today"))
            continue
            
        # If we reach here, it's a BUY signal
        price = current['close']
        atr_val = current['atr']
        
        risk_amount = equity * 0.025
        stop_distance = atr_val * 2.5
        
        if stop_distance <= 0:
            results.append((symbol, "ERROR", 0, "Invalid ATR"))
            continue
            
        share_qty = risk_amount / stop_distance
        pos_size = share_qty * price
        
        # Hard cap 15%
        if pos_size > equity * 0.15:
            pos_size = equity * 0.15
            
        # Sector check
        sec = sectors.get(symbol, 'UNKNOWN')
        current_sec_exp = sector_exposure.get(sec, 0.0)
        
        if current_sec_exp + pos_size > equity * 0.25:
            # Scale down to meet sector limit or reject
            available_room = (equity * 0.25) - current_sec_exp
            if available_room <= 0:
                results.append((symbol, "REJECTED", 0, f"Sector limit exceeded ({sec})"))
                continue
            else:
                pos_size = min(pos_size, available_room)
                reason = f"BUY (Scaled due to {sec} limit)"
        else:
            reason = "BUY (Conditions met)"
            
        results.append((symbol, "BUY", pos_size, reason))
        
    print("\n" + "="*80)
    print(f"{'Ticker':<8} | {'Signal':<10} | {'Position Size ($)':<18} | {'Reason'}")
    print("-" * 80)
    for res in results:
        pos_str = f"${res[2]:,.2f}" if res[2] > 0 else "-"
        print(f"{res[0]:<8} | {res[1]:<10} | {pos_str:<18} | {res[3]}")
        logging.info(f"Dry Run Result: {res[0]} - {res[1]} - {pos_str} - {res[3]}")
    print("="*80 + "\n")

if __name__ == "__main__":
    main()