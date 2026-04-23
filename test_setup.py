from alpaca.trading.client import TradingClient
import finnhub
import requests
import os
from dotenv import load_dotenv

load_dotenv()

# Test Alpaca
try:
    client = TradingClient(
        api_key=os.getenv('ALPACA_API_KEY'),
        secret_key=os.getenv('ALPACA_SECRET_KEY'),
        paper=True
    )
    account = client.get_account()
    print(f"✓ Alpaca connection successful")
    print(f"  Portfolio Value: ${account.portfolio_value}")
except Exception as e:
    print(f"✗ Alpaca failed: {e}")

#  # Test Finnhub
#try:
#    finnhub_client = finnhub.Client(api_key=os.getenv('FINNHUB_API_KEY'))
#    sentiment = finnhub_client.news_sentiment('AAPL')
#    print(f"✓ Finnhub connection successful")
#    print(f"  AAPL Sentiment: {sentiment['companyNewsScore']:.3f}")
#except Exception as e:
#    print(f"✗ Finnhub failed: {e}")

# Test Alpha Vantage
try:
    url = "https://www.alphavantage.co/query"
    params = {
        'function': 'OVERVIEW',
        'symbol': 'AAPL',
        'apikey': os.getenv('ALPHA_VANTAGE_API_KEY')
    }
    response = requests.get(url, params=params)
    data = response.json()
    if 'Symbol' in data:
        print(f"✓ Alpha Vantage connection successful")
        print(f"  AAPL Market Cap: ${float(data['MarketCapitalization']):,.0f}")
    else:
        print(f"✗ Alpha Vantage error: {data.get('Note', 'Unknown error')}")
except Exception as e:
    print(f"✗ Alpha Vantage failed: {e}")
