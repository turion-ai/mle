"""
Crypto Arbitrage Opportunity Scanner & Alert System
Monitors price differences across exchanges and sends notifications for profitable trades
"""

import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
import requests
from dataclasses import dataclass
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import hashlib
import hmac

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
    buy_price: float
    sell_price: float
    profit_percentage: float
    volume: float
    timestamp: datetime
    
    def estimated_profit(self, investment: float = 1000) -> float:
        """Calculate estimated profit for given investment"""
        return investment * (self.profit_percentage / 100)

class CryptoArbitrageBot:
    """Main arbitrage bot that scans and alerts on opportunities"""
    
    def __init__(self):
        # Email configuration from environment
        self.smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.email_from = os.getenv('EMAIL_FROM', '')
        self.email_password = os.getenv('EMAIL_PASSWORD', '')
        self.email_to = os.getenv('EMAIL_TO', '').split(',')
        
        # Trading configuration
        self.min_profit_percentage = float(os.getenv('MIN_PROFIT_PERCENTAGE', '2.0'))
        self.check_interval = int(os.getenv('CHECK_INTERVAL', '60'))
        self.symbols = os.getenv('SYMBOLS', 'BTC,ETH,BNB,SOL,MATIC').split(',')
        
        # API Keys (optional for premium features)
        self.coinmarketcap_api_key = os.getenv('COINMARKETCAP_API_KEY', '')
        
        # Track sent alerts to avoid duplicates
        self.sent_alerts = {}
        self.alert_cooldown = 3600  # 1 hour cooldown per opportunity
        
    def get_binance_prices(self) -> Dict[str, float]:
        """Fetch current prices from Binance"""
        prices = {}
        try:
            response = requests.get('https://api.binance.com/api/v3/ticker/price', timeout=10)
            if response.status_code == 200:
                data = response.json()
                for item in data:
                    symbol = item['symbol']
                    for crypto in self.symbols:
                        if symbol == f"{crypto}USDT":
                            prices[crypto] = float(item['price'])
                            break
        except Exception as e:
            logger.error(f"Error fetching Binance prices: {e}")
        return prices
    
    def get_coinbase_prices(self) -> Dict[str, float]:
        """Fetch current prices from Coinbase"""
        prices = {}
        try:
            for symbol in self.symbols:
                response = requests.get(
                    f'https://api.coinbase.com/v2/exchange-rates?currency={symbol}',
                    timeout=10
                )
                if response.status_code == 200:
                    data = response.json()
                    if 'data' in data and 'rates' in data['data']:
                        prices[symbol] = float(data['data']['rates'].get('USD', 0))
        except Exception as e:
            logger.error(f"Error fetching Coinbase prices: {e}")
        return prices
    
    def get_kraken_prices(self) -> Dict[str, float]:
        """Fetch current prices from Kraken"""
        prices = {}
        symbol_map = {
            'BTC': 'XXBTZUSD',
            'ETH': 'XETHZUSD',
            'SOL': 'SOLUSD',
            'MATIC': 'MATICUSD'
        }
        
        try:
            pairs = ','.join([symbol_map.get(s, f'{s}USD') for s in self.symbols if s in symbol_map])
            response = requests.get(
                f'https://api.kraken.com/0/public/Ticker?pair={pairs}',
                timeout=10
            )
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    for symbol, kraken_pair in symbol_map.items():
                        if kraken_pair in data['result']:
                            prices[symbol] = float(data['result'][kraken_pair]['c'][0])
        except Exception as e:
            logger.error(f"Error fetching Kraken prices: {e}")
        return prices
    
    def get_kucoin_prices(self) -> Dict[str, float]:
        """Fetch current prices from KuCoin"""
        prices = {}
        try:
            response = requests.get('https://api.kucoin.com/api/v1/market/allTickers', timeout=10)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and 'ticker' in data['data']:
                    for item in data['data']['ticker']:
                        symbol_pair = item['symbol']
                        for crypto in self.symbols:
                            if symbol_pair == f"{crypto}-USDT":
                                prices[crypto] = float(item['last'])
                                break
        except Exception as e:
            logger.error(f"Error fetching KuCoin prices: {e}")
        return prices
    
    def find_arbitrage_opportunities(self) -> List[ArbitrageOpportunity]:
        """Find profitable arbitrage opportunities across exchanges"""
        opportunities = []
        
        # Fetch prices from all exchanges
        exchanges = {
            'Binance': self.get_binance_prices(),
            'Coinbase': self.get_coinbase_prices(),
            'Kraken': self.get_kraken_prices(),
            'KuCoin': self.get_kucoin_prices()
        }
        
        # Log fetched prices
        for exchange, prices in exchanges.items():
            logger.info(f"{exchange} prices: {prices}")
        
        # Compare prices across exchanges for each symbol
        for symbol in self.symbols:
            prices_by_exchange = {}
            
            for exchange, prices in exchanges.items():
                if symbol in prices and prices[symbol] > 0:
                    prices_by_exchange[exchange] = prices[symbol]
            
            if len(prices_by_exchange) < 2:
                continue
            
            # Find min and max prices
            min_exchange = min(prices_by_exchange, key=prices_by_exchange.get)
            max_exchange = max(prices_by_exchange, key=prices_by_exchange.get)
            
            min_price = prices_by_exchange[min_exchange]
            max_price = prices_by_exchange[max_exchange]
            
            # Calculate profit percentage
            profit_pct = ((max_price - min_price) / min_price) * 100
            
            # Check if profit meets threshold
            if profit_pct >= self.min_profit_percentage:
                opportunity = ArbitrageOpportunity(
                    symbol=symbol,
                    buy_exchange=min_exchange,
                    sell_exchange=max_exchange,
                    buy_price=min_price,
                    sell_price=max_price,
                    profit_percentage=profit_pct,
                    volume=0,  # Would need exchange APIs to get real volume
                    timestamp=datetime.now()
                )
                opportunities.append(opportunity)
                logger.info(f"Found opportunity: {symbol} - Buy on {min_exchange} at ${min_price:.2f}, "
                          f"Sell on {max_exchange} at ${max_price:.2f}, Profit: {profit_pct:.2f}%")
        
        return opportunities
    
    def send_email_alert(self, opportunities: List[ArbitrageOpportunity]):
        """Send email alerts for profitable opportunities"""
        if not self.email_from or not self.email_password or not self.email_to[0]:
            logger.warning("Email configuration not set. Skipping email alerts.")
            return
        
        try:
            # Create email content
            subject = f"🚨 Crypto Arbitrage Alert - {len(opportunities)} Opportunities Found!"
            
            html_content = """
            <html>
            <body style="font-family: Arial, sans-serif;">
                <h2 style="color: #2e7d32;">💰 Profitable Arbitrage Opportunities Detected</h2>
                <table border="1" cellpadding="10" style="border-collapse: collapse;">
                    <tr style="background-color: #f5f5f5;">
                        <th>Crypto</th>
                        <th>Buy Exchange</th>
                        <th>Buy Price</th>
                        <th>Sell Exchange</th>
                        <th>Sell Price</th>
                        <th>Profit %</th>
                        <th>Est. Profit ($1000)</th>
                    </tr>
            """
            
            for opp in opportunities:
                html_content += f"""
                    <tr>
                        <td><strong>{opp.symbol}</strong></td>
                        <td>{opp.buy_exchange}</td>
                        <td>${opp.buy_price:,.2f}</td>
                        <td>{opp.sell_exchange}</td>
                        <td>${opp.sell_price:,.2f}</td>
                        <td style="color: #2e7d32; font-weight: bold;">{opp.profit_percentage:.2f}%</td>
                        <td style="color: #2e7d32;">${opp.estimated_profit():,.2f}</td>
                    </tr>
                """
            
            html_content += """
                </table>
                <p style="margin-top: 20px; color: #666;">
                    <strong>Note:</strong> These opportunities are time-sensitive. 
                    Always verify prices and consider transaction fees before trading.
                </p>
                <p style="color: #999; font-size: 12px;">
                    Generated by Crypto Arbitrage Bot at {timestamp}
                </p>
            </body>
            </html>
            """.format(timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC"))
            
            # Send email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.email_from
            msg['To'] = ', '.join(self.email_to)
            
            msg.attach(MIMEText(html_content, 'html'))
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.email_from, self.email_password)
                server.send_message(msg)
            
            logger.info(f"Email alert sent to {', '.join(self.email_to)}")
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {e}")
    
    def should_send_alert(self, opportunity: ArbitrageOpportunity) -> bool:
        """Check if alert should be sent (avoid spam)"""
        key = f"{opportunity.symbol}_{opportunity.buy_exchange}_{opportunity.sell_exchange}"
        
        if key in self.sent_alerts:
            time_since_last = (datetime.now() - self.sent_alerts[key]).total_seconds()
            if time_since_last < self.alert_cooldown:
                return False
        
        self.sent_alerts[key] = datetime.now()
        return True
    
    def create_webhook_alert(self, opportunities: List[ArbitrageOpportunity]):
        """Send alerts via webhook (Discord, Slack, etc.)"""
        webhook_url = os.getenv('WEBHOOK_URL', '')
        if not webhook_url:
            return
        
        try:
            for opp in opportunities:
                payload = {
                    "content": f"**Arbitrage Alert!** 🚨\n"
                              f"**{opp.symbol}**: Buy on {opp.buy_exchange} at ${opp.buy_price:,.2f}, "
                              f"Sell on {opp.sell_exchange} at ${opp.sell_price:,.2f}\n"
                              f"**Profit: {opp.profit_percentage:.2f}%** (${opp.estimated_profit():,.2f} per $1000)"
                }
                requests.post(webhook_url, json=payload, timeout=5)
        except Exception as e:
            logger.error(f"Failed to send webhook alert: {e}")
    
    def generate_api_report(self) -> Dict:
        """Generate JSON report for API consumers"""
        opportunities = self.find_arbitrage_opportunities()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "opportunities_count": len(opportunities),
            "min_profit_threshold": self.min_profit_percentage,
            "opportunities": [
                {
                    "symbol": opp.symbol,
                    "buy_exchange": opp.buy_exchange,
                    "sell_exchange": opp.sell_exchange,
                    "buy_price": opp.buy_price,
                    "sell_price": opp.sell_price,
                    "profit_percentage": opp.profit_percentage,
                    "estimated_profit_per_1000": opp.estimated_profit()
                }
                for opp in opportunities
            ]
        }
        
        # Save to file for web serving
        with open('arbitrage_report.json', 'w') as f:
            json.dump(report, f, indent=2)
        
        return report
    
    def run(self):
        """Main bot loop"""
        logger.info("Starting Crypto Arbitrage Bot...")
        logger.info(f"Monitoring symbols: {', '.join(self.symbols)}")
        logger.info(f"Minimum profit threshold: {self.min_profit_percentage}%")
        logger.info(f"Check interval: {self.check_interval} seconds")
        
        iteration = 0
        while True:
            try:
                iteration += 1
                logger.info(f"Scanning for opportunities (iteration {iteration})...")
                
                # Find opportunities
                opportunities = self.find_arbitrage_opportunities()
                
                # Filter new opportunities
                new_opportunities = [
                    opp for opp in opportunities 
                    if self.should_send_alert(opp)
                ]
                
                # Send alerts if new opportunities found
                if new_opportunities:
                    logger.info(f"Found {len(new_opportunities)} new profitable opportunities!")
                    self.send_email_alert(new_opportunities)
                    self.create_webhook_alert(new_opportunities)
                else:
                    logger.info("No new profitable opportunities found.")
                
                # Generate report
                report = self.generate_api_report()
                logger.info(f"Report generated with {report['opportunities_count']} total opportunities")
                
                # Clean old alerts
                cutoff = datetime.now() - timedelta(seconds=self.alert_cooldown)
                self.sent_alerts = {
                    k: v for k, v in self.sent_alerts.items() 
                    if v > cutoff
                }
                
                # Wait before next check
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Bot stopped by user.")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(30)  # Wait 30 seconds on error

def main():
    """Entry point"""
    bot = CryptoArbitrageBot()
    bot.run()

if __name__ == "__main__":
    main()