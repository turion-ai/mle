import os
import time
import uuid
from datetime import datetime, timedelta
from functools import wraps
import logging
from typing import Dict, List, Optional

import stripe
from flask import Flask, request, jsonify, render_template_string, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import redis
import psycopg2
from psycopg2.extras import RealDictCursor
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuration
class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-change-in-prod-'+str(uuid.uuid4()))
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://mle_user:mle_pass@db:5432/mle_db')
    REDIS_URL = os.getenv('REDIS_URL', 'redis://redis:6379')
    STRIPE_API_KEY = os.getenv('STRIPE_API_KEY')
    STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET')
    STRIPE_PRICE_PRO = os.getenv('STRIPE_PRICE_PRO', 'price_123pro')
    STRIPE_PRICE_PREMIUM = os.getenv('STRIPE_PRICE_PREMIUM', 'price_456premium')
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
    PORT = int(os.getenv('PORT', 5000))
    APP_URL = os.getenv('APP_URL', f'http://localhost:{PORT}')

config = Config()

# Initialize Flask app
app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY

# Initialize services
if config.STRIPE_API_KEY:
    stripe.api_key = config.STRIPE_API_KEY
redis_client = redis.from_url(config.REDIS_URL)

# Database helper functions
def get_db():
    """Get database connection"""
    return psycopg2.connect(config.DATABASE_URL)

