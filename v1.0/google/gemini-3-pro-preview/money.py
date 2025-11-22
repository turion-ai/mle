import os
import stripe
from flask import Flask, redirect, jsonify

app = Flask(__name__)

# Load keys from environment variables
# Note: You must provide the SECRET key for the backend to work.
# The Publishable key is typically sent to the frontend.
stripe.api_key = os.getenv('STRIPE_SECRET_KEY')
YOUR_DOMAIN = 'http://localhost:4242' # Replace with your public domain

@app.route('/')
def index():
    return "Welcome to the Payment Server. Navigate to /checkout to purchase."

@app.route('/checkout', methods=['GET']) # In production, use POST
def create_checkout_session():
    try:
        # Create a Checkout Session
        # This tells Stripe what you are selling and how much it costs.
        session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=[{
                'price_data': {
                    'currency': 'usd',
                    'product_data': {
                        'name': 'Generic Product',
                    },
                    'unit_amount': 2000,  # Amount in cents ($20.00)
                },
                'quantity': 1,
            }],
            mode='payment',
            success_url=YOUR_DOMAIN + '/success',
            cancel_url=YOUR_DOMAIN + '/cancel',
        )
        # Redirect the user to the Stripe Checkout Page
        return redirect(session.url, code=303)
    except Exception as e:
        return jsonify(error=str(e)), 403

@app.route('/success')
def success():
    return "Payment Successful! Funds will be deposited according to Stripe's payout schedule."

@app.route('/cancel')
def cancel():
    return "Payment Canceled."

if __name__ == '__main__':
    # Run the server on port 4242
    app.run(host='0.0.0.0', port=4242)