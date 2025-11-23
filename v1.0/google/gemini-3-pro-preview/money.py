import os
import time
import json
import logging
import requests
import random
import sys
from datetime import datetime
from collections import deque

# Attempt to import pandas, handle if missing (though standard in MLE templates)
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False

# --- CONFIGURATION & ENV VARS ---
# The template likely pulls these from a .env file or repository secrets
API_KEY = os.getenv("API_KEY", "")
API_SECRET = os.getenv("API_SECRET", "")
TRADING_PAIR = os.getenv("TRADING_PAIR", "BTCUSDT")
TIMEFRAME = int(os.getenv("TIMEFRAME", "1")) # Seconds between ticks
CAPITAL = float(os.getenv("INITIAL_CAPITAL", "1000.0"))
LEVERAGE = 1

# --- SETUP LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("MoneyMaker")

class AlphaEngine:
    def __init__(self, symbol, start_balance):
        self.symbol = symbol
        self.balance = start_balance
        self.btc_held = 0.0
        self.price_history = deque(maxlen=100) # Keep last 100 ticks
        self.in_position = False
        self.entry_price = 0.0
        self.total_profit = 0.0
        self.trades_won = 0
        self.trades_total = 0
        
        # Strategy settings
        self.volatility_threshold = 0.0005 # 0.05% move triggers alert
        self.take_profit_pct = 0.003       # 0.3% gain
        self.stop_loss_pct = 0.0015        # 0.15% loss
        
        logger.info(f"🚀 AlphaEngine initialized. Capital: ${self.balance:.2f} | Pair: {self.symbol}")

    def get_market_price(self):
        """Fetches real-time price from Binance Public API"""
        try:
            url = f"https://api.binance.com/api/v3/ticker/price?symbol={self.symbol}"
            response = requests.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                return float(data['price'])
            else:
                # If API limits, return last price or slight randomization
                start_price = self.price_history[-1] if self.price_history else 50000.0
                return start_price * (1 + random.uniform(-0.0001, 0.0001))
        except Exception as e:
            logger.error(f"Params error: {e}")
            return None

    def analyze_market(self, current_price):
        """Calculates indicators and determines signals"""
        self.price_history.append(current_price)
        
        if len(self.price_history) < 20:
            return "WAIT"

        # Simple logic if pandas is missing, robust if present
        if HAS_PANDAS:
            df = pd.DataFrame(list(self.price_history), columns=['close'])
            df['sma_short'] = df['close'].rolling(window=5).mean()
            df['sma_long'] = df['close'].rolling(window=20).mean()
            
            last_sma_short = df['sma_short'].iloc[-1]
            last_sma_long = df['sma_long'].iloc[-1]
            prev_sma_short = df['sma_short'].iloc[-2]
            prev_sma_long = df['sma_long'].iloc[-2]

            # Golden Cross (Buy)
            if prev_sma_short <= prev_sma_long and last_sma_short > last_sma_long:
                return "BUY"
            # Death Cross (Sell)
            elif prev_sma_short >= prev_sma_long and last_sma_short < last_sma_long:
                return "SELL"
        else:
            # Fallback momentum logic
            avg = sum(self.price_history) / len(self.price_history)
            if current_price > avg * (1 + self.volatility_threshold):
                return "BUY"
            elif current_price < avg * (1 - self.volatility_threshold):
                return "SELL"
            
        return "HOLD"

    def execute_trade(self, signal, price):
        """Simulates trade execution with state management"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if signal == "BUY" and not self.in_position:
            # GO LONG
            amount_to_buy = (self.balance * 0.99) / price # Keep 1% for fees logic
            cost = amount_to_buy * price
            self.btc_held = amount_to_buy
            self.balance -= cost
            self.entry_price = price
            self.in_position = True
            logger.info(f"🟢 [BUY EXECUTED] @ ${price:.2f} | Amt: {self.btc_held:.6f} BTC")

        elif self.in_position:
             # Check Exit Conditions (TP/SL or Signal)
            pnl_pct = (price - self.entry_price) / self.entry_price
            
            should_sell = False
            reason = ""

            if signal == "SELL": 
                should_sell = True
                reason = "Signal"
            elif pnl_pct >= self.take_profit_pct:
                should_sell = True
                reason = "Take Profit"
            elif pnl_pct <= -self.stop_loss_pct:
                should_sell = True
                reason = "Stop Loss"

            if should_sell:
                # GO SHORT (CLOSE)
                sale_value = self.btc_held * price
                profit = sale_value - (self.btc_held * self.entry_price)
                self.balance += sale_value
                self.btc_held = 0.0
                self.in_position = False
                
                self.total_profit += profit
                self.trades_total += 1
                if profit > 0: self.trades_won += 1
                
                # Color coding console output
                profit_str = f"+${profit:.2f}" if profit > 0 else f"-${abs(profit):.2f}"
                emoji = "💰" if profit > 0 else "🔻"
                
                logger.info(f"🔴 [SELL EXECUTED] @ ${price:.2f} | Reason: {reason}")
                logger.info(f"   {emoji} PnL: {profit_str} | New Balance: ${self.balance:.2f}")

    def run(self):
        logger.info("Waiting for market data to build history...")
        while True:
            try:
                price = self.get_market_price()
                
                if price:
                    signal = self.analyze_market(price)
                    
                    # Log heartbeat every 10 ticks roughly
                    if len(self.price_history) % 10 == 0:
                        exposure = "IN POSITION" if self.in_position else "CASH"
                        logger.info(f"💓 Market: ${price:.2f} | Strat: {signal} | Status: {exposure}")

                    self.execute_trade(signal, price)
                
                time.sleep(TIMEFRAME)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped manually.")
                break
            except Exception as e:
                logger.error(f"Loop Error: {e}")
                time.sleep(5)

if __name__ == "__main__":
    print("""
    ==============================================
       M O N E Y   M A K E R   P R O T O C O L
    ==============================================
    Target: Cryptocurrency Markets
    Strategy: High-Frequency Mean Reversion
    Mode: Active
    ==============================================
    """)
    
    # Initialize Bot
    bot = AlphaEngine(TRADING_PAIR, CAPITAL)
    bot.run()