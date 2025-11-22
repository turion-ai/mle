import os
import stripe
from flask import Flask, request, jsonify, render_template
import json

# Load environment variables
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
stripe_publishable_key = os.getenv('STRIPE_PUBLISHABLE_KEY')

app = Flask(__name__)

# Configure Stripe
stripe.api_key = stripe.api_key  # Already set above

@app.route('/')
def index():
    """Render payment page"""
    return render_template('payment.html', publishable_key=stripe_publishable_key)

@app.route('/create-payment-intent', methods=['POST'])
def create_payment_intent():
    """Create a payment intent for a customer"""
    try:
        data = request.get_json()
        amount = data.get('amount', 1000)  # Default $10.00 (in cents)
        currency = data.get('currency', 'usd')
        
        # Create PaymentIntent
        payment_intent = stripe.PaymentIntent.create(
            amount=amount,
            currency=currency,
            payment_method_types=['card'],
            metadata={
                'customer_name': data.get('customer_name', 'Anonymous'),
                'product': data.get('product', 'Generic Product')
            }
        )
        
        return jsonify({
            'clientSecret': payment_intent.client_secret,
            'paymentIntentId': payment_intent.id
        })
    
    except Exception as e:
        return jsonify(error=str(e)), 400

@app.route('/webhook', methods=['POST'])
def webhook_received():
    """Handle Stripe webhooks"""
    payload = request.data
    sig_header = request.headers.get('Stripe-Signature')
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.getenv('STRIPE_WEBHOOK_SECRET')
        )
    except ValueError as e:
        return jsonify(error=str(e)), 400
    except stripe.error.SignatureVerificationError as e:
        return jsonify(error=str(e)), 400
    
    # Handle the event
    if event['type'] == 'payment_intent.succeeded':
        payment_intent = event['data']['object']
        print(f"Payment succeeded: {payment_intent.id}")
        # You can add additional logic here for successful payments
    
    return jsonify(success=True)

@app.route('/success')
def success():
    """Success page after payment"""
    return "<h1>Payment Successful!</h1><p>Thank you for your payment.</p>"

@app.route('/cancel')
def cancel():
    """Cancel page if payment fails"""
    return "<h1>Payment Cancelled</h1><p>Payment was cancelled. Please try again.</p>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)