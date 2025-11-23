import os
import json
import time
from datetime import datetime
from pathlib import Path
from pytrends.request import TrendReq
from openai import OpenAI

OUTPUT_DIR = Path("outputs")
OUTPUT_DIR.mkdir(exist_ok=True)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

AFFILIATE_TAG = os.getenv("AMAZON_AFFILIATE_TAG", "")
AMAZON_SEARCH_URL = os.getenv("AMAZON_SEARCH_URL", "https://www.amazon.com/s?k=")

def get_trending_keywords():
    try:
        pytrends = TrendReq(hl="en-US", tz=360)
        pytrends.build_payload(["best product"], timeframe="now 7-d")
        related = pytrends.related_queries()
        top = related.get("best product", {}).get("top")
        if top is None:
            return []
        return [row["query"] for _, row in top.iterrows()][:5]
    except Exception:
        return ["best gadget", "best budget laptop", "smart home device"]

def ai_generate_review(keyword):
    prompt = (
        f"Write a persuasive, SEO‑optimized review article recommending top Amazon "
        f"products for the search term '{keyword}'. Include buying tips and benefits. "
        f"Do NOT make up specific product details—keep it general."
    )
    response = client.responses.create(model="gpt-4.1-mini", input=prompt)
    return response.output_text

def make_affiliate_link(keyword):
    q = keyword.replace(" ", "+")
    return f"{AMAZON_SEARCH_URL}{q}&tag={AFFILIATE_TAG}"

def generate_html(keyword, article_text, affiliate_link):
    return (
        f"<html><head><title>{keyword} Review Guide</title></head>"
        f"<body>"
        f"<h1>{keyword} – Top Picks & Buying Guide</h1>"
        f"<p>{article_text}</p>"
        f"<h2>Amazon Search Link</h2>"
        f"<p><a href='{affiliate_link}'>View recommended {keyword} products on Amazon</a></p>"
        f"</body></html>"
    )

def save_file(keyword, html):
    slug = keyword.lower().replace(" ", "-")
    path = OUTPUT_DIR / f"{slug}.html"
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    return path

def main():
    keywords = get_trending_keywords()
    for kw in keywords:
        print("Generating article for:", kw)
        article = ai_generate_review(kw)
        link = make_affiliate_link(kw)
        html = generate_html(kw, article, link)
        path = save_file(kw, html)
        print("Saved:", path)

    print("Done. Articles generated in /outputs")

if __name__ == "__main__":
    main()