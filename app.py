from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import bcrypt
import re
from collections import defaultdict
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"

# DB
def get_db_connection():
    conn = sqlite3.connect('fintech.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()

    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            email TEXT UNIQUE,
            password BLOB
        )
    ''')

    conn.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            description TEXT,
            amount REAL,
            category TEXT,
            date TEXT
        )
    ''')

    conn.commit()
    conn.close()

init_db()

# Password check
def is_strong_password(password):
    return len(password) >= 8

# Dashboard
@app.route('/')
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    transactions = conn.execute(
        'SELECT * FROM transactions WHERE user_id=?',
        (session["user_id"],)
    ).fetchall()
    conn.close()

    income = sum(t["amount"] for t in transactions if t["amount"] > 0)
    expenses = sum(t["amount"] for t in transactions if t["amount"] < 0)
    balance = income + expenses

    today = datetime.now().strftime("%Y-%m-%d")

    return render_template(
        'index.html',
        transactions=transactions,
        income=income,
        expenses=expenses,
        balance=balance,
        today=today
    )

# ADD TRANSACTION (FIXED DATE)
@app.route('/add', methods=['POST'])
def add_transaction():
    if "user_id" not in session:
        return redirect(url_for("login"))

    description = request.form.get('description')
    amount = float(request.form.get('amount'))
    category = request.form.get('category')
    t_type = request.form.get('type')
    date = request.form.get('date')

    # ✅ FIXED DATE HANDLING
    if not date or date == "":
        date = datetime.now().strftime("%Y-%m-%d")

    if t_type == "expense":
        amount = -abs(amount)
    else:
        amount = abs(amount)

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO transactions (user_id, description, amount, category, date) VALUES (?, ?, ?, ?, ?)',
        (session["user_id"], description, amount, category, date)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('home'))

# TRANSACTIONS
@app.route('/transactions')
def transactions_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    transactions = conn.execute(
        'SELECT * FROM transactions WHERE user_id=?',
        (session["user_id"],)
    ).fetchall()
    conn.close()

    return render_template('transactions.html', transactions=transactions)

# ANALYTICS (SAFE DATE FIX)
@app.route('/analytics')
def analytics():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    transactions = conn.execute(
        'SELECT * FROM transactions WHERE user_id=?',
        (session["user_id"],)
    ).fetchall()
    conn.close()

    income = sum(t["amount"] for t in transactions if t["amount"] > 0)
    expenses = abs(sum(t["amount"] for t in transactions if t["amount"] < 0))

    # Categories
    category_totals = {}
    for t in transactions:
        category = t["category"]
        amount = abs(t["amount"])
        category_totals[category] = category_totals.get(category, 0) + amount

    labels = list(category_totals.keys())
    values = list(category_totals.values())

    # Monthly
    monthly_data = defaultdict(float)
    for t in transactions:
        try:
            dt = datetime.strptime(t["date"], "%Y-%m-%d")
            month = dt.strftime("%b %Y")
        except:
            month = "Unknown"

        monthly_data[month] += abs(t["amount"])

    month_labels = list(monthly_data.keys())
    month_values = list(monthly_data.values())

    return render_template(
        'analytics.html',
        income=income,
        expenses=expenses,
        labels=labels,
        values=values,
        month_labels=month_labels,
        month_values=month_values
    )

# LOGIN
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_input = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username=? OR email=?',
            (user_input, user_input)
        ).fetchone()
        conn.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user["password"]):
            session["user_id"] = user["id"]
            return redirect(url_for("home"))

        return "Invalid login"

    return render_template('login.html')

# SIGNUP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, hashed)
            )
            conn.commit()
        except:
            return "Username or email exists"

        conn.close()
        return redirect(url_for('login'))

    return render_template('signup.html')

# LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))

# RUN
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)