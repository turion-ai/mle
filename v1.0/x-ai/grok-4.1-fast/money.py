import os
import httpx
from typing import Optional, List, Dict, Any
from fastapi import FastAPI, Request, HTTPException, Header, Body, Depends
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from openai import AsyncOpenAI
import redis.asyncio as redis
from contextlib import asynccontextmanager

# Environment variables
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
DOMAIN = os.getenv("DOMAIN", "localhost:8000")
REDIS_URL = os.getenv("REDIS_URL")

if not all([STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, OPENAI_API_KEY]):
    raise ValueError("Missing required env vars: STRIPE_SECRET_KEY, STRIPE_PUBLISHABLE_KEY, OPENAI_API_KEY")

redis_client = redis.from_url(REDIS_URL) if REDIS_URL else None

SYSTEM_PROMPT = """You are MoneyBot, an expert Python developer, entrepreneur, and online money-making expert.
You love creating profitable online businesses, SaaS products, affiliate sites, trading bots, and more.
Provide practical, step-by-step plans, code snippets, marketing tips, and actionable strategies to help users make real money online FAST.
Be optimistic, direct, and focus on low-cost, high-profit ideas that can scale.
If code is needed, provide full, runnable Python scripts."""

app = FastAPI(title="MoneyMaker AI", description="AI-powered money-making advisor. Free trial: 5 queries/hour. Pro: $10/1000 queries.")

