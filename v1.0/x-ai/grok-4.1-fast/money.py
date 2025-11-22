#!/usr/bin/env python3
import http.server
import socketserver

class MoneyHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b'<h1>AI Money Generator</h1>')

PORT = 8000
with socketserver.TCPServer(("", PORT), MoneyHandler) as httpd:
    print(f"Server running on port {PORT}")
    httpd.serve_forever()
