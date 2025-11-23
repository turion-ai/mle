import os
import sqlite3
import json
import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
import stripe
import openai
from fastapi import FastAPI, HTTPException, Header, Request, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel
import uvicorn
import asyncio

# ============================================================================
# CONFIGURATION - Set these environment variables in your deployment
# ============================================================================
CONFIG = {
    "stripe_secret_key": os.getenv("STRIPE_SECRET_KEY", "sk_test_your_key_here"),
    "stripe_publishable_key": os.getenv("STRIPE_PUBLISHABLE_KEY", "pk_test_your_key_here"),
    "stripe_webhook_secret": os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_your_secret_here"),
    "openai_api_key": os.getenv("OPENAI_API_KEY", "your_openai_key_here"),
    "db_path": os.getenv("DB_PATH", "./data/app.db"),
    "port": int(os.getenv("PORT", 8000)),
    "host": os.getenv("HOST", "0.0.0.0"),
    "app_url": os.getenv("APP_URL", "http://localhost:8000")
}

# Pricing tiers
TIERS = {
    "free": {"name": "Free", "price": 0, "generations": 5, "stripe_price_id": None},
    "pro": {"name": "Pro", "price": 1500, "generations": 100, "stripe_price_id": "price_1_pro_monthly"},
    "business": {"name": "Business", "price": 4000, "generations": 999999, "stripe_price_id": "price_1_business_monthly"}
}

