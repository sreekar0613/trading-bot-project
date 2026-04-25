import sqlite3
from pathlib import Path
import pandas as pd
import numpy as np
import yfinance as yf
from indicators.technical import (
    calculate_rsi,
    calculate_macd,
    calculate_bollinger,
    calculate_ema,
    calculate_atr,
    load_price_history
)
from strategy.regime import MarketRegimeDetector

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "trading_bot.db"

def generate_signals(symbol: str, start_date: str, end_date: str, regime_series: pd.Series = None) -> pd.DataFrame:
    """
    Generate entry and exit signals for a given symbol based on strategy rules.
    1. Entry (ALL must be true): RSI < 40, MACD crossover (>0), Close < Lower BB, Close > EMA200
    2. Exit (ANY triggers): Regime-aware dynamic parameters
    """
    # Load price data
    df = load_price_history(symbol, DB_PATH)
    if df.empty:
        return pd.DataFrame()
    
    # Calculate indicators
    df['rsi'] = calculate_rsi(df['close'])
    macd_res = calculate_macd(df['close'])
    df['macd_hist'] = macd_res['histogram']
    bb_res = calculate_bollinger(df['close'])
    df['bb_lower'] = bb_res['lower']
    df['ema200'] = calculate_ema(df['close'], period=200)
    df['atr'] = calculate_atr(df['high'], df['low'], df['close'])
    
    # Context signals with 10-day lookback
    df['rsi_min_10'] = df['rsi'].rolling(window=10).min()
    df['price_below_bb'] = (df['close'] < df['bb_lower']).astype(int)
    df['bb_context_10'] = df['price_below_bb'].rolling(window=10).max()
    
    # Filter by requested date range (start_date to end_date)
    mask = (df.index >= pd.Timestamp(start_date)) & (df.index <= pd.Timestamp(end_date))
    process_df = df.loc[mask].copy()
    
    if process_df.empty:
        return pd.DataFrame()

    signals = []
    position_open = False
    entry_date = None
    entry_price = 0.0
    entry_atr = 0.0
    peak_price = 0.0
    
    # Iterate through days to handle conditional state-based exit logic
    for i in range(len(process_df)):
        current_date = process_df.index[i]
        row = process_df.iloc[i]
        
        # Get prior row from full df for MACD crossover check
        orig_idx = df.index.get_loc(current_date)
        if orig_idx == 0:
            continue
        prior_row = df.iloc[orig_idx - 1]
        
        if not position_open:
            # ENTRY LOGIC (Confluence Required)
            cond_rsi = row['rsi_min_10'] < 40
            cond_macd = (row['macd_hist'] > 0) and (prior_row['macd_hist'] <= 0)
            cond_bb = row['bb_context_10'] > 0
            cond_ema = row['close'] > row['ema200']
            
            # Ensure no NaNs in required indicators
            if pd.isna([row['rsi_min_10'], row['macd_hist'], prior_row['macd_hist'], row['bb_context_10'], row['ema200']]).any():
                continue
                
            if cond_rsi and cond_macd and cond_bb and cond_ema:
                position_open = True
                entry_date = current_date
                entry_price = row['close']
                entry_atr = row['atr']
                peak_price = row['close']
                
                reason = f"Entry: RSI context {row['rsi_min_10']:.1f}, MACD cross, BB context"
                signals.append({
                    'date': current_date,
                    'symbol': symbol,
                    'signal_type': 'entry',
                    'price': entry_price,
                    'atr': entry_atr,
                    'reason': reason,
                    'days_held': 0
                })
        else:
            # EXIT LOGIC (Any Condition Triggers)
            if row['close'] > peak_price:
                peak_price = row['close']
                
            atr_mult = 3.0
            rsi_exit = 65
            time_stop = 14
            
            if regime_series is not None:
                try:
                    # Match by exact date or nearest previous
                    # regime_series index is datetime
                    # We can use get_indexer with method='pad'
                    idx = regime_series.index.get_indexer([pd.Timestamp(current_date).tz_localize(None)], method='pad')[0]
                    if idx >= 0:
                        current_regime = regime_series.iloc[idx]
                        if current_regime == 0:
                            atr_mult = 2.5
                            rsi_exit = 75
                            time_stop = 7
                        elif current_regime == 1:
                            atr_mult = 1.5
                            rsi_exit = 55
                            time_stop = 3
                        # state 2 stays at defaults
                except Exception:
                    pass
                
            exit_reasons = []
            
            # 1. RSI Overbought
            if row['rsi'] > rsi_exit:
                exit_reasons.append(f"RSI {row['rsi']:.1f} > {rsi_exit}")
                
            # 2. Max Holding Period (calendar days)
            days_held = (current_date - entry_date).days
            if days_held >= time_stop:
                exit_reasons.append(f"{days_held} days elapsed (stop={time_stop})")
                
            # 3. Trailing Stop
            if (peak_price - row['close']) > (atr_mult * entry_atr):
                exit_reasons.append(f"Trailing stop {atr_mult}x (Peak: {peak_price:.2f}, Drop: {peak_price - row['close']:.2f})")
                
            if exit_reasons:
                signals.append({
                    'date': current_date,
                    'symbol': symbol,
                    'signal_type': 'exit',
                    'price': row['close'],
                    'atr': row['atr'],
                    'reason': "Exit: " + " + ".join(exit_reasons),
                    'days_held': days_held
                })
                position_open = False
                entry_date = None
                entry_price = 0.0
                entry_atr = 0.0
                peak_price = 0.0
                
    return pd.DataFrame(signals)

