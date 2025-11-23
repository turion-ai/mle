#!/usr/bin/env python3
"""
AI Affiliate Marketing Blog Generator
Automatically creates and monetizes content with affiliate links
"""

import os
import json
import time
import random
import logging
from typing import List, Dict, Optional
import requests
import openai
from bs4 import BeautifulSoup
import markdown
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class AffiliateBlogGenerator:
    def __init__(self):
        # Load environment variables
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        self.affiliate_platform = os.getenv('AFFILIATE_PLATFORM', 'amazon')
        self.affiliate_id = os.getenv('AFFILIATE_ID')
        self.blog_niche = os.getenv('BLOG_NICHE', 'technology')
        
        if not self.openai_api_key:
            raise ValueError("OPENAI_API_KEY environment variable is required")
        
        if not self.affiliate_id:
            logger.warning("AFFILIATE_ID not set, affiliate links will not be generated")
        
        # Configure OpenAI
        openai.api_key = self.openai_api_key
        
        # Predefined product categories based on niche
        self.product_categories = self._get_categories_by_niche()
        
        logger.info(f"Initialized AffiliateBlogGenerator for niche: {self.blog_niche}")

    def _get_categories_by_niche(self) -> List[str]:
        """Get product categories based on the blog niche"""
        niches = {
            'technology': [
                'laptops', 'smartphones', 'headphones', 'smartwatches',
                'gaming_consoles', 'cameras', 'tablets', 'smart_home_devices'
            ],
            'fitness': [
                'protein_powder', 'workout_equipment', 'fitness_trackers',
                'sportswear', 'supplements', 'yoga_mats', 'resistance_bands'
            ],
            'home': [
                'kitchen_appliances', 'home_decor', 'cleaning_tools',
                'furniture', 'gardening_tools', 'bedding', 'storage_solutions'
            ],
            'beauty': [
                'skincare', 'makeup', 'hair_care', 'fragrances',
                'beauty_tools', 'cosmetics', 'personal_care'
            ]
        }
        
        return niches.get(self.blog_niche, niches['technology'])

    def generate_article_topic(self) -> str:
        """Generate an article topic using AI"""
        prompt = f"""Generate an engaging blog post topic about {random.choice(self.product_categories)} 
        for a {self.blog_niche} blog. The topic should be SEO-friendly and include potential for product recommendations.
        Return only the topic title, nothing else."""
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional SEO content writer."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=50,
                temperature=0.8
            )
            
            topic = response.choices[0].message.content.strip().strip('"')
            logger.info(f"Generated topic: {topic}")
            return topic
            
        except Exception as e:
            logger.error(f"Error generating topic: {e}")
            # Fallback topic
            fallback_topics = [
                f"Top 10 {random.choice(self.product_categories).replace('_', ' ').title()} for 2023",
                f"Best {random.choice(self.product_categories).replace('_', ' ')} Reviews and Buying Guide",
                f"How to Choose the Perfect {random.choice(self.product_categories).replace('_', ' ')}"
            ]
            return random.choice(fallback_topics)

    def generate_article_content(self, topic: str) -> str:
        """Generate full article content with affiliate integration"""
        prompt = f"""Write a comprehensive blog post about: {topic}
        
        Requirements:
        1. Write in a engaging, professional tone
        2. Include at least 3 product recommendations with clear places for affiliate links
        3. Structure with introduction, product reviews, comparison, and conclusion
        4. Include SEO-optimized headings and subheadings
        5. Mark product placement areas with [PRODUCT:product_name]
        6. Keep it around 1000-1500 words
        
        Focus on providing genuine value to readers while naturally incorporating product recommendations."""
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional affiliate content writer who creates valuable, SEO-optimized articles with natural product placements."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=2000,
                temperature=0.7
            )
            
            content = response.choices[0].message.content.strip()
            logger.info("Generated article content")
            return content
            
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return f"# {topic}\n\nError generating content. Please try again later."

    def generate_affiliate_links(self, product_names: List[str]) -> Dict[str, str]:
        """Generate affiliate links for products (simulated for demonstration)"""
        affiliate_links = {}
        
        for product in product_names:
            # In a real implementation, you would use actual affiliate API
            # This is a simulation for demonstration purposes
            if self.affiliate_platform == 'amazon':
                affiliate_links[product] = f"https://www.amazon.com/dp/EXAMPLE{random.randint(1000,9999)}/?tag={self.affiliate_id}"
            else:
                affiliate_links[product] = f"https://example.com/product/{product.replace(' ', '-').lower()}?affiliate={self.affiliate_id}"
        
        return affiliate_links

    def extract_product_placeholders(self, content: str) -> List[str]:
        """Extract product names from content placeholders"""
        import re
        pattern = r'\[PRODUCT:(.*?)\]'
        products = re.findall(pattern, content)
        return list(set(products))  # Remove duplicates

    def insert_affiliate_links(self, content: str, affiliate_links: Dict[str, str]) -> str:
        """Replace product placeholders with affiliate links"""
        for product, link in affiliate_links.items():
            placeholder = f"[PRODUCT:{product}]"
            affiliate_html = f'<a href="{link}" target="_blank" rel="nofollow sponsored">{product}</a>'
            content = content.replace(placeholder, affiliate_html)
        
        return content

    def generate_html_content(self, markdown_content: str) -> str:
        """Convert markdown content to HTML with proper styling"""
        # Convert markdown to HTML
        html_content = markdown.markdown(markdown_content)
        
        # Basic HTML template
        html_template = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>{self.blog_niche.title()} Blog</title>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 0 auto; padding: 20px; }}
                h1, h2, h3 {{ color: #333; }}
                a {{ color: #0066cc; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
                .product-recommendation {{ background: #f9f9f9; padding: 15px; border-left: 4px solid #0066cc; margin: 15px 0; }}
                .affiliate-disclaimer {{ background: #fff3cd; padding: 15px; border: 1px solid #ffeaa7; border-radius: 5px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <article>
                {html_content}
                <div class="affiliate-disclaimer">
                    <strong>Disclosure:</strong> This article contains affiliate links. 
                    If you make a purchase through these links, I may earn a commission at no extra cost to you.
                </div>
            </article>
        </body>
        </html>
        """
        
        return html_template

    def save_article(self, topic: str, content: str, format: str = 'html'):
        """Save the generated article to a file"""
        # Create directory if it doesn't exist
        os.makedirs('articles', exist_ok=True)
        
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"articles/{topic.lower().replace(' ', '_')}_{timestamp}.{format}"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logger.info(f"Article saved to {filename}")
        return filename

    def publish_article(self, html_content: str):
        """
        Simulate publishing article to a blog platform
        In a real implementation, this would integrate with WordPress, Ghost, or other CMS APIs
        """
        # This is a simulation - in production, integrate with actual CMS APIs
        logger.info("Simulating article publication...")
        logger.info("In a real implementation, this would publish to WordPress/Ghost/etc.")
        
        # Simulate API call delay
        time.sleep(1)
        
        return {
            "status": "published",
            "url": f"https://yourblog.com/posts/{int(time.time())}",
            "message": "Article published successfully (simulated)"
        }

    def generate_complete_article(self):
        """Generate a complete article from topic generation to publication"""
        logger.info("Starting article generation process...")
        
        # Step 1: Generate topic
        topic = self.generate_article_topic()
        
        # Step 2: Generate content
        content = self.generate_article_content(topic)
        
        # Step 3: Extract products for affiliate linking
        products = self.extract_product_placeholders(content)
        logger.info(f"Found products for affiliate linking: {products}")
        
        # Step 4: Generate affiliate links
        if self.affiliate_id and products:
            affiliate_links = self.generate_affiliate_links(products)
            content = self.insert_affiliate_links(content, affiliate_links)
        else:
            logger.warning("No affiliate links generated - missing affiliate ID or products")
        
        # Step 5: Convert to HTML
        html_content = self.generate_html_content(content)
        
        # Step 6: Save article
        filename = self.save_article(topic, html_content, 'html')
        
        # Step 7: Publish (simulated)
        publication_result = self.publish_article(html_content)
        
        logger.info(f"Article generation complete: {filename}")
        return {
            "topic": topic,
            "filename": filename,
            "publication": publication_result,
            "products": products
        }

    def run_scheduled_generation(self, articles_per_day: int = 1):
        """Run scheduled article generation"""
        logger.info(f"Starting scheduled generation: {articles_per_day} articles per day")
        
        results = []
        for i in range(articles_per_day):
            logger.info(f"Generating article {i+1}/{articles_per_day}")
            try:
                result = self.generate_complete_article()
                results.append(result)
                
                # Space out article generation throughout the day
                if i < articles_per_day - 1:
                    delay = (24 * 60 * 60) / articles_per_day  # Spread throughout day
                    logger.info(f"Waiting {delay/3600:.1f} hours before next article...")
                    time.sleep(delay)
                    
            except Exception as e:
                logger.error(f"Error generating article {i+1}: {e}")
                # Continue with next article
                continue
        
        return results

def main():
    """Main function to run the affiliate blog generator"""
    try:
        # Initialize the generator
        generator = AffiliateBlogGenerator()
        
        # Check if we should run scheduled generation or single article
        if os.getenv('SCHEDULED_MODE', 'false').lower() == 'true':
            articles_per_day = int(os.getenv('ARTICLES_PER_DAY', '1'))
            results = generator.run_scheduled_generation(articles_per_day)
            logger.info(f"Completed scheduled generation of {len(results)} articles")
        else:
            # Generate a single article
            result = generator.generate_complete_article()
            logger.info(f"Single article generation complete: {result['topic']}")
        
    except Exception as e:
        logger.error(f"Fatal error in main: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())