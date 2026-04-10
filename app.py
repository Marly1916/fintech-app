from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import bcrypt
import re
from collections import defaultdict
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = "your_secret_key"

# 🔗 DB connection
def get_db_connection():
    conn = sqlite3.connect('fintech.db')
    conn.row_factory = sqlite3.Row
    return conn

# 🧱 Initialize DB
def init_db():
    conn = get_db_connection()

    conn.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
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

    try:
        conn.execute("ALTER TABLE transactions ADD COLUMN date TEXT")
    except:
        pass

    conn.commit()
    conn.close()

init_db()

# 🔐 Password strength
def is_strong_password(password):
    if len(password) < 8: return False
    if not re.search(r"[A-Z]", password): return False
    if not re.search(r"[a-z]", password): return False
    if not re.search(r"[0-9]", password): return False
    if not re.search(r"[^A-Za-z0-9]", password): return False
    return True

# 🏠 Dashboard
@app.route('/')
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    transactions = conn.execute(
        'SELECT * FROM transactions WHERE user_id = ?',
        (session["user_id"],)
    ).fetchall()
    conn.close()

    income = sum(t["amount"] for t in transactions if t["amount"] > 0)
    expenses = sum(t["amount"] for t in transactions if t["amount"] < 0)
    balance = income + expenses

    return render_template(
        'index.html',
        transactions=transactions,
        income=income,
        expenses=expenses,
        balance=balance
    )

# 💳 Transactions
@app.route('/transactions')
def transactions_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    transactions = conn.execute(
        'SELECT * FROM transactions WHERE user_id = ?',
        (session["user_id"],)
    ).fetchall()
    conn.close()

    return render_template('transactions.html', transactions=transactions)

# 👤 PROFILE (UPDATED FEATURE 🔥)
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    if request.method == 'POST':
        new_username = request.form.get("username")
        new_password = request.form.get("password")

        if new_username:
            conn.execute(
                "UPDATE users SET username = ? WHERE id = ?",
                (new_username, session["user_id"])
            )

        if new_password:
            if is_strong_password(new_password):
                hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())
                conn.execute(
                    "UPDATE users SET password = ? WHERE id = ?",
                    (hashed, session["user_id"])
                )
            else:
                return "Password not strong enough!"

        conn.commit()

    user = conn.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    conn.close()

    return render_template("profile.html", user=user)

# 📊 Analytics
@app.route('/analytics')
def analytics():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()
    transactions = conn.execute(
        'SELECT * FROM transactions WHERE user_id = ?',
        (session["user_id"],)
    ).fetchall()
    conn.close()

    income = sum(t["amount"] for t in transactions if t["amount"] > 0)
    expenses = abs(sum(t["amount"] for t in transactions if t["amount"] < 0))

    category_totals = {}
    for t in transactions:
        category = t["category"]
        amount = abs(t["amount"])
        category_totals[category] = category_totals.get(category, 0) + amount

    labels = list(category_totals.keys())
    values = list(category_totals.values())

    monthly_data = defaultdict(float)
    for t in transactions:
        if t["date"]:
            dt = datetime.strptime(t["date"], "%Y-%m-%d")
            month = dt.strftime("%b %Y")
        else:
            month = "Unknown"

        monthly_data[month] += abs(t["amount"])

    sorted_months = sorted(
        monthly_data.keys(),
        key=lambda m: datetime.strptime(m, "%b %Y") if m != "Unknown" else datetime.min
    )

    month_labels = sorted_months
    month_values = [monthly_data[m] for m in sorted_months]

    return render_template(
        'analytics.html',
        income=income,
        expenses=expenses,
        labels=labels,
        values=values,
        month_labels=month_labels,
        month_values=month_values
    )

# ➕ Add transaction
@app.route('/add', methods=['POST'])
def add_transaction():
    if "user_id" not in session:
        return redirect(url_for("login"))

    description = request.form.get('description')
    amount = float(request.form.get('amount'))
    category = request.form.get('category')
    date = datetime.now().strftime("%Y-%m-%d")

    conn = get_db_connection()
    conn.execute(
        'INSERT INTO transactions (user_id, description, amount, category, date) VALUES (?, ?, ?, ?, ?)',
        (session["user_id"], description, amount, category, date)
    )
    conn.commit()
    conn.close()

    return redirect(url_for('home'))

# 🔐 Signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        if not is_strong_password(password):
            return "Weak password!"

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (username, password) VALUES (?, ?)',
                (username, hashed)
            )
            conn.commit()
        except:
            return "Username already exists"

        conn.close()
        return redirect(url_for('login'))

    return render_template('signup.html')

# 🔐 Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ?',
            (username,)
        ).fetchone()
        conn.close()

        if user and bcrypt.checkpw(password.encode('utf-8'), user["password"]):
            session["user_id"] = user["id"]
            return redirect(url_for("home"))

        return "Invalid login"

    return render_template('login.html')

# 🚪 Logout
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))

# ▶️ Run (Railway ready)
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)