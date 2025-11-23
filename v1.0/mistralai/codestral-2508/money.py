import os
import string
import random
from flask import Flask, request, redirect, render_template, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.middleware.proxy_fix import ProxyFix

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

# Configure database
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///urls.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# URL model
class URL(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    original_url = db.Column(db.String(500), nullable=False)
    short_url = db.Column(db.String(10), unique=True, nullable=False)
    clicks = db.Column(db.Integer, default=0)

    def __repr__(self):
        return f'<URL {self.short_url}>'

# Create tables
with app.app_context():
    db.create_all()

# Generate a random short URL
def generate_short_url():
    characters = string.ascii_letters + string.digits
    short_url = ''.join(random.choice(characters) for _ in range(6))
    return short_url

# Home page
@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        original_url = request.form['original_url']
        short_url = generate_short_url()

        # Check if the short URL already exists
        while URL.query.filter_by(short_url=short_url).first():
            short_url = generate_short_url()

        new_url = URL(original_url=original_url, short_url=short_url)
        db.session.add(new_url)
        db.session.commit()

        return render_template('home.html', short_url=short_url)

    return render_template('home.html')

# Redirect to original URL
@app.route('/<short_url>')
def redirect_to_url(short_url):
    url = URL.query.filter_by(short_url=short_url).first_or_404()
    url.clicks += 1
    db.session.commit()

    # Add affiliate tracking or ads here
    # For example, you can append an affiliate ID to the original URL
    # original_url = f"{url.original_url}?affiliate_id=YOUR_AFFILIATE_ID"

    return redirect(url.original_url)

# Dashboard to view URL statistics
@app.route('/dashboard')
def dashboard():
    urls = URL.query.all()
    return render_template('dashboard.html', urls=urls)

if __name__ == '__main__':
    app.run(debug=True)