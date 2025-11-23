"""
Crypto Arbitrage Opportunity Scanner & Alert System
Monitors price differences across exchanges and sends alerts for profitable arbitrage opportunities
"""

import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import asyncio
import aiohttp
from decimal import Decimal
import hmac
import hashlib
import requests
from dataclasses import dataclass
from collections import defaultdict
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class ArbitrageOpportunity:
    """Represents a profitable arbitrage opportunity"""
    symbol: str
    buy_exchange: str
    sell_exchange: str
    buy_price: Decimal
    sell_price: Decimal
    profit_percentage: Decimal
    volume_available: Decimal
    timestamp: datetime
    
    def __str__(self):
        return (f"🚨 ARBITRAGE ALERT: {self.symbol}\n"
                f"Buy on {self.buy_exchange}: ${self.buy_price:.4f}\n"
                f"Sell on {self.sell_exchange}: ${self.sell_price:.4f}\n"
                f"Profit: {self.profit_percentage:.2f}%\n"
                f"Max Volume: {self.volume_available:.4f}")

class ExchangeAPI:
    """Base class for exchange APIs"""
    
    def __init__(self, name: str):
        self.name = name
        self.session = None
        
    async def get_ticker(self, symbol: str) -> Dict:
        """Get current ticker data for a symbol"""
        raise NotImplementedError
        
    async def close(self):
        """Close the session"""
        if self.session:
            await self.session.close()

class BinanceAPI(ExchangeAPI):
    """Binance exchange API wrapper"""
    
    def __init__(self):
        super().__init__("Binance")
        self.base_url = "https://api.binance.com/api/v3"
        
    async def get_ticker(self, symbol: str) -> Dict:
        """Get Binance ticker data"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        try:
            url = f"{self.base_url}/ticker/24hr"
            params = {"symbol": symbol.replace("/", "")}
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "bid": Decimal(data.get("bidPrice", 0)),
                        "ask": Decimal(data.get("askPrice", 0)),
                        "volume": Decimal(data.get("volume", 0))
                    }
        except Exception as e:
            logger.error(f"Binance API error: {e}")
        return {"bid": Decimal(0), "ask": Decimal(0), "volume": Decimal(0)}

class KucoinAPI(ExchangeAPI):
    """KuCoin exchange API wrapper"""
    
    def __init__(self):
        super().__init__("KuCoin")
        self.base_url = "https://api.kucoin.com/api/v1"
        
    async def get_ticker(self, symbol: str) -> Dict:
        """Get KuCoin ticker data"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        try:
            symbol_formatted = symbol.replace("/", "-")
            url = f"{self.base_url}/market/orderbook/level1"
            params = {"symbol": symbol_formatted}
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    if data.get("data"):
                        return {
                            "bid": Decimal(data["data"].get("bestBid", 0)),
                            "ask": Decimal(data["data"].get("bestAsk", 0)),
                            "volume": Decimal(data["data"].get("size", 0))
                        }
        except Exception as e:
            logger.error(f"KuCoin API error: {e}")
        return {"bid": Decimal(0), "ask": Decimal(0), "volume": Decimal(0)}

class CoinbaseAPI(ExchangeAPI):
    """Coinbase exchange API wrapper"""
    
    def __init__(self):
        super().__init__("Coinbase")
        self.base_url = "https://api.exchange.coinbase.com"
        
    async def get_ticker(self, symbol: str) -> Dict:
        """Get Coinbase ticker data"""
        if not self.session:
            self.session = aiohttp.ClientSession()
            
        try:
            symbol_formatted = symbol.replace("/", "-")
            url = f"{self.base_url}/products/{symbol_formatted}/ticker"
            headers = {"User-Agent": "ArbitrageBot/1.0"}
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    data = await response.json()
                    return {
                        "bid": Decimal(data.get("bid", 0)),
                        "ask": Decimal(data.get("ask", 0)),
                        "volume": Decimal(data.get("volume", 0))
                    }
        except Exception as e:
            logger.error(f"Coinbase API error: {e}")
        return {"bid": Decimal(0), "ask": Decimal(0), "volume": Decimal(0)}

