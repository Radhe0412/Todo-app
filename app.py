# app.py
from flask import Flask, render_template, url_for, request, redirect, session, flash
from flask_session import Session
import pymysql
import os
from datetime import date
from dotenv import load_dotenv

# -------------------------
# LOAD ENV VARIABLES
# -------------------------
load_dotenv()  # Load from .env

# -------------------------
# APP CONFIG
# -------------------------
app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "supersecretkey")
app.config["SESSION_TYPE"] = "filesystem"
app.config["SESSION_PERMANENT"] = False
app.session_cookie_name = 'my_custom_cookie_name'
Session(app)

# -------------------------
# DATABASE CONNECTION
# -------------------------
def get_db_connection():
    try:
        conn = pymysql.connect(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "root"),
            password=os.getenv("DB_PASSWORD", ""),
            db=os.getenv("DB_NAME", "todo_db"),
            port=int(os.getenv("DB_PORT", 3306)),
            cursorclass=pymysql.cursors.DictCursor,
            charset='utf8mb4'
        )
        return conn
    except Exception as e:
        print("Database connection failed:", e)
        return None

# -------------------------
# HELPER FUNCTIONS
# -------------------------
def fetch_count(query, params=()):
    conn = get_db_connection()
    if not conn:
        return 0
    with conn.cursor() as cur:
        cur.execute(query, params)
        result = cur.fetchone()
    conn.close()
    return result['cnt'] if result else 0

# -------------------------
# ROUTES
# -------------------------

@app.route('/')
def home():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_id = session['user_id']
    pending = fetch_count("SELECT COUNT(*) AS cnt FROM tasks WHERE status=0 AND user_id=%s", (user_id,))
    total = fetch_count("SELECT COUNT(*) AS cnt FROM tasks WHERE user_id=%s", (user_id,))
    completed = fetch_count("SELECT COUNT(*) AS cnt FROM tasks WHERE status=1 AND user_id=%s", (user_id,))

    return render_template('user/home.html', pending=pending, total=total, completed=completed)

# -------------------------
# AUTH ROUTES
# -------------------------

@app.route('/register')
def register():
    return render_template('user/register.html')

@app.route('/register_process', methods=['POST'])
def register_process():
    user_name = request.form['user_name']
    contact_no = request.form['contact_no']
    user_email = request.form['user_email']
    user_pass = request.form['user_pass']
    gender = request.form['gender']
    dob = request.form['date']

    conn = get_db_connection()
    if not conn:
        flash("Database connection error!")
        return redirect(url_for('register'))

    with conn.cursor() as cur:
        # Check duplicate email
        cur.execute("SELECT * FROM user_register WHERE user_email=%s", (user_email,))
        if cur.fetchone():
            flash("Email already registered!")
            return redirect(url_for('register'))

        cur.execute("""INSERT INTO user_register 
                       (user_name, contact_no, user_email, user_pass, gender, date, status) 
                       VALUES (%s, %s, %s, %s, %s, %s, 0)""",
                    (user_name, contact_no, user_email, user_pass, gender, dob))
        conn.commit()
    conn.close()

    flash("Registration successful! Please login.")
    return redirect(url_for('login'))

@app.route('/login')
def login():
    return render_template('user/login.html')

@app.route('/login_process', methods=['POST'])
def login_process():
    user_email = request.form['user_email']
    user_pass = request.form['user_pass']

    conn = get_db_connection()
    if not conn:
        flash("Database connection error!")
        return redirect(url_for('login'))

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM user_register WHERE user_email=%s AND user_pass=%s", (user_email, user_pass))
        account = cur.fetchone()
    conn.close()

    if account:
        if account['status'] == 1:
            flash("Your account has been blocked by admin")
            return redirect(url_for('login'))

        # Set session
        session['user_id'] = account['user_id']
        session['user_name'] = account['user_name']
        session['user_email'] = account['user_email']
        session['status'] = account['status']
        return redirect(url_for('home'))

    flash("Incorrect email or password")
    return redirect(url_for('login'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# -------------------------
# TASK ROUTES
# -------------------------
@app.route('/all_tasks')
def all_tasks():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if not conn:
        flash("Database error!")
        return redirect(url_for('home'))

    with conn.cursor() as cur:
        cur.execute("SELECT * FROM tasks WHERE user_id=%s ORDER BY due_date ASC", (session['user_id'],))
        data = cur.fetchall()
    conn.close()

    return render_template('user/all_tasks.html', data=data)

@app.route('/add_task', methods=['GET', 'POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    if request.method == 'POST':
        conn = get_db_connection()
        if not conn:
            flash("Database error!")
            return redirect(url_for('add_task'))

        with conn.cursor() as cur:
            cur.execute("""INSERT INTO tasks
                           (user_id, task_title, task_description, due_date, created_date, priority, status)
                           VALUES (%s, %s, %s, %s, %s, %s, 0)""",
                        (session['user_id'],
                         request.form['task_title'],
                         request.form['task_description'],
                         request.form['due_date'],
                         date.today(),
                         request.form['priority']))
            conn.commit()
        conn.close()
        flash("Task added successfully!")
        return redirect(url_for('home'))

    return render_template('user/add_task.html')

@app.route('/delete_task/<int:task_id>')
def delete_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    if conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tasks WHERE task_id=%s AND user_id=%s", (task_id, session['user_id']))
            conn.commit()
        conn.close()
    return redirect(url_for('all_tasks'))

# -------------------------
# RUN APP
# -------------------------
if __name__ == "__main__":
    app.run(debug=True)
