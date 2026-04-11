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
            email TEXT UNIQUE,
            password BLOB
        )
    ''')

    try:
        conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
    except:
        pass

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
        'SELECT * FROM transactions WHERE user_id=?',
        (session["user_id"],)
    ).fetchall()
    conn.close()

    income = sum(t["amount"] for t in transactions if t["amount"] > 0)
    expenses = sum(t["amount"] for t in transactions if t["amount"] < 0)
    balance = income + expenses

    return render_template('index.html',
                           transactions=transactions,
                           income=income,
                           expenses=expenses,
                           balance=balance)

# 👤 PROFILE
@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    conn = get_db_connection()

    if request.method == 'POST':
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")

        if username:
            conn.execute("UPDATE users SET username=? WHERE id=?",
                         (username, session["user_id"]))

        if email:
            conn.execute("UPDATE users SET email=? WHERE id=?",
                         (email, session["user_id"]))

        if password:
            if is_strong_password(password):
                hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
                conn.execute("UPDATE users SET password=? WHERE id=?",
                             (hashed, session["user_id"]))
            else:
                return "Weak password!"

        conn.commit()

    user = conn.execute("SELECT * FROM users WHERE id=?",
                        (session["user_id"],)).fetchone()
    conn.close()

    return render_template("profile.html", user=user)

# 🔐 SIGNUP
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')

        if not is_strong_password(password):
            return "Weak password!"

        hashed = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (username, email, password) VALUES (?, ?, ?)',
                (username, email, hashed)
            )
            conn.commit()
        except:
            return "Username or email already exists"

        conn.close()
        return redirect(url_for('login'))

    return render_template('signup.html')

# 🔐 LOGIN (username OR email)
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

# 🔁 FORGOT PASSWORD (NEW 🔥)
@app.route('/forgot', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email')
        new_password = request.form.get('password')

        if not is_strong_password(new_password):
            return "Weak password!"

        conn = get_db_connection()
        user = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()

        if not user:
            conn.close()
            return "Email not found"

        hashed = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt())

        conn.execute(
            "UPDATE users SET password=? WHERE email=?",
            (hashed, email)
        )
        conn.commit()
        conn.close()

        return redirect(url_for('login'))

    return render_template('forgot.html')

# 🚪 LOGOUT
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for("login"))

# ▶️ RUN
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)