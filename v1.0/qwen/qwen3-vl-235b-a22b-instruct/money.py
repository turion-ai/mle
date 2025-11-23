#!/usr/bin/env python3
"""
Online Money Making Program - Crypto Arbitrage Bot
This program monitors cryptocurrency prices across multiple exchanges and executes arbitrage trades
when profitable opportunities are detected.
"""

import os
import time
import logging
import asyncio
import json
import requests
from datetime import datetime
from typing import Dict, List, Optional
from dataclasses import dataclass

# Import from the template repository
from mle import MLE
from mle.utils import get_env_var, setup_logging

# Set up logging
setup_logging()
logger = logging.getLogger(__name__)

# Environment variables (as defined in the template)
API_KEY = get_env_var("API_KEY", "")
SECRET_KEY = get_env_var("SECRET_KEY", "")
PASSPHRASE = get_env_var("PASSPHRASE", "")
EXCHANGE_API_URL = get_env_var("EXCHANGE_API_URL", "https://api.exchange.com/v1")
MAX_TRADE_AMOUNT = float(get_env_var("MAX_TRADE_AMOUNT", "100.0"))
MIN_PROFIT_MARGIN = float(get_env_var("MIN_PROFIT_MARGIN", "0.5"))  # 0.5%
CHECK_INTERVAL = int(get_env_var("CHECK_INTERVAL", "30"))  # seconds

@dataclass
class CryptoPrice:
    symbol: str
    price: float
    exchange: str
    timestamp: datetime

@dataclass
class ArbitrageOpportunity:
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: float
    sell_price: float
    profit_margin: float
    profit_amount: float
    volume: float

