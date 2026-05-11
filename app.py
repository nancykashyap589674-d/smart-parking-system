from flask import Flask, render_template, request, redirect, url_for, session, flash
import smtplib
import random
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import qrcode
import os
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')

app = Flask(__name__)
app.secret_key = 'supersecretkey'

# -------------------------------
# POSTGRESQL CONNECTION
# -------------------------------
import psycopg2

import os
DATABASE_URL = os.environ.get("DATABASE_URL")

conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
def get_cursor():
    global conn

    try:
        conn.poll()
    except:
        conn = psycopg2.connect(DATABASE_URL)
        conn.autocommit = True

    return conn.cursor()

print("Connected to PostgreSQL successfully")

cursor = get_cursor()
cursor.execute("""
CREATE TABLE IF NOT EXISTS parking_slots (
    id SERIAL PRIMARY KEY,
    slot_name VARCHAR(50) UNIQUE,
    status VARCHAR(20),
    email VARCHAR(100),
    name VARCHAR(100),
    phone VARCHAR(20),
    carname VARCHAR(50),
    carnumber VARCHAR(50),
    time VARCHAR(50)
)
""")


# Slots already managed in PostgreSQL database

# -------------------------------
# EMAIL CONFIGURATION
# -------------------------------
import os
SENDER_EMAIL = os.environ.get("EMAIL_USER")
SENDER_PASSWORD = os.environ.get("EMAIL_PASSWORD")

# -------------------------------
# GENERATE QR
# -------------------------------
def generate_qr(email):
    filename = f"{email}.png"
    qr_folder = os.path.join("static", "qrcodes")
    if not os.path.exists(qr_folder):
        os.makedirs(qr_folder)

    path = os.path.join(qr_folder, filename)

    data = request.host_url + "parking_entry?email=" + email + "&slot=ALL"

    qr = qrcode.make(data)
    qr.save(path)

    return filename

# -------------------------------
# HOME PAGE
# -------------------------------
@app.route('/')
def home():
    return render_template('choose_login.html')

# -------------------------------
# ADMIN LOGIN
# -------------------------------
@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        if username == "admin" and password == "1234":
         session['admin'] = True   # ✅ ADD THIS LINE
         flash("Login successful", "success")
         return redirect('/admin_dashboard')
        else:
            flash("Invalid username or password", "error")
            return redirect('/admin_login')

    return render_template('admin_login.html')

# -------------------------------
# ADMIN DASHBOARD
# -------------------------------
@app.route('/admin_dashboard')
def admin_dashboard():
    if 'admin' not in session:
     return redirect('/admin_login')

    # Fetch data
    cursor = get_cursor()
    cursor.execute("SELECT * FROM parking_slots")
    slots = cursor.fetchall()

    free_slots = len([s for s in slots if s[2] == 'free'])
    occupied_slots = len([s for s in slots if s[2] == 'occupied'])

    # -------------------------------
    # STATIC FOLDER PATH
    # -------------------------------
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    STATIC_DIR = os.path.join(BASE_DIR, "static")

    # Create static folder if not exists
    if not os.path.exists(STATIC_DIR):
        os.makedirs(STATIC_DIR)

    # -------------------------------
    # GRAPH DATA
    # -------------------------------
    labels = ['Free', 'Occupied']
    values = [free_slots, occupied_slots]

    # -------------------------------
    # BAR CHART
    # -------------------------------
    bar_path = os.path.join(STATIC_DIR, "bar_chart.png")

    plt.figure(figsize=(5, 4))
    plt.bar(labels, values, color=['green', 'red'])
    plt.title("Parking Slots Status")
    plt.tight_layout()
    plt.savefig(bar_path, dpi=100)
    plt.close('all')

    # -------------------------------
    # PIE CHART
    # -------------------------------
    pie_path = os.path.join(STATIC_DIR, "pie_chart.png")

    plt.figure(figsize=(5, 4))
    plt.pie(values, labels=labels, autopct='%1.1f%%')
    plt.title("Parking Distribution")
    plt.tight_layout()
    plt.savefig(pie_path, dpi=100)
    plt.close('all')

    # -------------------------------
    # RETURN TO HTML
    # -------------------------------
    return render_template(
        "admin_dashboard.html",
        slots=slots,
        free_slots=free_slots,
        occupied_slots=occupied_slots,
        bar_chart="bar_chart.png",
        pie_chart="pie_chart.png"
    )

