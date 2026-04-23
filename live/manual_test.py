import os
import sys
import time
import logging
from dotenv import load_dotenv

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

# Setup logging
LOG_FILE = "logs/paper_trading.log"
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stdout)]
)

def main():
    load_dotenv()
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    
    if not api_key or not secret_key:
        logging.error("Alpaca API keys missing in .env")
        return
        
    trading_client = TradingClient(api_key, secret_key, paper=True)
    
    symbol = "AAPL"
    qty = 0.1
    
    logging.info(f"Starting Round Trip Test for {qty} shares of {symbol}")
    
    # 1. Buy Order
    try:
        buy_req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY
        )
        buy_order = trading_client.submit_order(buy_req)
        logging.info(f"BUY Order Submitted: ID={buy_order.id}, Status={buy_order.status}")
    except Exception as e:
        logging.error(f"Failed to submit BUY order: {e}")
        return
        
    # Wait for fill
    logging.info("Waiting 5 seconds for order fill...")
    time.sleep(5)
    
    # 2. Check Positions
    try:
        positions = trading_client.get_all_positions()
        found = False
        for p in positions:
            if p.symbol == symbol:
                logging.info(f"Confirmed Position: {p.qty} shares of {p.symbol} at avg entry ${p.avg_entry_price}")
                found = True
        if not found:
            logging.warning(f"Position for {symbol} not found! Order might still be pending.")
    except Exception as e:
        logging.error(f"Failed to fetch positions: {e}")
        
    # 3. Sell Order
    try:
        sell_req = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
        sell_order = trading_client.submit_order(sell_req)
        logging.info(f"SELL Order Submitted: ID={sell_order.id}, Status={sell_order.status}")
    except Exception as e:
        logging.error(f"Failed to submit SELL order: {e}")
        
    logging.info("Round Trip Test Completed")

if __name__ == "__main__":
    main()