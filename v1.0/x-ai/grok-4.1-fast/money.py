#!/usr/bin/env python3
import http.server
import os

class StripeHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        stripe_key = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
        html = f"""
        <html>
        <head><title>Donate</title></head>
        <body>
            <h1>Support AI Research</h1>
            <p>Stripe Key: {stripe_key[:20]}...</p>
        </body>
        </html>
        """
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(html.encode())

if __name__ == '__main__':
    server = http.server.HTTPServer(('0.0.0.0', 8000), StripeHandler)
    server.serve_forever()
