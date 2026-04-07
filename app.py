from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import bcrypt
import re
from collections import defaultdict
from datetime import datetime

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

    # Ensure date column exists
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

# 📊 REAL ANALYTICS
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

    # 💰 totals
    income = sum(t["amount"] for t in transactions if t["amount"] > 0)
    expenses = abs(sum(t["amount"] for t in transactions if t["amount"] < 0))

    # 📊 category totals
    category_totals = {}
    for t in transactions:
        category = t["category"]
        amount = abs(t["amount"])
        category_totals[category] = category_totals.get(category, 0) + amount

    labels = list(category_totals.keys())
    values = list(category_totals.values())

    # 🥇 top categories
    sorted_categories = sorted(category_totals.items(), key=lambda x: x[1], reverse=True)
    top_categories = sorted_categories[:3]

    # 📅 REAL monthly data
    monthly_data = defaultdict(float)

    for t in transactions:
        if t["date"]:
            dt = datetime.strptime(t["date"], "%Y-%m-%d")
            month = dt.strftime("%b %Y")
        else:
            month = "Unknown"

        monthly_data[month] += abs(t["amount"])

    # sort months
    def sort_key(m):
        if m == "Unknown":
            return datetime.min
        return datetime.strptime(m, "%b %Y")

    sorted_months = sorted(monthly_data.keys(), key=sort_key)

    month_labels = sorted_months
    month_values = [monthly_data[m] for m in sorted_months]

    # 💡 insights
    insights = []

    if sorted_categories:
        top = sorted_categories[0]
        insights.append(f"You spend the most on {top[0]}.")

        if expenses > 0 and top[1] > expenses * 0.5:
            insights.append(f"{top[0]} takes over 50% of your spending.")

    if income > 0:
        savings = income - expenses
        rate = (savings / income) * 100

        if rate < 20:
            insights.append("Your savings rate is low. Try to save at least 20%.")
        else:
            insights.append("Great! Your savings rate is healthy.")

    return render_template(
        'analytics.html',
        income=income,
        expenses=expenses,
        labels=labels,
        values=values,
        top_categories=top_categories,
        insights=insights,
        month_labels=month_labels,
        month_values=month_values
    )

# ➕ Add transaction (WITH DATE)
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

# ▶️ Run
if __name__ == '__main__':
    app.run()