def init_db():
    """Initialize database tables"""
    conn = get_db()
    cur = conn.cursor()
    
    # Enable UUID extension
    try:
        cur.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    except:
        pass
    
    # Users table
    cur.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            api_key TEXT UNIQUE NOT NULL DEFAULT uuid_generate_v4(),
            tier TEXT DEFAULT 'free',
            company_name TEXT,
            stripe_customer_id TEXT,
            subscription_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Usage tracking
    cur.execute('''
        CREATE TABLE IF NOT EXISTS usage (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            user_id UUID NOT NULL REFERENCES users(id),
            endpoint TEXT NOT NULL,
            tokens_used INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes
    cur.execute('CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_users_api_key ON users(api_key)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_usage_user_id ON usage(user_id)')
    cur.execute('CREATE INDEX IF NOT EXISTS idx_usage_date ON usage(created_at)')
    
    conn.commit()
    cur.close()
    conn.close()
    logger.info("✅ Database initialized")

# Initialize database
init_db()

# Rate limiting decorator
def rate_limit(f):
    """Rate limit based on user tier"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        api_key = request.headers.get('X-API-Key')
        if not api_key:
            return jsonify({'error': 'X-API-Key header required'}), 401
        
        # Get user from API key
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT id, tier FROM users WHERE api_key = %s", (api_key,))
        user = cur.fetchone()
        
        if not user:
            cur.close()
            conn.close()
            return jsonify({'error': 'Invalid API key'}), 401
        
        # Determine limit
        limits = {'free': 10, 'pro': 100, 'premium': 1000}
        user_limit = limits.get(user['tier'], 10)
        
        # Check Redis rate limit
        key = f"rate:{user['id']}:{datetime.utcnow().date()}"
        current = redis_client.get(key)
        
        if current and int(current) >= user_limit:
            cur.close()
            conn.close()
            return jsonify({
                'error': 'Rate limit exceeded',
                'limit': user_limit,
                'tier': user['tier'],
                'upgrade_url': f"{config.APP_URL}/dashboard"
            }), 429
        
        # Increment counter
        pipe = redis_client.pipeline()
        pipe.incr(key)
        pipe.expire(key, 86400)
        pipe.execute()
        
        cur.close()
        conn.close()
        return f(*args, user_id=user['id'], **kwargs)
    return decorated_function

# Authentication decorator
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# HTML Templates
HOME_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>AI Content API - Monetized ML Service</title>
    <style>
        body { font-family: system-ui, -apple-system, sans-serif; margin: 0; padding: 0; background: #f7fafc; }
        .container { max-width: 1000px; margin: 0 auto; padding: 20px; }
        .header { display: flex; justify-content: space-between; padding: 20px; background: white; border-radius: 8px; margin-bottom: 30px; }
        .hero { background: linear-gradient(90deg, #667eea 0%, #764ba2 100%); color: white; padding: 60px; border-radius: 12px; text-align: center; }
        .pricing { display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px; margin-top: 40px; }
        .plan { background: white; padding: 30px; border-radius: 8px; text-align: center; }
        .plan.featured { border: 2px solid #667eea; }
        .btn { background: #667eea; color: white; padding: 12px 24px; text-decoration: none; border-radius: 6px; display: inline-block; }
        pre { background: #2d3748; color: #e2e8f0; padding: 16px; border-radius: 6px; overflow-x: auto; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🚀 AI Content API</h1>
            <div>
                {% if session.user_email %}
                    <a href="{{ url_for('dashboard') }}">Dashboard</a> | 
                    <a href="{{ url_for('logout') }}">Logout</a>
                {% else %}
                    <a href="{{ url_for('login') }}">Login</a> | 
                    <a href="{{ url_for('register') }}">Register</a>
                {% endif %}
            </div>
        </div>
        
        <div class="hero">
            <h1>Generate High-Quality Content with AI</h1>
            <p>API-driven content generation for agencies, marketers, and developers. Monetize your content pipeline.</p>
        </div>
        
        <h2>Quick Start</h2>
        <pre>curl -X POST {{ request.url_root }}api/v1/generate \
  -H "X-API-Key: YOUR_API_KEY" \
  -d '{"prompt": "AI in healthcare", "type": "blog"}'</pre>
        
        <div class="pricing">
            <div class="plan">
                <h3>Free</h3>
                <h2>$0</h2>
                <p>10 requests/day</p>
                <a href="{{ url_for('register') }}" class="btn">Get Started</a>
            </div>
            <div class="plan featured">
                <h3>Pro 💼</h3>
                <h2>$49/mo</h2>
                <p>100 requests/day</p>
                <p>Priority support</p>
                <a href="{{ url_for('dashboard') }}" class="btn">Upgrade</a>
            </div>
            <div class="plan">
                <h3>Premium 🚀</h3>
                <h2>$199/mo</h2>
                <p>1,000 requests/day</p>
                <p>White-label</p>
                <a href="{{ url_for('dashboard') }}" class="btn">Contact Sales</a>
            </div>
        </div>
    </div>
</body>
</html>
"""

DASHBOARD_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Dashboard - AI Content API</title>
    <style>
        body { font-family: sans-serif; margin: 40px; background: #f7fafc; }
        .card { background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }
        .api-key { background: #2d3748; color: #e2e8f0; padding: 10px; font-family: monospace; }
        .btn { background: #667eea; color: white; padding: 10px 20px; text-decoration: none; border-radius: 4px; }
    </style>
</head>
<body>
    <h1>Dashboard</h1>
    
    <div class="card">
        <h2>API Key</h2>
        <div class="api-key">{{ user.api_key }}</div>
    </div>
    
    <div class="card">
        <h2>Plan: {{ user.tier|title }}</h2>
        <p>Requests today: {{ usage_today }} / {{ limit }}</p>
        {% if user.tier == 'free' %}
            <a href="{{ url_for('create_checkout_session', tier='pro') }}" class="btn">Upgrade to Pro</a>
        {% elif user.tier == 'pro' %}
            <a href="{{ url_for('create_checkout_session', tier='premium') }}" class="btn">Upgrade to Premium</a>
        {% endif %}
    </div>
    
    <div class="card">
        <h2>API Example</h2>
        <pre>curl -X POST {{ request.url_root }}api/v1/generate \
  -H "X-API-Key: {{ user.api_key }}" \
  -d '{"prompt": "AI trends", "type": "blog", "max_length": 800}'</pre>
    </div>
    
    <a href="{{ url_for('index') }}">← Back to Home</a>
</body>
</html>
"""

# Routes
@app.route('/')
def index():
    """Home page"""
    return render_template_string(HOME_TEMPLATE)

@app.route('/register', methods=['GET', 'POST'])
def register():
    """User registration"""
    if request.method == 'POST':
        data = request.get_json() or request.form
        email = data.get('email')
        password = data.get('password')
        
        if not email or not password:
            return jsonify({'error': 'Email and password required'}), 400
        
        conn = get_db()
        cur = conn.cursor()
        
        try:
            # Check existing
            cur.execute("SELECT email FROM users WHERE email = %s", (email,))
            if cur.fetchone():
                return jsonify({'error': 'Email already exists'}), 400
            
            # Create Stripe customer
            customer = stripe.Customer.create(email=email)
            
            # Create user
            password_hash = generate_password_hash(password)
            cur.execute(
                "INSERT INTO users (email, password_hash, stripe_customer_id) VALUES (%s, %s, %s) RETURNING api_key",
                (email, password_hash, customer.id)
            )
            api_key = cur.fetchone()[0]
            conn.commit()
            
            # Auto-login
            session['user_email'] = email
            
            return jsonify({'api_key': api_key, 'message': 'Registration successful'}), 201
        except Exception as e:
            conn.rollback()
            logger.error(f"Registration error: {e}")
            return jsonify({'error': 'Registration failed'}), 500
        finally:
            cur.close()
            conn.close()
    
    return render_template_string("""
    <div style="max-width: 400px; margin: 40px auto; padding: 20px; background: white; border-radius: 8px;">
        <h1>Register</h1>
        <form method="post">
            <input type="email" name="email" placeholder="Email" required style="width: 100%; padding: 10px; margin: 10px 0;"><br>
            <input type="password" name="password" placeholder="Password" required style="width: 100%; padding: 10px; margin: 10px 0;"><br>
            <button type="submit" style="width: 100%; padding: 12px; background: #667eea; color: white; border: none; border-radius: 4px;">Register</button>
        </form>
    </div>
    """)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """User login"""
    if request.method == 'POST':
        data = request.get_json() or request.form
        email = data.get('email')
        password = data.get('password')
        
        conn = get_db()
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT email, password_hash, api_key, tier FROM users WHERE email = %s", (email,))
        user = cur.fetchone()
        cur.close()
        conn.close()
        
        if user and check_password_hash(user['password_hash'], password):
            session['user_email'] = user['email']
            session['user_id'] = user['api_key']
            return jsonify({'api_key': user['api_key'], 'tier': user['tier']})
        
        return jsonify({'error': 'Invalid credentials'}), 401
    
    return render_template_string("""
    <div style="max-width: 400px; margin: 40px auto; padding: 20px; background: white; border-radius: 8px;">
        <h1>Login</h1>
        <form method="post">
            <input type="email" name="email" placeholder="Email" required style="width: 100%; padding: 10px; margin: 10px 0;"><br>
            <input type="password" name="password" placeholder="Password" required style="width: 100%; padding: 10px; margin: 10px 0;"><br>
            <button type="submit" style="width: 100%; padding: 12px; background: #667eea; color: white; border: none; border-radius: 4px;">Login</button>
        </form>
    </div>
    """)

@app.route('/logout')
def logout():
    """User logout"""
    session.clear()
    return redirect(url_for('index'))

@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    
    cur.execute("SELECT api_key, tier FROM users WHERE email = %s", (session['user_email'],))
    user = cur.fetchone()
    
    # Get today's usage
    cur.execute(
        "SELECT COUNT(*) as count FROM usage WHERE user_id = (SELECT id FROM users WHERE email = %s) AND created_at >= CURRENT_DATE",
        (session['user_email'],)
    )
    usage_today = cur.fetchone()['count']
    
    cur.close()
    conn.close()
    
    limits = {'free': 10, 'pro': 100, 'premium': 1000}
    limit = limits.get(user['tier'], 10)
    
    return render_template_string(DASHBOARD_TEMPLATE, user=user, usage_today=usage_today, limit=limit)

@app.route('/create-checkout-session/<tier>')
@login_required
def create_checkout_session(tier):
    """Create Stripe checkout session"""
    if tier not in ['pro', 'premium']:
        return jsonify({'error': 'Invalid tier'}), 400
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute("SELECT stripe_customer_id FROM users WHERE email = %s", (session['user_email'],))
    user = cur.fetchone()
    cur.close()
    conn.close()
    
    if not user or not user['stripe_customer_id']:
        return jsonify({'error': 'No Stripe customer'}), 400
    
    try:
        price_id = config.STRIPE_PRICE_PRO if tier == 'pro' else config.STRIPE_PRICE_PREMIUM
        checkout_session = stripe.checkout.Session.create(
            customer=user['stripe_customer_id'],
            payment_method_types=['card'],
            line_items=[{'price': price_id, 'quantity': 1}],
            mode='subscription',
            success_url=f"{config.APP_URL}/dashboard",
            cancel_url=f"{config.APP_URL}/dashboard",
        )
        return redirect(checkout_session.url)
    except Exception as e:
        logger.error(f"Stripe error: {e}")
        return jsonify({'error': 'Payment failed'}), 500

@app.route('/webhook', methods=['POST'])
def webhook():
    """Stripe webhook handler"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, config.STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({'error': 'Invalid signature'}), 400
    
    # Handle subscription events
    if event['type'] == 'customer.subscription.created':
        subscription = event['data']['object']
        customer_id = subscription['customer']
        price_id = subscription['items']['data'][0]['price']['id']
        tier = 'pro' if price_id == config.STRIPE_PRICE_PRO else 'premium'
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET tier = %s, subscription_id = %s WHERE stripe_customer_id = %s",
            (tier, subscription['id'], customer_id)
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"User {customer_id} upgraded to {tier}")
    
    elif event['type'] == 'customer.subscription.deleted':
        subscription = event['data']['object']
        
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "UPDATE users SET tier = 'free', subscription_id = NULL WHERE subscription_id = %s",
            (subscription['id'],)
        )
        conn.commit()
        cur.close()
        conn.close()
        logger.info(f"Subscription {subscription['id']} canceled")
    
    return '', 200

# API Routes
@app.route('/api/v1/generate', methods=['POST'])
@rate_limit
def generate(user_id):
    """Generate AI content"""
    data = request.json
    prompt = data.get('prompt', '').strip()
    content_type = data.get('type', 'blog')
    max_length = min(data.get('max_length', 500), 2000)
    
    if not prompt or len(prompt) < 10:
        return jsonify({'error': 'Prompt must be at least 10 characters'}), 400
    
    # Generate content
    try:
        if config.OPENAI_API_KEY:
            response = requests.post(
                'https://api.openai.com/v1/completions',
                headers={
                    'Authorization': f'Bearer {config.OPENAI_API_KEY}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'gpt-3.5-turbo-instruct',
                    'prompt': f"Write {content_type} content about: {prompt}",
                    'max_tokens': max_length,
                    'temperature': 0.7
                },
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            content = result['choices'][0]['text']
            tokens_used = result['usage']['total_tokens']
        else:
            # Mock generation for demo
            content = f"[Demo] {content_type.title()} content about: {prompt}\n\n"
            content += "This is a demonstration. In production, integrate OpenAI API."
            tokens_used = len(content.split())
    except Exception as e:
        logger.error(f"Generation error: {e}")
        return jsonify({'error': 'Content generation failed'}), 500
    
    # Track usage
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO usage (user_id, endpoint, tokens_used) VALUES (%s, %s, %s)",
            (user_id, 'generate', tokens_used)
        )
        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"Usage tracking error: {e}")
    
    return jsonify({
        'content': content,
        'tokens_used': tokens_used,
        'tier': request.user_tier if hasattr(request, 'user_tier') else 'unknown'
    })

@app.route('/api/v1/usage', methods=['GET'])
@rate_limit
def get_usage(user_id):
    """Get usage statistics"""
    days = request.args.get('days', 30, type=int)
    
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)
    cur.execute(
        """
        SELECT 
            DATE(created_at) as date,
            COUNT(*) as requests,
            SUM(tokens_used) as tokens
        FROM usage
        WHERE user_id = %s AND created_at >= CURRENT_DATE - INTERVAL '%s days'
        GROUP BY DATE(created_at)
        ORDER BY date DESC
        """,
        (user_id, days)
    )
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    return jsonify({
        'usage': [{
            'date': row['date'].isoformat(),
            'requests': row['requests'],
            'tokens': row['tokens']
        } for row in rows],
        'total_requests': sum(r['requests'] for r in rows),
        'total_tokens': sum(r['tokens'] for r in rows)
    })

@app.route('/health')
def health():
    """Health check endpoint"""
    try:
        redis_client.ping()
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        return jsonify({'status': 'healthy', 'services': ['db', 'redis']}), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({'status': 'unhealthy', 'error': str(e)}), 500

if __name__ == '__main__':
    # Run on all interfaces for containerization
    app.run(host='0.0.0.0', port=config.PORT, debug=config.DEBUG)