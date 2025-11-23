import os
import time
import json
import logging
import requests
from datetime import datetime

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - [MONEY_MAKER] - %(levelname)s - %(message)s'
)
logger = logging.getLogger()

# --- CONFIGURATION FROM ENV VARIARABLES (MLE TEMPLATE STANDARD) ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
AFFILIATE_LINK = os.getenv("AFFILIATE_LINK", "https://accounts.binance.com/register?ref_id=YOUR_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")
# How often to run the loop (in seconds). Default 1 hour.
SLEEP_INTERVAL = int(os.getenv("SLEEP_INTERVAL", 3600))

class MoneyMakerBot:
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
        self.coingecko_api = "https://api.coingecko.com/api/v3"
        
        if not OPENAI_API_KEY:
            logger.warning("OPENAI_API_KEY is missing. Bot will run in DRY-RUN mode (no AI generation).")
        
        logger.info("MoneyMakerBot initialized. Let's get this bread.")

    def get_trending_coins(self):
        """
        Fetches the top 7 trending coins on CoinGecko.
        Market sentiment moves fast; we capture the 'Search Trends' to ride the wave.
        """
        try:
            url = f"{self.coingecko_api}/search/trending"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            
            coins = data.get('coins', [])
            if not coins:
                return []
            
            # Extract clean data
            trend_data = []
            for item in coins[:3]: # Top 3 only to focus capital/attention
                coin = item['item']
                trend_data.append({
                    'name': coin['name'],
                    'symbol': coin['symbol'],
                    'market_cap_rank': coin.get('market_cap_rank', 'N/A'),
                    'price_btc': coin.get('price_btc', 0)
                })
            
            return trend_data
        except Exception as e:
            logger.error(f"Failed to fetch trending coins: {e}")
            return []

    def generate_alpha_content(self, trend_data):
        """
        Uses OpenAI to generate a high-converting 'Alpha' post.
        It utilizes the 'Fear Of Missing Out' (FOMO) psychological trigger.
        """
        if not OPENAI_API_KEY:
            return f"🔥 Trending now: {trend_data[0]['name']} ({trend_data[0]['symbol']}). Don't miss out! Sign up here: {AFFILIATE_LINK}"

        coins_str = ", ".join([f"{c['name']} (${c['symbol']})" for c in trend_data])
        
        prompt = (
            f"You are a high-net-worth crypto trader and influencer. \n"
            f"The following coins are trending right now: {coins_str}.\n"
            f"Write a short, punchy, high-energy social media post (Twitter/X style) analyzing why these are moving.\n"
            f"Create urgency. Be professional but aggressive.\n"
            f"End the post with a call to action to trade these specifically on my partner exchange using the link provided below.\n"
            f"Do not mention that this is AI generated."
        )

        payload = {
            "model": "gpt-4o", # Or gpt-3.5-turbo depending on budget
            "messages": [
                {"role": "system", "content": "You are an expert financial copywriter optimized for conversion."},
                {"role": "user", "content": prompt}
            ],
            "max_tokens": 150
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {OPENAI_API_KEY}"
        }

        try:
            resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            result = resp.json()
            content = result['choices'][0]['message']['content']
            
            # Append the money link
            final_content = f"{content}\n\n🚀 Start Trading Here for a Bonus: {AFFILIATE_LINK}"
            return final_content
        except Exception as e:
            logger.error(f"OpenAI generation failed: {e}")
            return None

    def publish_content(self, content):
        """
        Publishes the content. 
        In a full MLE deployment, this would connect to X/Twitter API or a Telegram Bot.
        Here, we support a Discord Webhook (standard for paid groups/signals) or stdout.
        """
        logger.info("--- GENERATED CONTENT ---")
        print(content)
        logger.info("-------------------------")

        if DISCORD_WEBHOOK_URL and "http" in DISCORD_WEBHOOK_URL:
            try:
                payload = {"content": content}
                requests.post(DISCORD_WEBHOOK_URL, json=payload)
                logger.info("Successfully dispatched signal to Discord.")
            except Exception as e:
                logger.error(f"Failed to post to Discord: {e}")
        else:
            logger.info("No Webhook URL provided. Content logged only.")

    def run(self):
        """
        Main execution loop.
        """
        logger.info("Starting Money Generation Loop...")
        
        while True:
            logger.info("Scanning market for liquidity trends...")
            trending_coins = self.get_trending_coins()
            
            if trending_coins:
                logger.info(f"Identified trends: {[c['symbol'] for c in trending_coins]}")
                
                # Generate the content that sells
                alpha_post = self.generate_alpha_content(trending_coins)
                
                if alpha_post:
                    self.publish_content(alpha_post)
                else:
                    logger.warning("Content generation returned empty.")
            else:
                logger.warning("No API data received. Market might be quiet or API rate limited.")

            logging.info(f"Sleeping for {SLEEP_INTERVAL} seconds before next cycle...")
            time.sleep(SLEEP_INTERVAL)

if __name__ == "__main__":
    # The entry point for the MLE template container
    bot = MoneyMakerBot()
    bot.run()