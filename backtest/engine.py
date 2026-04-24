import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = REPO_ROOT / "trading_bot.db"
SIGNALS_PATH = REPO_ROOT / "backtest" / "signals_log.csv"
REPORTS_DIR = REPO_ROOT / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

def run_backtest():
    print("Initializing Backtest Engine...")
    
    # 1. Load Data
    signals_df = pd.read_csv(SIGNALS_PATH)
    if signals_df.empty:
        print("No signals found in signals_log.csv")
        return
        
    signals_df['date'] = pd.to_datetime(signals_df['date'])
    
    conn = sqlite3.connect(DB_PATH)
    
    # Load fundamental universe for sector mapping
    funds_df = pd.read_sql_query("SELECT symbol, sector FROM fundamental_universe", conn)
    sector_map = dict(zip(funds_df['symbol'], funds_df['sector']))
    all_sectors = set(sector_map.values())
    
    # Load price history to get all trading dates and daily close prices
    prices_query = "SELECT symbol, date, close FROM price_history WHERE date >= '2020-07-01' AND date <= '2024-12-31'"
    prices_raw = pd.read_sql_query(prices_query, conn)
    prices_raw['date'] = pd.to_datetime(prices_raw['date'])
    conn.close()
    
    # Create a pivot table of prices: index=date, columns=symbol, values=close
    prices_df = prices_raw.pivot(index='date', columns='symbol', values='close')
    trading_dates = prices_df.index.sort_values()
    
    # 2. Setup Portfolio State
    initial_capital = 1100.0
    cash = initial_capital
    open_positions = {}  # symbol -> {qty, entry_price, entry_date, sector}
    equity_curve = []
    trade_history = []
    
    print(f"Running simulation from {trading_dates[0].strftime('%Y-%m-%d')} to {trading_dates[-1].strftime('%Y-%m-%d')}...")
    
    # 3. Execution Loop
    for date in trading_dates:
        current_prices = prices_df.loc[date]
        
        # Step A: Exits
        daily_exit_signals = signals_df[(signals_df['date'] == date) & (signals_df['signal_type'] == 'exit')]
        for _, row in daily_exit_signals.iterrows():
            symbol = row['symbol']
            if symbol in open_positions:
                exit_price = current_prices.get(symbol, row['price'])
                if pd.isna(exit_price):
                    exit_price = row['price']
                
                pos = open_positions.pop(symbol)
                qty = pos['qty']
                cash += qty * exit_price
                
                pnl_dollar = (exit_price - pos['entry_price']) * qty
                pnl_pct = (exit_price / pos['entry_price'] - 1) * 100
                
                trade_history.append({
                    'Entry Date': pos['entry_date'].strftime('%Y-%m-%d'),
                    'Exit Date': date.strftime('%Y-%m-%d'),
                    'Ticker': symbol,
                    'PnL %': pnl_pct,
                    'PnL $': pnl_dollar,
                    'Entry Price': pos['entry_price'],
                    'Exit Price': exit_price
                })
                
        # Step B: Equity Update
        portfolio_value = cash
        sector_exposure = {sector: 0.0 for sector in all_sectors}
        
        for sym, pos in open_positions.items():
            price = current_prices.get(sym)
            if pd.isna(price):
                price = pos['entry_price']
                
            val = pos['qty'] * price
            portfolio_value += val
            sector_exposure[pos['sector']] = sector_exposure.get(pos['sector'], 0.0) + val
            
        equity_curve.append({'Date': date.strftime('%Y-%m-%d'), 'Equity': portfolio_value, 'Cash': cash})
        
        # Step C: Entries
        daily_entry_signals = signals_df[(signals_df['date'] == date) & (signals_df['signal_type'] == 'entry')]
        for _, row in daily_entry_signals.iterrows():
            symbol = row['symbol']
            if symbol not in open_positions and len(open_positions) < 15:
                sector = sector_map.get(symbol, 'Unknown')
                current_price = current_prices.get(symbol, row['price'])
                atr = row['atr']
                
                if pd.isna(current_price) or current_price == 0 or pd.isna(atr) or atr == 0:
                    continue
                    
                # Check current sector exposure
                current_sector_val = sector_exposure.get(sector, 0.0)
                if (current_sector_val / portfolio_value) >= 0.25:
                    continue
                    
                # Position Sizing
                risk_amount = portfolio_value * 0.025
                stop_distance = atr * 2.5
                qty = risk_amount / stop_distance
                
                # Hard Cap: max 15% of equity
                if (qty * current_price) > (portfolio_value * 0.15):
                    qty = (portfolio_value * 0.15) / current_price
                    
                # Sector Limit: new pos + existing <= 25%
                max_additional_sector_val = (portfolio_value * 0.25) - current_sector_val
                if max_additional_sector_val <= 0:
                    continue
                if (qty * current_price) > max_additional_sector_val:
                    qty = max_additional_sector_val / current_price
                    
                # Cash Check
                if (qty * current_price) > cash:
                    qty = cash / current_price
                    
                if qty > 0:
                    cost = qty * current_price
                    cash -= cost
                    open_positions[symbol] = {
                        'qty': qty,
                        'entry_price': current_price,
                        'entry_date': date,
                        'sector': sector
                    }
                    sector_exposure[sector] = sector_exposure.get(sector, 0.0) + cost
                    
    # Force close any remaining positions at the end of the backtest
    last_date = trading_dates[-1]
    last_prices = prices_df.loc[last_date]
    for symbol, pos in list(open_positions.items()):
        exit_price = last_prices.get(symbol, pos['entry_price'])
        if pd.isna(exit_price):
            exit_price = pos['entry_price']
            
        qty = pos['qty']
        cash += qty * exit_price
        
        pnl_dollar = (exit_price - pos['entry_price']) * qty
        pnl_pct = (exit_price / pos['entry_price'] - 1) * 100
        
        trade_history.append({
            'Entry Date': pos['entry_date'].strftime('%Y-%m-%d'),
            'Exit Date': last_date.strftime('%Y-%m-%d'),
            'Ticker': symbol,
            'PnL %': pnl_pct,
            'PnL $': pnl_dollar,
            'Entry Price': pos['entry_price'],
            'Exit Price': exit_price
        })
        
    # Update last equity curve entry
    equity_curve[-1]['Equity'] = cash
    equity_curve[-1]['Cash'] = cash
    
    # 4. Metrics Calculation
    equity_df = pd.DataFrame(equity_curve)
    equity_df['Date'] = pd.to_datetime(equity_df['Date'])
    equity_df.set_index('Date', inplace=True)
    
    equity_df['Return'] = equity_df['Equity'].pct_change()
    mean_return = equity_df['Return'].mean()
    std_return = equity_df['Return'].std()
    sharpe_ratio = (mean_return / std_return) * np.sqrt(252) if std_return != 0 else 0.0
    
    equity_df['Peak'] = equity_df['Equity'].cummax()
    equity_df['Drawdown'] = (equity_df['Equity'] - equity_df['Peak']) / equity_df['Peak']
    max_drawdown = equity_df['Drawdown'].min() * 100
    
    final_equity = equity_df['Equity'].iloc[-1]
    total_return = ((final_equity / initial_capital) - 1) * 100
    
    trades_df = pd.DataFrame(trade_history)
    if not trades_df.empty:
        gross_profit = trades_df[trades_df['PnL $'] > 0]['PnL $'].sum()
        gross_loss = abs(trades_df[trades_df['PnL $'] < 0]['PnL $'].sum())
        profit_factor = gross_profit / gross_loss if gross_loss != 0 else float('inf')
        win_rate = (len(trades_df[trades_df['PnL $'] > 0]) / len(trades_df)) * 100
    else:
        profit_factor = 0.0
        win_rate = 0.0
        
    # 5. Output
    print("\n" + "="*40)
    print("BACKTEST SUMMARY TABLE")
    print("="*40)
    print(f"Initial Capital : ${initial_capital:,.2f}")
    print(f"Final Equity    : ${final_equity:,.2f}")
    print(f"Total Return    : {total_return:.2f}%")
    print(f"Max Drawdown    : {max_drawdown:.2f}%")
    print(f"Sharpe Ratio    : {sharpe_ratio:.2f}")
    print(f"Profit Factor   : {profit_factor:.2f}")
    print(f"Win Rate        : {win_rate:.2f}%")
    print(f"Total Trades    : {len(trades_df)}")
    print("="*40)
    
    if not trades_df.empty:
        print("\n--- First 5 Executed Trades ---")
        # Format PnL for display
        display_df = trades_df.copy()
        display_df['PnL %'] = display_df['PnL %'].map('{:.2f}%'.format)
        display_df['PnL $'] = display_df['PnL $'].map('${:.2f}'.format)
        display_df['Entry Price'] = display_df['Entry Price'].map('${:.2f}'.format)
        display_df['Exit Price'] = display_df['Exit Price'].map('${:.2f}'.format)
        print(display_df[['Entry Date', 'Exit Date', 'Ticker', 'PnL %', 'PnL $']].head(5).to_string())
        
    # Save reports
    results_path = REPORTS_DIR / "backtest_results.csv"
    curve_path = REPORTS_DIR / "equity_curve.csv"
    
    trades_df.to_csv(results_path, index=False)
    equity_df.reset_index().to_csv(curve_path, index=False)
    
    print(f"\n✓ Saved trade log to {results_path}")
    print(f"✓ Saved equity curve to {curve_path}")

if __name__ == "__main__":
    run_backtest()