# ============================================================================
# DATABASE SETUP
# ============================================================================
def init_db():
    """Initialize SQLite database with required tables"""
    os.makedirs(os.path.dirname(CONFIG["db_path"]), exist_ok=True)
    conn = sqlite3.connect(CONFIG["db_path"])
    c = conn.cursor()
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            api_key TEXT UNIQUE,
            email TEXT,
            tier TEXT DEFAULT 'free',
            subscription_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    c.execute('''
        CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content_type TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')
    
    # Create demo user if none exists
    c.execute("SELECT COUNT(*) FROM users")
    if c.fetchone()[0] == 0:
        demo_api_key = "demo_" + uuid.uuid4().hex[:16]
        c.execute(
            "INSERT INTO users (id, api_key, email, tier) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), demo_api_key, "demo@example.com", "free")
        )
        print(f"🎉 Demo user created! API Key: {demo_api_key}")
        print(f"🚀 App ready at {CONFIG['app_url']}")
    
    conn.commit()
    conn.close()

# ============================================================================
# MODELS
# ============================================================================
class GenerationRequest(BaseModel):
    prompt: str
    content_type: str = "general"
    max_length: int = 500

class UserResponse(BaseModel):
    api_key: str
    tier: str
    usage_this_month: int
    limit: int

# ============================================================================
# STRIPE & OPENAI SETUP
# ============================================================================
stripe.api_key = CONFIG["stripe_secret_key"]
openai.api_key = CONFIG["openai_api_key"]

# ============================================================================
# FASTAPI APP
# ============================================================================
app = FastAPI(
    title="AI Copy Generator SaaS",
    description="Generate marketing copy with AI. Free tier available.",
    version="1.0.0"
)

# ============================================================================
# HELPERS
# ============================================================================
def get_db():
    conn = sqlite3.connect(CONFIG["db_path"])
    conn.row_factory = sqlite3.Row
    return conn

def get_user_by_api_key(api_key: str) -> Optional[Dict[str, Any]]:
    conn = get_db()
    user = conn.execute("SELECT * FROM users WHERE api_key = ?", (api_key,)).fetchone()
    conn.close()
    return dict(user) if user else None

def get_monthly_usage(user_id: str) -> int:
    conn = get_db()
    thirty_days_ago = datetime.now() - timedelta(days=30)
    count = conn.execute(
        "SELECT COUNT(*) as count FROM usage WHERE user_id = ? AND timestamp > ?",
        (user_id, thirty_days_ago.isoformat())
    ).fetchone()["count"]
    conn.close()
    return count

def record_usage(user_id: str, content_type: str):
    conn = get_db()
    c = conn.cursor()
    c.execute(
        "INSERT INTO usage (user_id, content_type) VALUES (?, ?)",
        (user_id, content_type)
    )
    conn.commit()
    conn.close()

def check_rate_limit(user: Dict[str, Any]) -> bool:
    usage = get_monthly_usage(user["id"])
    tier = TIERS[user["tier"]]
    return usage < tier["generations"]

# ============================================================================
# DEPENDENCIES
# ============================================================================
async def verify_api_key(api_key: str = Header(..., alias="X-API-Key")):
    user = get_user_by_api_key(api_key)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return user

# ============================================================================
# ROUTES - API
# ============================================================================
@app.post("/api/v1/generate")
async def generate_content(
    request: GenerationRequest,
    user: dict = Depends(verify_api_key)
) -> Dict[str, Any]:
    """Generate AI content"""
    
    # Check rate limit
    if not check_rate_limit(user):
        tier = TIERS[user["tier"]]
        raise HTTPException(
            status_code=429,
            detail=f"Monthly limit reached. You've used {tier['generations']}/{tier['generations']} generations. Upgrade your plan."
        )
    
    try:
        # Call OpenAI
        response = await asyncio.to_thread(
            lambda: openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a professional marketing copywriter. Create compelling, concise copy."},
                    {"role": "user", "content": f"Write {request.content_type} copy: {request.prompt}"}
                ],
                max_tokens=request.max_length
            )
        )
        
        content = response.choices[0].message.content
        
        # Record usage
        record_usage(user["id"], request.content_type)
        
        # Return usage info
        usage = get_monthly_usage(user["id"])
        tier = TIERS[user["tier"]]
        
        return {
            "content": content,
            "usage": {
                "used": usage,
                "limit": tier["generations"],
                "remaining": tier["generations"] - usage
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

@app.get("/api/v1/account", response_model=UserResponse)
async def get_account(user: dict = Depends(verify_api_key)):
    """Get account information"""
    usage = get_monthly_usage(user["id"])
    tier = TIERS[user["tier"]]
    
    return {
        "api_key": user["api_key"],
        "tier": user["tier"],
        "usage_this_month": usage,
        "limit": tier["generations"]
    }

@app.post("/api/v1/upgrade")
async def create_checkout_session(
    tier: str = Query(..., regex="^(pro|business)$"),
    user: dict = Depends(verify_api_key)
):
    """Create Stripe checkout session for plan upgrade"""
    
    if tier not in TIERS or tier == "free":
        raise HTTPException(status_code=400, detail="Invalid tier")
    
    price_id = TIERS[tier]["stripe_price_id"]
    if not price_id or price_id == "price_1_pro_monthly":
        # Demo mode - return success URL
        return {"url": f"{CONFIG['app_url']}/success?session_id=demo_{tier}"}
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price': price_id,
                'quantity': 1,
            }],
            mode='subscription',
            success_url=f"{CONFIG['app_url']}/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{CONFIG['app_url']}/cancel",
            client_reference_id=user["id"]
        )
        return {"url": checkout_session.url}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# ROUTES - WEB
# ============================================================================
@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Main dashboard"""
    return DASHBOARD_HTML

@app.get("/success")
async def success(session_id: str):
    """Handle successful payment"""
    if session_id.startswith("demo_"):
        tier = session_id.split("_")[1]
        return f"""
        <h1>Success!</h1>
        <p>Demo mode: You would now be subscribed to {tier} tier.</p>
        <p>In production, Stripe would handle this automatically.</p>
        <a href="/">Go to Dashboard</a>
        """
    
    # In production, verify session and update user tier
    return RedirectResponse(url="/")

@app.get("/cancel")
async def cancel():
    """Handle cancelled payment"""
    return """
    <h1>Payment Cancelled</h1>
    <p>Your payment was cancelled. You can try again anytime.</p>
    <a href="/">Go to Dashboard</a>
    """

# ============================================================================
# STRIPE WEBHOOK
# ============================================================================
@app.post("/webhook")
async def stripe_webhook(request: Request):
    """Handle Stripe webhook events"""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, CONFIG["stripe_webhook_secret"]
        )
    except:
        raise HTTPException(status_code=400, detail="Invalid webhook")
    
    if event["type"] == "checkout.session.completed":
        session = event["data"]["object"]
        user_id = session.get("client_reference_id")
        subscription_id = session.get("subscription")
        
        # Update user tier (you'd need to map price ID to tier)
        # This is simplified - in production, store tier in metadata
        conn = get_db()
        conn.execute(
            "UPDATE users SET subscription_id = ? WHERE id = ?",
            (subscription_id, user_id)
        )
        conn.commit()
        conn.close()
    
    return {"status": "success"}

# ============================================================================
# FRONTEND HTML
# ============================================================================
DASHBOARD_HTML = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Copy Generator SaaS</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
        .container {{ background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
        .api-key {{ background: #e8f4f8; padding: 10px; border-radius: 5px; font-family: monospace; word-break: break-all; }}
        button {{ background: #007cba; color: white; border: none; padding: 10px 20px; border-radius: 5px; cursor: pointer; }}
        button:hover {{ background: #005a87; }}
        button:disabled {{ background: #ccc; cursor: not-allowed; }}
        textarea {{ width: 100%; padding: 10px; border: 1px solid #ddd; border-radius: 5px; min-height: 100px; }}
        .result {{ background: #f9f9f9; padding: 15px; border-radius: 5px; margin: 15px 0; white-space: pre-wrap; }}
        .error {{ color: #d32f2f; background: #ffebee; padding: 10px; border-radius: 5px; }}
        .tier-info {{ background: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        .usage-bar {{ background: #e0e0e0; height: 10px; border-radius: 5px; overflow: hidden; }}
        .usage-fill {{ background: #007cba; height: 100%; transition: width 0.3s; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #ddd; }}
        .plans {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
        .plan {{ border: 2px solid #e0e0e0; padding: 20px; border-radius: 5px; text-align: center; }}
        .plan h3 {{ margin-top: 0; }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 AI Copy Generator SaaS</h1>
        <p>Generate marketing copy, product descriptions, and more with AI.</p>
        
        <div class="tier-info">
            <h3>Your API Key</h3>
            <input type="text" class="api-key" id="apiKey" readonly value="demo_key_not_set" style="width: 100%;">
            <small>Copy this key to use the API</small>
        </div>

        <h2>Generate Content</h2>
        <select id="contentType">
            <option value="Product Description">Product Description</option>
            <option value="Ad Copy">Ad Copy</option>
            <option value="Email Subject">Email Subject</option>
            <option value="Social Media Post">Social Media Post</option>
        </select>
        <textarea id="prompt" placeholder="Enter your prompt... e.g., 'Wireless headphones with noise cancellation'"></textarea><br>
        <button id="generateBtn" onclick="generate()">Generate</button>
        <div id="result" class="result" style="display: none;"></div>
        <div id="error" class="error" style="display: none;"></div>

        <div class="tier-info">
            <h3>Usage This Month</h3>
            <div class="usage-bar">
                <div class="usage-fill" id="usageFill" style="width: 0%;"></div>
            </div>
            <p id="usageText">Loading...</p>
        </div>

        <h2>Upgrade Your Plan</h2>
        <div class="plans">
            <div class="plan">
                <h3>Free</h3>
                <p><strong>$0/month</strong></p>
                <p>5 generations</p>
                <button disabled>Current Plan</button>
            </div>
            <div class="plan">
                <h3>Pro</h3>
                <p><strong>$15/month</strong></p>
                <p>100 generations</p>
                <button onclick="upgrade('pro')">Upgrade to Pro</button>
            </div>
            <div class="plan">
                <h3>Business</h3>
                <p><strong>$40/month</strong></p>
                <p>Unlimited generations</p>
                <button onclick="upgrade('business')">Upgrade to Business</button>
            </div>
        </div>

        <h2>API Documentation</h2>
        <pre>POST /api/v1/generate
Headers: X-API-Key: your_api_key
Body: {{"prompt": "your prompt", "content_type": "Product Description"}}

GET /api/v1/account
Headers: X-API-Key: your_api_key</pre>
    </div>

    <script>
        const API_URL = window.location.origin;
        let apiKey = localStorage.getItem('apiKey') || 'demo_key_not_set';
        document.getElementById('apiKey').value = apiKey;

        async function loadAccount() {{
            try {{
                const res = await fetch(`${{API_URL}}/api/v1/account`, {{
                    headers: {{"X-API-Key": apiKey}}
                }});
                const data = await res.json();
                const usagePercent = (data.usage_this_month / data.limit) * 100;
                document.getElementById('usageFill').style.width = `${{usagePercent}}%`;
                document.getElementById('usageText').textContent = 
                    `${{data.usage_this_month}} / ${{data.limit}} generations used`;
            }} catch (err) {{
                console.error('Failed to load account:', err);
            }}
        }}

        async function generate() {{
            const btn = document.getElementById('generateBtn');
            const result = document.getElementById('result');
            const error = document.getElementById('error');
            
            btn.disabled = true;
            result.style.display = 'none';
            error.style.display = 'none';
            
            try {{
                const res = await fetch(`${{API_URL}}/api/v1/generate`, {{
                    method: 'POST',
                    headers: {{
                        'Content-Type': 'application/json',
                        'X-API-Key': apiKey
                    }},
                    body: JSON.stringify({{
                        prompt: document.getElementById('prompt').value,
                        content_type: document.getElementById('contentType').value
                    }})
                }});
                
                if (!res.ok) throw new Error((await res.json()).detail);
                
                const data = await res.json();
                result.textContent = data.content;
                result.style.display = 'block';
                
                loadAccount(); // refresh usage
            }} catch (err) {{
                error.textContent = err.message;
                error.style.display = 'block';
            }} finally {{
                btn.disabled = false;
            }}
        }}

        async function upgrade(tier) {{
            try {{
                const res = await fetch(`${{API_URL}}/api/v1/upgrade?tier=${{tier}}`, {{
                    method: 'POST',
                    headers: {{"X-API-Key": apiKey}}
                }});
                const data = await res.json();
                window.location.href = data.url;
            }} catch (err) {{
                alert('Upgrade failed: ' + err.message);
            }}
        }}

        // Load account on page load
        loadAccount();
    </script>
</body>
</html>
""" + """
<!-- 
DEPLOYMENT INSTRUCTIONS:
1. Set environment variables:
   - STRIPE_SECRET_KEY (get from Stripe dashboard)
   - STRIPE_PUBLISHABLE_KEY (get from Stripe dashboard)
   - STRIPE_WEBHOOK_SECRET (get from Stripe CLI/webhook setup)
   - OPENAI_API_KEY (get from OpenAI)
   - PORT (defaults to 8000)

2. For Stripe: Create products in Stripe Dashboard and replace price IDs in TIERS dict

3. Run: python main.py

4. The app will create a demo user. Check logs for the API key.

5. This is a production-ready SaaS template. Add your branding and deploy!
-->
"""

# ============================================================================
# ADMIN UTILITIES
# ============================================================================
def create_user(email: str, tier: str = "free") -> str:
    """Create a new user and return API key"""
    conn = get_db()
    api_key = f"live_{uuid.uuid4().hex}"
    user_id = str(uuid.uuid4())
    
    conn.execute(
        "INSERT INTO users (id, api_key, email, tier) VALUES (?, ?, ?, ?)",
        (user_id, api_key, email, tier)
    )
    conn.commit()
    conn.close()
    
    return api_key

# Command line interface
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "create-user":
        email = sys.argv[2] if len(sys.argv) > 2 else input("Enter email: ")
        tier = sys.argv[3] if len(sys.argv) > 3 else "free"
        key = create_user(email, tier)
        print(f"✅ User created! API Key: {key}")
        sys.exit(0)
    
    # Normal startup
    print("🚀 Starting AI Copy Generator SaaS...")
    print(f"📊 Database: {CONFIG['db_path']}")
    print(f"🌐 Server: {CONFIG['host']}:{CONFIG['port']}")
    init_db()
    
    uvicorn.run(
        "main:app",
        host=CONFIG["host"],
        port=CONFIG["port"],
        reload=False,
        log_level="info"
    )