class CryptoArbitrageBot:
    def __init__(self):
        self.mle = MLE()
        self.prices: Dict[str, List[CryptoPrice]] = {}
        self.trading_pairs = ["BTC/USD", "ETH/USD", "BTC/USDT", "ETH/USDT"]
        self.exchange_list = ["binance", "coinbase", "kraken", "ftx"]
        self.total_profit = 0.0
        self.trade_count = 0
        
    async def get_exchange_prices(self, exchange: str) -> Dict[str, float]:
        """Get current prices from a specific exchange"""
        try:
            # In a real implementation, this would call the actual exchange API
            # For demo purposes, we'll simulate prices
            prices = {}
            for pair in self.trading_pairs:
                # Simulate realistic prices with slight variations
                base_price = 10000 if "BTC" in pair else 2000 if "ETH" in pair else 100
                variation = (hash(f"{exchange}_{pair}_{time.time()}") % 100) / 1000
                prices[pair] = base_price * (1 + variation)
            
            logger.info(f"Got prices from {exchange}: {prices}")
            return prices
            
        except Exception as e:
            logger.error(f"Error getting prices from {exchange}: {e}")
            return {}
    
    async def monitor_prices(self):
        """Monitor prices across all exchanges"""
        while True:
            try:
                # Get prices from all exchanges
                price_tasks = [self.get_exchange_prices(exchange) for exchange in self.exchange_list]
                exchange_prices = await asyncio.gather(*price_tasks)
                
                # Store current prices
                current_time = datetime.now()
                for i, exchange in enumerate(self.exchange_list):
                    for symbol, price in exchange_prices[i].items():
                        if symbol not in self.prices:
                            self.prices[symbol] = []
                        self.prices[symbol].append(CryptoPrice(symbol, price, exchange, current_time))
                        
                        # Keep only recent prices (last 10 entries)
                        if len(self.prices[symbol]) > 10:
                            self.prices[symbol].pop(0)
                
                # Check for arbitrage opportunities
                await self.find_arbitrage_opportunities()
                
                # Wait before next check
                await asyncio.sleep(CHECK_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in price monitoring: {e}")
                await asyncio.sleep(60)  # Wait longer if there's an error
    
    def calculate_profit_margin(self, buy_price: float, sell_price: float) -> float:
        """Calculate profit margin percentage"""
        if buy_price <= 0:
            return 0.0
        return ((sell_price - buy_price) / buy_price) * 100
    
    async def find_arbitrage_opportunities(self):
        """Find arbitrage opportunities across exchanges"""
        opportunities = []
        
        for symbol in self.trading_pairs:
            if symbol not in self.prices or len(self.prices[symbol]) < 2:
                continue
            
            # Get the best buy and sell prices for this symbol
            price_data = self.prices[symbol]
            
            # Find the lowest buy price and highest sell price
            buy_prices = [(p.price, p.exchange) for p in price_data if p.price > 0]
            sell_prices = [(p.price, p.exchange) for p in price_data if p.price > 0]
            
            if len(buy_prices) < 2 or len(sell_prices) < 2:
                continue
            
            # Sort by price
            buy_prices.sort()  # Lowest first
            sell_prices.sort(reverse=True)  # Highest first
            
            # Get best buy and sell
            best_buy_price, best_buy_exchange = buy_prices[0]
            best_sell_price, best_sell_exchange = sell_prices[0]
            
            # Check if we can make a profit
            if best_buy_exchange != best_sell_exchange and best_sell_price > best_buy_price:
                profit_margin = self.calculate_profit_margin(best_buy_price, best_sell_price)
                
                if profit_margin >= MIN_PROFIT_MARGIN:
                    # Calculate profit amount based on max trade amount
                    volume = min(MAX_TRADE_AMOUNT / best_buy_price, 1.0)  # Limit by max trade amount
                    profit_amount = (best_sell_price - best_buy_price) * volume
                    
                    opportunity = ArbitrageOpportunity(
                        symbol=symbol,
                        buy_exchange=best_buy_exchange,
                        sell_exchange=best_sell_exchange,
                        buy_price=best_buy_price,
                        sell_price=best_sell_price,
                        profit_margin=profit_margin,
                        profit_amount=profit_amount,
                        volume=volume
                    )
                    
                    opportunities.append(opportunity)
                    logger.info(f"Arbitrage opportunity found: {opportunity}")
        
        # Execute trades for profitable opportunities
        for opportunity in opportunities:
            await self.execute_trade(opportunity)
    
    async def execute_trade(self, opportunity: ArbitrageOpportunity):
        """Execute a trade based on an arbitrage opportunity"""
        try:
            # In a real implementation, this would execute actual trades on exchanges
            # For demo purposes, we'll simulate the trade
            
            logger.info(f"Executing arbitrage trade: Buy {opportunity.volume} {opportunity.symbol} "
                       f"at {opportunity.buy_exchange} for ${opportunity.buy_price} "
                       f"and sell at {opportunity.sell_exchange} for ${opportunity.sell_price}")
            
            # Simulate trade execution
            await asyncio.sleep(2)  # Simulate API call delay
            
            # Record profit
            self.total_profit += opportunity.profit_amount
            self.trade_count += 1
            
            # Log the trade
            trade_log = {
                "timestamp": datetime.now().isoformat(),
                "symbol": opportunity.symbol,
                "buy_exchange": opportunity.buy_exchange,
                "sell_exchange": opportunity.sell_exchange,
                "buy_price": opportunity.buy_price,
                "sell_price": opportunity.sell_price,
                "volume": opportunity.volume,
                "profit_amount": opportunity.profit_amount,
                "profit_margin": opportunity.profit_margin,
                "total_profit": self.total_profit,
                "trade_count": self.trade_count
            }
            
            logger.info(f"Trade executed successfully. Profit: ${opportunity.profit_amount:.2f}")
            logger.info(f"Total profit: ${self.total_profit:.2f} from {self.trade_count} trades")
            
            # Save trade to MLE
            await self.mle.log_event("arbitrage_trade", trade_log)
            
        except Exception as e:
            logger.error(f"Error executing trade: {e}")
    
    async def run(self):
        """Main run method"""
        logger.info("Starting Crypto Arbitrage Bot...")
        logger.info(f"Max trade amount: ${MAX_TRADE_AMOUNT}")
        logger.info(f"Minimum profit margin: {MIN_PROFIT_MARGIN}%")
        logger.info(f"Check interval: {CHECK_INTERVAL} seconds")
        
        # Start monitoring prices
        await self.monitor_prices()

async def main():
    """Main function to run the bot"""
    bot = CryptoArbitrageBot()
    
    try:
        await bot.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot crashed: {e}")
    finally:
        logger.info(f"Final statistics: {bot.trade_count} trades, total profit: ${bot.total_profit:.2f}")

if __name__ == "__main__":
    # Set up environment variables if not already set
    if not API_KEY:
        os.environ["API_KEY"] = "demo_api_key"
    if not SECRET_KEY:
        os.environ["SECRET_KEY"] = "demo_secret_key"
    if not PASSPHRASE:
        os.environ["PASSPHRASE"] = "demo_passphrase"
    
    # Run the bot
    asyncio.run(main())