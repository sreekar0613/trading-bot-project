import os
from dotenv import load_dotenv
from alpaca.trading.client import TradingClient

load_dotenv()

_client: TradingClient | None = None


def get_trading_client() -> TradingClient:
    global _client
    if _client is None:
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")
        if not api_key or not secret_key:
            raise RuntimeError("ALPACA_API_KEY and ALPACA_SECRET_KEY must be set in .env")
        _client = TradingClient(api_key, secret_key, paper=True)
    return _client


def fetch_account() -> dict:
    client = get_trading_client()
    acct = client.get_account()
    return {
        "portfolio_value": float(acct.portfolio_value),
        "buying_power": float(acct.buying_power),
        "cash": float(acct.cash),
        "equity": float(acct.equity),
        "last_equity": float(acct.last_equity),
    }


def fetch_positions() -> list[dict]:
    client = get_trading_client()
    positions = client.get_all_positions()
    return [
        {
            "symbol": p.symbol,
            "qty": float(p.qty),
            "avg_entry_price": float(p.avg_entry_price),
            "current_price": float(p.current_price),
            "market_value": float(p.market_value),
            "unrealized_pl": float(p.unrealized_pl),
        }
        for p in positions
    ]