# -------------------------------
# LOGIN WITH EMAIL + OTP
# -------------------------------
@app.route('/login_email', methods=['GET', 'POST'])
def login_email():
    if request.method == 'POST':
        email = request.form['email']

        otp = random.randint(100000, 999999)
        
        session['otp'] = otp
        session['temp_email'] = email

        try:
            msg = MIMEMultipart()
            msg['From'] = SENDER_EMAIL
            msg['To'] = email
            msg['Subject'] = "Smart Parking System - OTP"

            body = f"Your OTP is: {otp}"
            msg.attach(MIMEText(body, 'plain'))
            server = smtplib.SMTP("smtp-relay.brevo.com", 587, timeout=60)
            
            server.starttls()
            
            print("EMAIL:", SENDER_EMAIL)
            print("PASSWORD EXISTS:", SENDER_PASSWORD is not None)
            print("OTP:", otp)

            server.login(SENDER_EMAIL, SENDER_PASSWORD)

            
            text = msg.as_string()

            server.sendmail(SENDER_EMAIL, email, text)

            server.quit()

            flash("OTP sent successfully!")
        except Exception as e:
            flash(f"Error: {str(e)}")

        return redirect(url_for('verify_otp'))

    return render_template('login_email.html')

# -------------------------------
# VERIFY OTP
# -------------------------------
@app.route('/verify_otp', methods=['GET', 'POST'])
def verify_otp():
    if request.method == 'POST':
        entered_otp = request.form['otp']
        saved_otp = str(session.get('otp'))

        if entered_otp == saved_otp:
            session['user'] = session.get('temp_email')
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid OTP")

    return render_template('verify_otp.html')

# -------------------------------
# DASHBOARD
# -------------------------------
@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect(url_for('login_email'))

    email = session['user']
    qr_file = generate_qr(email)

    cursor = get_cursor()
    cursor.execute("SELECT * FROM parking_slots")
    slots = cursor.fetchall()

    total_slots = len(slots)
    free_slots = len([s for s in slots if s[2] == 'free'])
    occupied_slots = len([s for s in slots if s[2] == 'occupied'])

    return render_template(
        "dashboard.html",
        email=email,
        slots=slots,
        total_slots=total_slots,
        free_slots=free_slots,
        occupied_slots=occupied_slots,
        qr_file=qr_file
    )

# -------------------------------
# LIVE SLOT UPDATE
# -------------------------------
@app.route('/get_slots')
def get_slots():
    cursor = get_cursor()
    cursor.execute("SELECT * FROM parking_slots")
    slots = cursor.fetchall()
    return {"slots": [list(s) for s in slots]}

# -------------------------------
# PARKING ENTRY PAGE
# -------------------------------
@app.route('/parking_entry')
def parking_entry():

    email = request.args.get('email')

    if not email:
        return redirect(url_for('login_email'))

    # get user's booked slots
    cursor = get_cursor()
    cursor.execute(
    "SELECT * FROM parking_slots WHERE email=%s AND status='occupied'",
    (email,)
)

    user_slots = cursor.fetchall() or []
    

    # get all slots
    cursor = get_cursor()
    cursor.execute("SELECT * FROM parking_slots")
    slots = cursor.fetchall()

    return render_template(
        "parking_entry.html",
        email=email,
        slots=slots,
        user_slots=user_slots
    )

@app.route('/exit_page')
def exit_page():
    email = request.args.get('email')
    cursor = get_cursor()
    cursor.execute(
        "SELECT * FROM parking_slots WHERE email=%s AND status='occupied'",
        (email,)
    )
    user_slots = cursor.fetchall() or []

    return render_template("exit.html", slots=user_slots, email=email)

# -------------------------------
# BOOK SLOT
# -------------------------------
@app.route('/book_slot', methods=['POST'])
def book_slot():

    slot_name = request.form['slot']
    email = request.form.get('email')
    name = request.form['name']
    phone = request.form['phone']
    carname = request.form['carname']
    carnumber = request.form['carnumber']
    time = request.form['time']

    

    # check if slot already occupied
    cursor = get_cursor()
    cursor.execute("SELECT status FROM parking_slots WHERE slot_name=%s", (slot_name,))
    result = cursor.fetchone()

    if result and result[0] == 'occupied':
        return {"status": "error", "message": "Already booked"}

    # update slot
    cursor = get_cursor()
    cursor.execute("""
    UPDATE parking_slots 
    SET status='occupied',
        email=%s,
        name=%s,
        phone=%s,
        carname=%s,
        carnumber=%s,
        time=%s
    WHERE slot_name=%s
    """, (email, name, phone, carname, carnumber, time, slot_name))

    conn.commit()

    return {"status": "success"}

# -------------------------------
# EXIT SLOT
# -------------------------------
@app.route('/exit_slot', methods=['POST'])
def exit_slot():

    slot = request.form['slot']
    cursor = get_cursor()
    cursor.execute("""
    UPDATE parking_slots
    SET status='free',
        email=NULL,
        name=NULL,
        phone=NULL,
        carname=NULL,
        carnumber=NULL,
        time=NULL
    WHERE slot_name=%s
    """, (slot,))

    conn.commit()

    return {"status": "success"}

# -------------------------------
# LOGOUT
# -------------------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login_email'))

# -------------------------------
# RUN
# -------------------------------
if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000))
    )

