import os
import logging
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame
from datetime import datetime, timedelta

# Configuration
load_dotenv()
LOG_FILE = "logs/paper_trading.log"
os.makedirs("logs", exist_ok=True)

# Centralized Logging for Phase 3
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

def test_connectivity():
    logging.info("--- Starting Alpaca Paper Connectivity Test ---")
    
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

    if not api_key or not secret_key:
        logging.error("API keys missing from .env file. Please verify ALPACA_API_KEY and ALPACA_SECRET_KEY.")
        return False

    try:
        # 1. Test Trading Client (Account Info)
        trading_client = TradingClient(api_key, secret_key, paper=True)
        account = trading_client.get_account()
        
        logging.info("✓ Trading Client: Successfully Connected")
        logging.info(f"  Account ID: {account.id}")
        logging.info(f"  Status: {account.status}")
        logging.info(f"  Portfolio Value: ${float(account.portfolio_value):,.2f}")
        logging.info(f"  Equity: ${float(account.equity):,.2f}")
        logging.info(f"  Buying Power: ${float(account.buying_power):,.2f}")
        
        if account.trading_blocked:
            logging.warning("! Warning: Trading is currently BLOCKED on this account.")
        else:
            logging.info("✓ Trading Status: Active")

        # 2. Test Data Client (Historical Bars)
        data_client = StockHistoricalDataClient(api_key, secret_key)
        request = StockBarsRequest(
            symbol_or_symbols="AAPL",
            timeframe=TimeFrame.Day,
            start=datetime.now() - timedelta(days=5)
        )
        bars = data_client.get_stock_bars(request)
        
        if bars:
            logging.info("✓ Data Client: Successfully retrieved test bar for AAPL")
        
        logging.info("--- Connectivity Test PASSED ---")
        return True

    except Exception as e:
        logging.error(f"✗ Connectivity Test FAILED: {str(e)}")
        logging.info("Troubleshooting Steps:")
        logging.info("  1. Verify the ALPACA_BASE_URL is set to the paper endpoint in your .env.")
        logging.info("  2. Ensure your internet connection is stable.")
        logging.info("  3. Confirm your Paper Trading keys are valid in the Alpaca Dashboard.")
        return False

if __name__ == "__main__":
    test_connectivity()