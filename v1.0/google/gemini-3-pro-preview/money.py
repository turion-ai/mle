import os
import uvicorn
import stripe
import random
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse

# --- Configuration & Environment Setup ---
# In a production Docker container, these are injected by the cloud provider
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
APP_URL = os.getenv("APP_URL", "http://localhost:8080") 
PORT = int(os.getenv("PORT", 8080))

if not STRIPE_SECRET_KEY or not STRIPE_PUBLISHABLE_KEY:
    print("WARNING: Stripe keys are missing. App will start but payments will fail.")

stripe.api_key = STRIPE_SECRET_KEY

app = FastAPI(title="The Wisdom Store")

# --- Content Assets ---

# The "Product" we are selling
PREMIUM_WISDOMS = [
    "Success is not final, failure is not fatal: it is the courage to continue that counts.",
    "Code is like humor. When you have to explain it, it’s bad.",
    "Simplicity is the soul of efficiency.",
    "Make it work, make it right, make it fast.",
    "The best way to predict the future is to create it."
]

# HTML Templates (Embedded for single-file requirement)
def get_html_base(content: str):
    return f"""
    <!DOCTYPE html>
    <html>
        <head>
            <title>The Wisdom Store</title>
            <meta name="viewport" content="width=device-width, initial-scale=1">
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background: #f4f4f5; display: flex; justify-content: center; align-items: center; height: 100vh; margin: 0; }}
                .card {{ background: white; padding: 2rem; border-radius: 12px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); text-align: center; max-width: 400px; width: 100%; }}
                h1 {{ color: #333; }}
                p {{ color: #666; line-height: 1.5; }}
                .btn {{ background: #635bff; color: white; border: none; padding: 12px 24px; border-radius: 4px; font-size: 16px; cursor: pointer; font-weight: bold; text-decoration: none; display: inline-block; transition: background 0.2s; }}
                .btn:hover {{ background: #544ee0; }}
                .price {{ font-size: 2rem; color: #333; font-weight: bold; margin: 1rem 0; }}
                .quote {{ font-style: italic; font-size: 1.2rem; color: #444; border-left: 4px solid #635bff; padding-left: 1rem; margin: 1.5rem 0; }}
            </style>
        </head>
        <body>
            <div class="card">
                {content}
            </div>
        </body>
    </html>
    """

# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def home():
    """The Landing Page."""
    content = f"""
        <h1>Unlock Instant Wisdom</h1>
        <p>Struggling with a bug? Need motivation? Unlock premium developer wisdom now.</p>
        <div class="price">$5.00</div>
        <form action="/create-checkout-session" method="POST">
            <button type="submit" class="btn">Buy Access Now</button>
        </form>
        <p style="font-size: 0.8rem; margin-top: 1rem;">Secured by Stripe</p>
    """
    return get_html_base(content)

@app.post("/create-checkout-session")
async def create_checkout_session():
    """
    Creates a Stripe Checkout Session.
    We define the product details on the fly (Ad-hoc pricing).
    """
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[
                {
                    'price_data': {
                        'currency': 'usd',
                        'unit_amount': 500,  # $5.00 USD (in cents)
                        'product_data': {
                            'name': 'Premium Developer Wisdom',
                            'description': 'Instant access to high-level programming philosophy.',
                            'images': ['https://images.unsplash.com/photo-1555066931-4365d14bab8c?auto=format&fit=crop&w=300&q=80'],
                        },
                    },
                    'quantity': 1,
                },
            ],
            mode='payment',
            success_url=APP_URL + '/success',
            cancel_url=APP_URL + '/cancel',
        )
        return RedirectResponse(checkout_session.url, status_code=303)
    except Exception as e:
        return HTMLResponse(content=f"Error creating checkout session: {str(e)}", status_code=500)

@app.get("/success", response_class=HTMLResponse)
async def success():
    """
    The "Thank You" page that delivers the digital product.
    In a complex app, you would verify the session_id via Webhook here.
    """
    wisdom = random.choice(PREMIUM_WISDOMS)
    content = f"""
        <h1>Payment Successful!</h1>
        <p>Thank you for your purchase. Here is your premium content:</p>
        <div class="quote">"{wisdom}"</div>
        <a href="/" class="btn">Get More Wisdom</a>
    """
    return get_html_base(content)

@app.get("/cancel", response_class=HTMLResponse)
async def cancel():
    """The Cancel Page if the user backs out of payment."""
    content = f"""
        <h1>Order Canceled</h1>
        <p>You haven't been charged. The wisdom remains locked away for now.</p>
        <a href="/" class="btn">Try Again</a>
    """
    return get_html_base(content)

@app.get("/health")
async def health_check():
    """Health check for Cloud balancers."""
    return {"status": "ok"}

if __name__ == "__main__":
    # Host 0.0.0.0 is required for Docker
    uvicorn.run(app, host="0.0.0.0", port=PORT)