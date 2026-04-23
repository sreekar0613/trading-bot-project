import os
import sys
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient
from alpaca.data.historical import StockHistoricalDataClient

def test_alpaca_connection():
    """Test Alpaca API connection and display account details."""
    
    # Load environment variables
    load_dotenv()
    
    # Get API credentials
    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    
    # Validate credentials exist
    if not api_key or not secret_key:
        print("❌ Error: ALPACA_API_KEY or ALPACA_SECRET_KEY not found in .env file")
        sys.exit(1)
    
    try:
        # Initialize Trading Client (for orders/positions)
        trading_client = TradingClient(
            api_key=api_key,
            secret_key=secret_key,
            paper=True  # Paper trading mode
        )
        print("✓ Trading client initialized")
        
        # Initialize Data Client (for historical price data)
        data_client = StockHistoricalDataClient(
            api_key=api_key,
            secret_key=secret_key
        )
        print("✓ Data client initialized")
        
        # Fetch account information
        account = trading_client.get_account()
        print("✓ Alpaca API connection successful\n")
        
        # Display account details
        print("Account Details:")
        print(f"  Portfolio Value: ${float(account.portfolio_value):,.2f}")
        print(f"  Buying Power: ${float(account.buying_power):,.2f}")
        print(f"  Cash: ${float(account.cash):,.2f}")
        print(f"  Equity: ${float(account.equity):,.2f}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Connection failed: {str(e)}")
        print("\nTroubleshooting:")
        print("  1. Verify API keys in .env file are correct")
        print("  2. Check internet connection")
        print("  3. Confirm Alpaca API status at https://status.alpaca.markets/")
        sys.exit(1)

if __name__ == "__main__":
    test_alpaca_connection()