import os
import requests
import json
from dotenv import load_dotenv

def main():
    load_dotenv()
    api_key = os.getenv("FINNHUB_API_KEY")
    
    if not api_key:
        print("Error: FINNHUB_API_KEY not found in .env")
        return
        
    symbol = "AAPL"
    url = f"https://finnhub.io/api/v1/news-sentiment?symbol={symbol}&token={api_key}"
    
    print(f"Testing Finnhub News Sentiment for {symbol}...")
    
    try:
        response = requests.get(url)
        response.raise_for_status()
        data = response.json()
        
        print("\n--- Full JSON Response ---")
        print(json.dumps(data, indent=2))
        
        print("\n--- Sentiment Extraction ---")
        if 'sentiment' in data:
            sentiment = data['sentiment']
            print(f"Bearish Percent: {sentiment.get('bearishPercent', 'N/A')}")
            print(f"Bullish Percent: {sentiment.get('bullishPercent', 'N/A')}")
            print(f"Sector Average Bullish Percent: {sentiment.get('sectorAverageBullishPercent', 'N/A')}")
        else:
            print("Key 'sentiment' not found in response.")
            
    except requests.exceptions.RequestException as e:
        print(f"Request failed: {e}")
        
if __name__ == "__main__":
    main()