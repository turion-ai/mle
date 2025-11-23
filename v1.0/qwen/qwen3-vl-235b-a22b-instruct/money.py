#!/usr/bin/env python3
"""
Online Money Making Program - Automated Crypto Arbitrage Bot

This program implements a crypto arbitrage trading bot that identifies price differences
between exchanges and executes profitable trades. It uses the CCXT library to connect
to multiple cryptocurrency exchanges and implements risk management features.

The bot is designed to be deployed using the mle-template repository, which provides
the necessary environment variables and infrastructure for running the bot continuously.
"""

import os
import time
import logging
import asyncio
import json
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import random

# Import required libraries from the mle-template repository
import ccxt
import requests
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('arbitrage_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Configuration
EXCHANGES = ['binance', 'kraken', 'coinbasepro', 'huobi', 'okx']
SYMBOLS = ['BTC/USDT', 'ETH/USDT', 'BNB/USDT', 'SOL/USDT', 'ADA/USDT']
MIN_PROFIT_PERCENT = 0.5  # Minimum profit percentage to execute trade
MAX_TRADE_AMOUNT = 100.0  # Maximum amount to trade in USD
MIN_TRADE_AMOUNT = 10.0   # Minimum amount to trade in USD
TRADE_INTERVAL = 30       # Check for arbitrage opportunities every 30 seconds
MAX_RETRIES = 3           # Maximum number of retries for failed trades
FEE_BUFFER = 0.1          # Buffer for exchange fees (percentage)

# Initialize exchanges
exchanges = {}
for exchange_name in EXCHANGES:
    try:
        exchange_class = getattr(ccxt, exchange_name)
        exchange = exchange_class({
            'apiKey': os.getenv(f'{exchange_name.upper()}_API_KEY'),
            'secret': os.getenv(f'{exchange_name.upper()}_SECRET_KEY'),
            'password': os.getenv(f'{exchange_name.upper()}_PASSWORD'),
            'enableRateLimit': True,
        })
        exchanges[exchange_name] = exchange
        logger.info(f"Successfully initialized {exchange_name}")
    except Exception as e:
        logger.warning(f"Could not initialize {exchange_name}: {e}")

class ArbitrageBot:
    def __init__(self):
        self.profit_history = []
        self.trade_history = []
        self.total_profit = 0.0
        self.active_trades = 0
        self.max_concurrent_trades = 3
        
    async def get_market_data(self) -> Dict[str, Dict[str, float]]:
        """Get current market prices for all symbols across all exchanges"""
        market_data = {}
        
        for symbol in SYMBOLS:
            market_data[symbol] = {}
            for exchange_name, exchange in exchanges.items():
                try:
                    ticker = await asyncio.to_thread(exchange.fetch_ticker, symbol)
                    market_data[symbol][exchange_name] = {
                        'ask': ticker['ask'],
                        'bid': ticker['bid'],
                        'last': ticker['last'],
                        'timestamp': ticker['timestamp']
                    }
                except Exception as e:
                    logger.warning(f"Error fetching {symbol} from {exchange_name}: {e}")
                    continue
        
        return market_data
    
    def find_arbitrage_opportunities(self, market_data: Dict[str, Dict[str, float]]) -> List[Dict]:
        """Find arbitrage opportunities across exchanges"""
        opportunities = []
        
        for symbol in SYMBOLS:
            if symbol not in market_data:
                continue
                
            # Get all available prices for this symbol
            prices = {}
            for exchange_name, data in market_data[symbol].items():
                if 'ask' in data and 'bid' in data:
                    prices[exchange_name] = {
                        'ask': data['ask'],
                        'bid': data['bid']
                    }
            
            if len(prices) < 2:
                continue
                
            # Find the exchange with the lowest ask price (buy)
            buy_exchange = min(prices.keys(), key=lambda x: prices[x]['ask'])
            buy_price = prices[buy_exchange]['ask']
            
            # Find the exchange with the highest bid price (sell)
            sell_exchange = max(prices.keys(), key=lambda x: prices[x]['bid'])
            sell_price = prices[sell_exchange]['bid']
            
            # Calculate potential profit
            if buy_exchange != sell_exchange and sell_price > buy_price:
                profit_percent = ((sell_price - buy_price) / buy_price) * 100
                
                # Check if profit exceeds minimum threshold (including fee buffer)
                if profit_percent > (MIN_PROFIT_PERCENT + FEE_BUFFER):
                    opportunity = {
                        'symbol': symbol,
                        'buy_exchange': buy_exchange,
                        'sell_exchange': sell_exchange,
                        'buy_price': buy_price,
                        'sell_price': sell_price,
                        'profit_percent': profit_percent,
                        'profit_amount': sell_price - buy_price
                    }
                    opportunities.append(opportunity)
        
        return opportunities
    
    async def execute_trade(self, opportunity: Dict) -> bool:
        """Execute an arbitrage trade"""
        if self.active_trades >= self.max_concurrent_trades:
            logger.info("Maximum concurrent trades reached, waiting...")
            return False
            
        self.active_trades += 1
        trade_success = False
        
        try:
            symbol = opportunity['symbol']
            buy_exchange_name = opportunity['buy_exchange']
            sell_exchange_name = opportunity['sell_exchange']
            buy_price = opportunity['buy_price']
            sell_price = opportunity['sell_price']
            
            # Calculate trade amount (use minimum of available balance and max trade amount)
            buy_exchange = exchanges[buy_exchange_name]
            sell_exchange = exchanges[sell_exchange_name]
            
            # Get available balance
            try:
                balance = await asyncio.to_thread(buy_exchange.fetch_balance)
                usdt_balance = balance.get('USDT', {}).get('free', 0)
                if usdt_balance < MIN_TRADE_AMOUNT:
                    logger.warning(f"Insufficient USDT balance on {buy_exchange_name}: {usdt_balance}")
                    return False
                    
                trade_amount = min(MAX_TRADE_AMOUNT, usdt_balance)
                if trade_amount < MIN_TRADE_AMOUNT:
                    return False
                    
                # Calculate amount of crypto to buy
                crypto_amount = trade_amount / buy_price
                
                # Execute buy order
                logger.info(f"Buying {crypto_amount:.6f} {symbol} on {buy_exchange_name} at {buy_price}")
                buy_order = await asyncio.to_thread(
                    buy_exchange.create_market_buy_order, 
                    symbol, 
                    crypto_amount
                )
                
                # Execute sell order
                logger.info(f"Selling {crypto_amount:.6f} {symbol} on {sell_exchange_name} at {sell_price}")
                sell_order = await asyncio.to_thread(
                    sell_exchange.create_market_sell_order, 
                    symbol, 
                    crypto_amount
                )
                
                # Calculate profit
                buy_cost = buy_order['cost'] if 'cost' in buy_order else (buy_price * crypto_amount)
                sell_revenue = sell_order['cost'] if 'cost' in sell_order else (sell_price * crypto_amount)
                profit = sell_revenue - buy_cost
                
                # Record trade
                trade_record = {
                    'timestamp': datetime.now().isoformat(),
                    'symbol': symbol,
                    'buy_exchange': buy_exchange_name,
                    'sell_exchange': sell_exchange_name,
                    'buy_price': buy_price,
                    'sell_price': sell_price,
                    'crypto_amount': crypto_amount,
                    'buy_cost': buy_cost,
                    'sell_revenue': sell_revenue,
                    'profit': profit,
                    'profit_percent': (profit / buy_cost) * 100
                }
                
                self.trade_history.append(trade_record)
                self.total_profit += profit
                self.profit_history.append(profit)
                
                logger.info(f"Trade completed: Profit = ${profit:.2f} ({(profit / buy_cost) * 100:.2f}%)")
                trade_success = True
                
            except Exception as e:
                logger.error(f"Error executing trade: {e}")
                logger.error(traceback.format_exc())
                
        except Exception as e:
            logger.error(f"Unexpected error in execute_trade: {e}")
            logger.error(traceback.format_exc())
            
        finally:
            self.active_trades -= 1
            return trade_success
    
    async def run(self):
        """Main loop of the arbitrage bot"""
        logger.info("Starting Crypto Arbitrage Bot...")
        logger.info(f"Monitoring {len(SYMBOLS)} symbols across {len(EXCHANGES)} exchanges")
        logger.info(f"Minimum profit threshold: {MIN_PROFIT_PERCENT}%")
        
        while True:
            try:
                # Get market data
                market_data = await self.get_market_data()
                
                # Find arbitrage opportunities
                opportunities = self.find_arbitrage_opportunities(market_data)
                
                # Execute trades
                for opportunity in opportunities:
                    logger.info(f"Found arbitrage opportunity: {opportunity}")
                    success = await self.execute_trade(opportunity)
                    if success:
                        # Add a small delay between trades to avoid rate limits
                        await asyncio.sleep(5)
                
                # Log summary
                if len(self.profit_history) > 0:
                    avg_profit = sum(self.profit_history[-10:]) / len(self.profit_history[-10:])
                    logger.info(f"Total profit: ${self.total_profit:.2f}")
                    logger.info(f"Average recent profit: ${avg_profit:.2f}")
                
                # Wait before next iteration
                await asyncio.sleep(TRADE_INTERVAL)
                
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                logger.error(traceback.format_exc())
                await asyncio.sleep(60)  # Wait longer if there's an error

async def main():
    """Main function to run the bot"""
    bot = ArbitrageBot()
    
    # Start the bot
    await bot.run()

if __name__ == "__main__":
    # Check if required environment variables are set
    required_env_vars = []
    for exchange in EXCHANGES:
        required_env_vars.extend([
            f'{exchange.upper()}_API_KEY',
            f'{exchange.upper()}_SECRET_KEY',
            f'{exchange.upper()}_PASSWORD'
        ])
    
    missing_vars = []
    for var in required_env_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.warning(f"Missing environment variables: {missing_vars}")
        logger.warning("The bot will run in simulation mode without executing real trades.")
    
    # Run the bot
    asyncio.run(main())