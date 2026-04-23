import os
import time
import logging
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

# Load Alpaca keys from .env
load_dotenv()

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# Import indicators
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))
from indicators.technical import (
    calculate_rsi, calculate_macd, calculate_bollinger, calculate_ema, calculate_atr
)

# Setup logging
logging.basicConfig(
    filename='logs/paper_trading.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class TradingBot:
    def __init__(self):
        self.api_key = os.getenv('ALPACA_API_KEY')
        self.secret_key = os.getenv('ALPACA_SECRET_KEY')
        
        if not self.api_key or not self.secret_key:
            logging.error("Alpaca API keys missing in .env")
            raise ValueError("Alpaca API keys are missing in .env file.")
            
        self.trading_client = TradingClient(self.api_key, self.secret_key, paper=True)
        self.data_client = StockHistoricalDataClient(self.api_key, self.secret_key)
        
        self.tickers = ["AAPL", "MSFT", "GOOGL", "NVDA", "META", "JPM", "V"]
        self.risk_per_trade = 0.025  # 2.5% risk per trade
        self.stop_loss_atr_multiplier = 2.5
        
        logging.info("Trading Bot initialized.")
        
    def check_market_hours(self) -> bool:
        """Only evaluate signals during market hours (9:30 AM - 4:00 PM ET)."""
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(eastern)
        
        # Check if it's weekend
        if now_et.weekday() >= 5:
            return False
            
        market_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now_et.replace(hour=16, minute=0, second=0, microsecond=0)
        
        return market_open <= now_et <= market_close

    def check_session_kill_switch(self):
        """If daily equity drops > 5% below last_equity, close all positions and exit."""
        account = self.trading_client.get_account()
        equity = float(account.equity)
        last_equity = float(account.last_equity)
        
        if last_equity > 0:
            daily_pl_pct = ((equity - last_equity) / last_equity) * 100
            logging.info(f"Current Daily P&L: {daily_pl_pct:.2f}%")
            
            if daily_pl_pct < -5.0:
                logging.critical(f"KILL SWITCH TRIGGERED! Daily P&L is {daily_pl_pct:.2f}% (exceeds -5%).")
                self.trading_client.cancel_orders()
                self.trading_client.close_all_positions(cancel_orders=True)
                logging.critical("All positions closed and orders cancelled. Exiting bot.")
                sys.exit(1)

    def fetch_historical_data(self, symbol: str, lookback_days: int = 300):
        """Fetch enough daily data to calculate EMA200 properly."""
        end_time = datetime.now()
        start_time = end_time - timedelta(days=lookback_days)
        
        request = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Day,
            start=start_time,
            end=end_time
        )
        
        bars = self.data_client.get_stock_bars(request)
        if bars.df.empty:
            return None
            
        # Bars come with MultiIndex (symbol, timestamp). Drop symbol level.
        df = bars.df.loc[symbol].copy()
        return df

    def calculate_position_size(self, price: float, atr_value: float) -> float:
        """Calculate position size: (Equity * 0.025) / (ATR * 2.5)"""
        account = self.trading_client.get_account()
        equity = float(account.equity)
        
        risk_amount = equity * self.risk_per_trade
        stop_distance = atr_value * self.stop_loss_atr_multiplier
        
        if stop_distance <= 0:
            return 0.0
            
        share_quantity = risk_amount / stop_distance
        
        # Hard cap: single position cannot exceed 15% of portfolio
        max_position_value = equity * 0.15
        if (share_quantity * price) > max_position_value:
            share_quantity = max_position_value / price
            
        return share_quantity

    def generate_signals(self):
        """Evaluate real-time signals for the defined tickers."""
        logging.info("Evaluating signals...")
        
        orders_to_place = []
        
        for symbol in self.tickers:
            df = self.fetch_historical_data(symbol)
            if df is None or len(df) < 200:
                logging.warning(f"Not enough data for {symbol}")
                continue
                
            # Calculate Indicators
            rsi = calculate_rsi(df['close'])
            macd_data = calculate_macd(df['close'])
            bb_data = calculate_bollinger(df['close'])
            ema200 = calculate_ema(df['close'], period=200)
            atr = calculate_atr(df['high'], df['low'], df['close'])
            
            # Combine into a single DataFrame for easier 10-day lookback
            out = df[['close']].copy()
            out['rsi'] = rsi
            out['macd'] = macd_data['macd']
            out['macd_signal'] = macd_data['signal']
            out['bb_lower'] = bb_data['lower']
            out['ema200'] = ema200
            out['atr'] = atr
            
            # We need the last 10 days context
            if len(out) < 10:
                continue
                
            last_10 = out.iloc[-10:]
            current = out.iloc[-1]
            prev = out.iloc[-2]
            
            # Context filters over the last 10 days
            rsi_oversold_recently = (last_10['rsi'] < 35).any()
            near_lower_bb_recently = (last_10['close'] < last_10['bb_lower'] * 1.01).any()
            
            # Current trigger filters
            uptrend = current['close'] > current['ema200']
            macd_cross_above = (prev['macd'] < prev['macd_signal']) and (current['macd'] > current['macd_signal'])
            
            if uptrend and rsi_oversold_recently and near_lower_bb_recently and macd_cross_above:
                logging.info(f"BUY Signal generated for {symbol}")
                
                # Position Sizing
                share_qty = self.calculate_position_size(current['close'], current['atr'])
                if share_qty > 0:
                    orders_to_place.append({
                        'symbol': symbol,
                        'qty': round(share_qty, 4), # Support fractional shares
                        'side': OrderSide.BUY
                    })
                    
        return orders_to_place

    def execute_orders(self, orders):
        """Submit queued orders."""
        for order_info in orders:
            try:
                order_req = MarketOrderRequest(
                    symbol=order_info['symbol'],
                    qty=order_info['qty'],
                    side=order_info['side'],
                    time_in_force=TimeInForce.DAY
                )
                self.trading_client.submit_order(order_req)
                logging.info(f"Executed Order: {order_info['side']} {order_info['qty']} shares of {order_info['symbol']}")
            except Exception as e:
                logging.error(f"Failed to submit order for {order_info['symbol']}: {str(e)}")

    def run_daily_checks(self):
        """Placeholder for 4:05 PM ET and 10:15 AM ET logic"""
        eastern = pytz.timezone('US/Eastern')
        now_et = datetime.now(eastern)
        
        # Placeholder logic: usually we would use schedule library to trigger this
        # E.g., if now_et.hour == 16 and now_et.minute == 5: generate signals
        # if now_et.hour == 10 and now_et.minute == 15: execute queued orders
        
        logging.info("Running daily checks placeholder...")
        pass

if __name__ == "__main__":
    bot = TradingBot()
    
    # Normally this would be part of a loop with schedule checking
    # schedule.every(5).minutes.do(bot.check_session_kill_switch)
    # schedule.every().day.at("16:05").do(bot.generate_signals)
    # schedule.every().day.at("10:15").do(bot.execute_orders)
    
    try:
        # Example flow for testing purposes:
        # bot.check_session_kill_switch()
        # if bot.check_market_hours():
        #     signals = bot.generate_signals()
        #     if signals:
        #         bot.execute_orders(signals)
        logging.info("Bot execution completed.")
    except Exception as e:
        logging.error(f"Bot encountered an error: {str(e)}")