class ArbitrageScanner:
    """Main arbitrage scanner and alert system"""
    
    def __init__(self):
        self.exchanges = [
            BinanceAPI(),
            KucoinAPI(),
            CoinbaseAPI()
        ]
        self.symbols = [
            "BTC/USDT", "ETH/USDT", "BNB/USDT", "XRP/USDT",
            "ADA/USDT", "SOL/USDT", "DOGE/USDT", "DOT/USDT",
            "MATIC/USDT", "LTC/USDT"
        ]
        self.min_profit_percentage = Decimal("0.5")  # Minimum 0.5% profit
        self.opportunities = []
        self.sent_alerts = defaultdict(lambda: datetime.min)
        self.alert_cooldown = timedelta(minutes=30)
        
        # Email configuration from environment variables
        self.email_enabled = os.getenv("ENABLE_EMAIL_ALERTS", "false").lower() == "true"
        self.email_from = os.getenv("EMAIL_FROM", "")
        self.email_to = os.getenv("EMAIL_TO", "")
        self.email_password = os.getenv("EMAIL_PASSWORD", "")
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        
        # Webhook configuration
        self.webhook_url = os.getenv("WEBHOOK_URL", "")
        
    async def fetch_prices(self, symbol: str) -> Dict[str, Dict]:
        """Fetch prices from all exchanges for a symbol"""
        prices = {}
        tasks = []
        
        for exchange in self.exchanges:
            tasks.append(self.fetch_exchange_price(exchange, symbol))
            
        results = await asyncio.gather(*tasks)
        
        for exchange, price_data in results:
            if price_data:
                prices[exchange.name] = price_data
                
        return prices
    
    async def fetch_exchange_price(self, exchange: ExchangeAPI, symbol: str) -> Tuple[ExchangeAPI, Dict]:
        """Fetch price from a single exchange"""
        try:
            price_data = await exchange.get_ticker(symbol)
            return (exchange, price_data)
        except Exception as e:
            logger.error(f"Error fetching from {exchange.name}: {e}")
            return (exchange, None)
    
    def calculate_arbitrage(self, symbol: str, prices: Dict[str, Dict]) -> List[ArbitrageOpportunity]:
        """Calculate arbitrage opportunities from price data"""
        opportunities = []
        
        exchanges = list(prices.keys())
        for i in range(len(exchanges)):
            for j in range(len(exchanges)):
                if i == j:
                    continue
                    
                buy_exchange = exchanges[i]
                sell_exchange = exchanges[j]
                
                buy_price = prices[buy_exchange]["ask"]
                sell_price = prices[sell_exchange]["bid"]
                
                if buy_price <= 0 or sell_price <= 0:
                    continue
                
                profit_percentage = ((sell_price - buy_price) / buy_price) * 100
                
                if profit_percentage >= self.min_profit_percentage:
                    volume = min(
                        prices[buy_exchange]["volume"],
                        prices[sell_exchange]["volume"]
                    ) * Decimal("0.01")  # Conservative volume estimate
                    
                    opportunity = ArbitrageOpportunity(
                        symbol=symbol,
                        buy_exchange=buy_exchange,
                        sell_exchange=sell_exchange,
                        buy_price=buy_price,
                        sell_price=sell_price,
                        profit_percentage=profit_percentage,
                        volume_available=volume,
                        timestamp=datetime.now()
                    )
                    opportunities.append(opportunity)
                    
        return opportunities
    
    def send_email_alert(self, opportunity: ArbitrageOpportunity):
        """Send email alert for arbitrage opportunity"""
        if not self.email_enabled or not all([self.email_from, self.email_to, self.email_password]):
            return
            
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_from
            msg['To'] = self.email_to
            msg['Subject'] = f"Arbitrage Alert: {opportunity.profit_percentage:.2f}% on {opportunity.symbol}"
            
            body = str(opportunity)
            msg.attach(MIMEText(body, 'plain'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_from, self.email_password)
                server.send_message(msg)
                
            logger.info(f"Email alert sent for {opportunity.symbol}")
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
    
    def send_webhook_alert(self, opportunity: ArbitrageOpportunity):
        """Send webhook alert for arbitrage opportunity"""
        if not self.webhook_url:
            return
            
        try:
            payload = {
                "text": str(opportunity),
                "symbol": opportunity.symbol,
                "profit_percentage": float(opportunity.profit_percentage),
                "buy_exchange": opportunity.buy_exchange,
                "sell_exchange": opportunity.sell_exchange,
                "buy_price": float(opportunity.buy_price),
                "sell_price": float(opportunity.sell_price),
                "timestamp": opportunity.timestamp.isoformat()
            }
            
            response = requests.post(self.webhook_url, json=payload, timeout=10)
            if response.status_code == 200:
                logger.info(f"Webhook alert sent for {opportunity.symbol}")
        except Exception as e:
            logger.error(f"Failed to send webhook: {e}")
    
    def should_send_alert(self, opportunity: ArbitrageOpportunity) -> bool:
        """Check if we should send an alert for this opportunity"""
        key = f"{opportunity.symbol}_{opportunity.buy_exchange}_{opportunity.sell_exchange}"
        last_sent = self.sent_alerts[key]
        
        if datetime.now() - last_sent > self.alert_cooldown:
            self.sent_alerts[key] = datetime.now()
            return True
        return False
    
    async def scan_once(self):
        """Perform one scan cycle"""
        logger.info("Starting scan cycle...")
        all_opportunities = []
        
        for symbol in self.symbols:
            try:
                prices = await self.fetch_prices(symbol)
                if len(prices) >= 2:
                    opportunities = self.calculate_arbitrage(symbol, prices)
                    all_opportunities.extend(opportunities)
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")
        
        # Sort by profit percentage
        all_opportunities.sort(key=lambda x: x.profit_percentage, reverse=True)
        
        # Process and alert for top opportunities
        for opportunity in all_opportunities[:5]:  # Top 5 opportunities
            logger.info(f"Found opportunity: {opportunity}")
            
            if self.should_send_alert(opportunity):
                self.send_email_alert(opportunity)
                self.send_webhook_alert(opportunity)
        
        self.opportunities = all_opportunities
        return all_opportunities
    
    async def run_continuous(self, interval_seconds: int = 60):
        """Run continuous scanning"""
        logger.info(f"Starting continuous arbitrage scanning (interval: {interval_seconds}s)")
        
        while True:
            try:
                opportunities = await self.scan_once()
                
                if opportunities:
                    logger.info(f"Found {len(opportunities)} arbitrage opportunities")
                    for opp in opportunities[:3]:
                        print(opp)
                        print("-" * 50)
                else:
                    logger.info("No profitable arbitrage opportunities found")
                
                await asyncio.sleep(interval_seconds)
                
            except KeyboardInterrupt:
                logger.info("Scanning stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in scan cycle: {e}")
                await asyncio.sleep(interval_seconds)
        
        # Cleanup
        for exchange in self.exchanges:
            await exchange.close()

async def main():
    """Main entry point"""
    print("=" * 60)
    print("CRYPTO ARBITRAGE SCANNER - PROFIT FINDER")
    print("=" * 60)
    print("Monitoring price differences across exchanges...")
    print("Looking for profitable arbitrage opportunities...")
    print("-" * 60)
    
    scanner = ArbitrageScanner()
    
    # Run continuous scanning
    await scanner.run_continuous(interval_seconds=30)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise