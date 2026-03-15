from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import math
import csv
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = "attendance_secret_key"

attendance_open = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
USERS_FILE = os.path.join(BASE_DIR, "users.csv")
ATTENDANCE_FILE = os.path.join(BASE_DIR, "attendance.csv")

# College Location
COLLEGE_LAT = 18.489105
COLLEGE_LON = 73.810561
RADIUS_KM = 0.5


# ---------------- LOGIN PAGES ----------------

@app.route('/')
def login():
    return render_template("login.html")


@app.route('/student_login')
def student_login():
    return render_template("Student_login.html")


@app.route('/faculty_login')
def faculty_login():
    return render_template("Faculty_login.html")


# ---------------- CHECK USER ----------------

def check_user(user_id, password):

    with open(USERS_FILE, 'r') as file:
        reader = csv.reader(file)

        next(reader)  # skip header row

        for row in reader:
            if row[0].strip() == user_id and row[1].strip() == password:
                return row[2].strip()

    return None


# ---------------- LOGIN SYSTEM ----------------

@app.route('/login', methods=['POST'])
def check_login():

    user_id = request.form['student_id']
    password = request.form['password']

    ip = request.remote_addr

    role = check_user(user_id, password)

    if role == "student":

        # WiFi Check (Mobile Hotspot example)
        if not (ip.startswith("10.181") or ip == "127.0.0.1"):
            return "Connect to College WiFi / Hotspot"

        session['role'] = "student"
        session['user_id'] = user_id

        return redirect(url_for('student_dashboard'))

    elif role == "faculty":

        session['role'] = "faculty"
        return redirect(url_for('faculty_dashboard'))

    else:
        return "Invalid Login"


# ---------------- STUDENT DASHBOARD ----------------

@app.route('/student_dashboard')
def student_dashboard():

    if 'role' in session and session['role'] == "student":
        return render_template("student_dashboard.html", attendance_open=attendance_open)

    return "Access Denied"


# ---------------- FACULTY DASHBOARD ----------------

@app.route('/faculty_dashboard')
def faculty_dashboard():

    if 'role' in session and session['role'] == "faculty":

        schedule = []

        if os.path.exists("schedule.csv"):
            with open("schedule.csv", "r") as file:
                reader = csv.DictReader(file)
                for row in reader:
                    schedule.append(row)

        return render_template(
            "faculty_dashboard.html",
            attendance_open=attendance_open,
            schedule=schedule
        )

    return "Access Denied"


# ---------------- OPEN ATTENDANCE ----------------

@app.route('/open_attendance', methods=['POST'])
def open_attendance():

    global attendance_open
    attendance_open = True

    return redirect(url_for('faculty_dashboard'))


# ---------------- CLOSE ATTENDANCE ----------------

@app.route('/close_attendance', methods=['POST'])
def close_attendance():

    global attendance_open
    attendance_open = False

    return redirect(url_for('faculty_dashboard'))

# ---------------- Update Schedule ----------------
@app.route('/faculty_schedule')
def faculty_schedule():

    schedule = []

    with open('schedule.csv', 'r') as file:
        reader = csv.DictReader(file)
        for row in reader:
            schedule.append(row)

    return render_template("faculty_dashboard.html", schedule=schedule)

@app.route('/update_schedule', methods=['POST'])
def update_schedule():

    faculty_id = request.form['faculty_id']
    day = request.form['day']
    subject = request.form['subject']
    batch = request.form['batch']
    time = request.form['time']

    rows = []
    updated = False

    if os.path.exists("schedule.csv"):
        with open("schedule.csv", "r") as file:
            reader = csv.DictReader(file)

            for row in reader:

                if row['faculty_id'] == faculty_id and row['day'] == day:
                    row['subject'] = subject
                    row['batch'] = batch
                    row['time'] = time
                    updated = True

                rows.append(row)

    # If schedule not found → add new
    if not updated:
        rows.append({
            "faculty_id": faculty_id,
            "day": day,
            "subject": subject,
            "batch": batch,
            "time": time
        })

    with open("schedule.csv", "w", newline="") as file:
        fieldnames = ['faculty_id','day','subject','batch','time']
        writer = csv.DictWriter(file, fieldnames=fieldnames)

        writer.writeheader()
        writer.writerows(rows)

    return redirect(url_for('faculty_dashboard'))


# ---------------- LOCATION CHECK ----------------

def is_in_college(lat, lon):

    R = 6371

    dlat = math.radians(lat - COLLEGE_LAT)
    dlon = math.radians(lon - COLLEGE_LON)

    a = math.sin(dlat/2)**2 + math.cos(math.radians(COLLEGE_LAT)) * math.cos(math.radians(lat)) * math.sin(dlon/2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

    distance = R * c

    return distance <= RADIUS_KM


# ---------------- MARK ATTENDANCE ----------------

@app.route('/mark_attendance', methods=['POST'])
def mark_attendance():

    global attendance_open

    if not attendance_open:
        return jsonify({"message": "Attendance session is closed."})

    data = request.json
    lat = float(data.get('latitude'))
    lon = float(data.get('longitude'))
    subject = str(data.get('subject'))

    if not subject:
        return jsonify({"message": "Subject not selected"})

    if is_in_college(lat, lon):

        student_id = session['user_id']
        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")

        # Check duplicate attendance
        if not os.path.exists(ATTENDANCE_FILE):
            with open(ATTENDANCE_FILE, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(["student_id","subject","date","time"])

        with open(ATTENDANCE_FILE, 'r') as f:
            reader = csv.reader(f)
            next(reader, None)

            for row in reader:
                if len(row) < 3:
                    continue
                if row[0] == student_id and row[1] == subject and row[2] == date:
                     return jsonify({"message": "Attendance already marked for this subject today!"})


        # Save attendance
        with open(ATTENDANCE_FILE, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([student_id, subject, date, time])

        return jsonify({"message": "Attendance Marked Successfully"})

    else:
        return jsonify({"message": "You are not in college location!"})


if not os.path.exists("schedule.csv"):
    with open("schedule.csv","w",newline="") as f:
        writer = csv.writer(f)
        writer.writerow(['faculty_id','day','subject','batch','time'])
# ---------------- ATTENDANCE HISTORY ----------------
@app.route('/attendance_history')
def attendance_history():

    history = {}

    if os.path.exists(ATTENDANCE_FILE):

        with open(ATTENDANCE_FILE, 'r') as file:
            reader = csv.DictReader(file)

            for row in reader:

                key = (row['date'], row['subject'])

                if key not in history:
                    history[key] = {
                        "date": row['date'],
                        "subject": row['subject'],
                        "class": "AD-1",
                        "total": 60,
                        "present": 0
                    }

                history[key]["present"] += 1

    history_list = list(history.values())

    return render_template(
        "faculty_dashboard.html",
        attendance_open=attendance_open,
        history=history_list
    )


# ---------------- LOGOUT ----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------------- RUN APP ----------------

if __name__ == '__main__':
   app.run(host="0.0.0.0", port=5000, debug=True)