def scan_universe(start_date: str = '2020-07-01', end_date: str = '2024-12-31') -> pd.DataFrame:
    """
    Query fundamental_universe for qualified tickers and scan each for signals.
    """
    conn = sqlite3.connect(DB_PATH)
    # Get only tickers in the fundamental_universe as per pre-screening requirement
    tickers_df = pd.read_sql_query("SELECT symbol FROM fundamental_universe", conn)
    conn.close()
    
    print("Fitting regime model on SPY...")
    try:
        spy_df = yf.download('SPY', start='2010-01-01', end=end_date, progress=False)
        # Flatten multiindex columns if needed
        if isinstance(spy_df.columns, pd.MultiIndex):
            spy_df.columns = spy_df.columns.get_level_values(0)
        detector = MarketRegimeDetector()
        regime_series = detector.predict_all(spy_df)
        detector.save()
        print("Regime model fitted and saved.")
    except Exception as e:
        print(f"Warning: Failed to fit regime model: {e}")
        regime_series = None
    
    all_signals = []
    for symbol in tickers_df['symbol']:
        sig_df = generate_signals(symbol, start_date, end_date, regime_series)
        if not sig_df.empty:
            all_signals.append(sig_df)
            
    if not all_signals:
        return pd.DataFrame()
        
    combined = pd.concat(all_signals)
    combined = combined.sort_values(by=['date', 'symbol']).reset_index(drop=True)
    return combined

if __name__ == "__main__":
    print("Generating signals for qualified universe (2020-2024)...")
    signals_log = scan_universe()
    
    # Save to CSV in backtest directory
    output_path = REPO_ROOT / "backtest" / "signals_log_relaxed.csv"
    signals_log.to_csv(output_path, index=False)
    print(f"✓ Signals saved to {output_path}")
    
    if not signals_log.empty:
        print("\n--- First 10 Signals ---")
        print(signals_log.head(10).to_string())
        
        print("\n--- Summary Stats ---")
        summary = signals_log.groupby(['symbol', 'signal_type']).size().unstack(fill_value=0)
        print(summary.to_string())
        
        print("\n--- Example Complete Trade ---")
        tickers_with_exits = signals_log[signals_log['signal_type'] == 'exit']['symbol'].unique()
        if len(tickers_with_exits) > 0:
            target_symbol = tickers_with_exits[0]
            example_trade = signals_log[signals_log['symbol'] == target_symbol].head(2)
            print(example_trade.to_string())
        else:
            print("No complete trades (entry + exit) found.")
    else:
        print("\nNo signals generated.")
        print("Note: The strict confluence of RSI < 35 and MACD Crossover on the same day is extremely restrictive.")