HTML_INDEX = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MoneyMaker AI - Make Money Online</title>
    <script src="https://js.stripe.com/v3/"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; color: #333; }
        .container { background: white; border-radius: 20px; box-shadow: 0 20px 40px rgba(0,0,0,0.1); max-width: 800px; width: 90%; max-height: 90vh; display: flex; flex-direction: column; overflow: hidden; }
        h1 { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; text-align: center; padding: 20px; font-size: 2em; }
        .status { text-align: center; padding: 10px; background: #f0f8ff; font-weight: bold; }
        .pro { color: #28a745; }
        .free { color: #ffc107; }
        #messages { flex: 1; overflow-y: auto; padding: 20px; background: #fafafa; }
        .message { margin-bottom: 15px; padding: 12px 16px; border-radius: 18px; max-width: 80%; word-wrap: break-word; }
        .user { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; margin-left: auto; text-align: right; }
        .assistant { background: white; border: 1px solid #e0e0e0; margin-right: auto; }
        .input-container { display: flex; padding: 20px; border-top: 1px solid #eee; }
        #message { flex: 1; padding: 12px 16px; border: 1px solid #ddd; border-radius: 25px; outline: none; }
        button { margin-left: 10px; padding: 12px 24px; border: none; border-radius: 25px; cursor: pointer; font-weight: bold; transition: transform 0.2s; }
        #send { background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%); color: white; }
        #pay { background: linear-gradient(135deg, #28a745 0%, #20c997 100%); color: white; }
        button:hover { transform: scale(1.05); }
        button:disabled { opacity: 0.5; cursor: not-allowed; transform: none; }
        .error { color: #dc3545; background: #f8d7da; border: 1px solid #f5c6cb; }
    </style>
</head>
<body>
    <div class="container">
        <h1>💰 MoneyMaker AI</h1>
        <div id="status" class="status free">Free Trial: 5 queries/hour per IP. <button id="pay" style="font-size: 0.9em; padding: 4px 12px; margin-left: 10px;">Upgrade Pro ($10/1000)</button></div>
        <div id="messages"></div>
        <div class="input-container">
            <input id="message" placeholder="Ask me: 'Build a SaaS that makes $10k/month' or 'Crypto trading bot code'...">
            <button id="send">Send 🚀</button>
        </div>
    </div>
    <script>
        let chatHistory = [];
        let stripe = null;
        const token = localStorage.getItem('proToken');
        const messagesEl = document.getElementById('messages');
        const statusEl = document.getElementById('status');
        const payBtn = document.getElementById('pay');
        const sendBtn = document.getElementById('send');
        const messageInput = document.getElementById('message');

        // Handle success redirect
        const urlParams = new URLSearchParams(window.location.search);
        const sessionId = urlParams.get('session_id');
        if (sessionId && urlParams.get('status') === 'cancelled') {
            statusEl.textContent = 'Payment cancelled. Try again?';
            statusEl.className = 'status error';
        } else if (sessionId) {
            localStorage.setItem('proToken', sessionId);
            window.history.replaceState({}, document.title, '/');
            location.reload();
        }

        if (token) {
            statusEl.innerHTML = '✅ Pro Access Active! <span class="pro">(1000 queries)</span>';
            payBtn.style.display = 'none';
        }

        async function initStripe() {
            const res = await fetch('/config');
            const {stripe_pk} = await res.json();
            stripe = Stripe(stripe_pk);
        }

        payBtn.onclick = async () => {
            const email = prompt('Email for receipt (optional):');
            if (!stripe) await initStripe();
            try {
                const res = await fetch('/create-checkout-session', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({email: email || null})
                });
                const {sessionId} = await res.json();
                await stripe.redirectToCheckout({sessionId});
            } catch (e) {
                alert('Error: ' + e.message);
            }
        };

        sendBtn.onclick = sendMessage;
        messageInput.onkeypress = (e) => { if (e.key === 'Enter') sendMessage(); };

        async function sendMessage() {
            const msg = messageInput.value.trim();
            if (!msg) return;
            messageInput.value = '';
            sendBtn.disabled = true;
            addMessage('user', msg);
            chatHistory.push({role: 'user', content: msg});
            try {
                const res = await fetch('/chat', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        ...(token && {'Authorization': `Bearer ${token}`})
                    },
                    body: JSON.stringify({messages: chatHistory.slice(-20)})
                });
                if (!res.ok) {
                    const err = await res.json();
                    throw new Error(err.detail || 'Server error');
                }
                const {response} = await res.json();
                addMessage('assistant', response);
                chatHistory.push({role: 'assistant', content: response});
            } catch (e) {
                addMessage('assistant', `❌ ${e.message}`);
            }
            sendBtn.disabled = false;
            messageInput.focus();
        }

        function addMessage(role, content) {
            const div = document.createElement('div');
            div.className = `message ${role}`;
            div.textContent = content;
            messagesEl.appendChild(div);
            messagesEl.scrollTop = messagesEl.scrollHeight;
        }

        initStripe();
    </script>
</body>
</html>"""

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]

def get_openai_client():
    return AsyncOpenAI(api_key=OPENAI_API_KEY)

@app.post("/chat")
async def chat(
    request: Request,
    chat_req: ChatRequest,
    authorization: Optional[str] = Header(None),
    client: AsyncOpenAI = Depends(get_openai_client)
):
    token = None
    if authorization and authorization.startswith("Bearer "):
        token = authorization[7:].strip()

    if not redis_client:
        raise HTTPException(503, "Redis not configured")

    r = redis_client
    ip = request.client.host

    if not token:
        # Free tier
        free_key = f"free:{ip}"
        count = await r.incr(free_key)
        if count == 1:
            await r.expire(free_key, 3600)
        if count > 5:
            raise HTTPException(402, "Free limit: 5 queries/hour. Upgrade to Pro!")
    else:
        # Pro tier
        paid_key = f"paid:{token}"
        if not await r.exists(paid_key):
            async with httpx.AsyncClient() as http:
                resp = await http.get(
                    f"https://api.stripe.com/v1/checkout/sessions/{token}",
                    headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"}
                )
                data = resp.json()
                if resp.status_code != 200 or data.get("payment_status") != "paid":
                    raise HTTPException(401, "Invalid Pro token")
                await r.set(paid_key, "1", ex=30 * 24 * 3600)  # 30 days
        count_key = f"count:{token}"
        count = await r.incr(count_key)
        if count == 1:
            await r.expire(count_key, 30 * 24 * 3600)
        if count > 1000:
            raise HTTPException(402, "Pro limit: 1000 queries. Buy again!")

    # Generate response
    try:
        messages = [{"role": "system", "content": SYSTEM_PROMPT}] + chat_req.messages[-20:]
        completion = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            temperature=0.7,
            max_tokens=1500
        )
        return {"response": completion.choices[0].message.content}
    except Exception as e:
        raise HTTPException(500, f"AI Error: {str(e)}")

@app.post("/create-checkout-session")
async def create_checkout_session(email: Optional[str] = Body(None)):
    data = {
        "payment_method_types": ["card"],
        "mode": "payment",
        "success_url": f"https://{DOMAIN}/?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"https://{DOMAIN}/?status=cancelled",
        "line_items": [{
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": "MoneyMaker AI Pro",
                    "description": "1000 queries with expert money-making AI advisor 💰",
                    "metadata": {"domain": DOMAIN}
                },
                "unit_amount": 1000
            },
            "quantity": 1
        }]
    }
    if email:
        data["customer_email"] = email

    async with httpx.AsyncClient() as http:
        resp = await http.post(
            "https://api.stripe.com/v1/checkout/sessions",
            headers={"Authorization": f"Bearer {STRIPE_SECRET_KEY}"},
            data=data
        )
        if resp.status_code != 200:
            raise HTTPException(400, resp.text)
        session_data = resp.json()
        return {"sessionId": session_data["id"]}

@app.get("/config")
async def config():
    return {"stripe_pk": STRIPE_PUBLISHABLE_KEY}

@app.get("/", response_class=HTMLResponse)
async def index():
    return HTML_INDEX

@asynccontextmanager
async def lifespan(app_: FastAPI):
    yield
    if redis_client:
        await redis_client.aclose()

app.router.lifespan_context = lifespan

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)