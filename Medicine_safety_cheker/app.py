from flask import Flask, render_template, request, redirect, session
import mysql.connector
import json

app = Flask(__name__)
app.secret_key = "your_secret_key"

# ----------------- DATABASE CONNECTIONS -----------------
conn_users = mysql.connector.connect(
    host="localhost",
    user="root",
    password="medicine@123",
    database="user_db"
)
cur_user = conn_users.cursor(dictionary=True, buffered=True)

conn_meds = mysql.connector.connect(
    host="localhost",
    user="root",
    password="medicine@123",
    database="medicines_db"
)
cur_meds = conn_meds.cursor(dictionary=True, buffered=True)

# ----------------- HOME PAGE -----------------
@app.route('/')
def home():
    # Redirect if logged in
    if 'user_id' in session:
        if session['role'] == 'admin':
            return redirect('/admin_dashboard')
        else:
            return redirect('/user_dashboard')
    return render_template('index.html')


# ----------------- LOGIN -----------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        role_input = request.form['role'].strip().lower()  # 'user' or 'admin' from form

        # Fetch user from DB
        cur_user.execute("SELECT * FROM users WHERE username=%s", (username,))
        user = cur_user.fetchone()

        if user:
            db_role = user['role'].strip().lower()  # force lowercase
            if user['password'] == password and db_role == role_input:
                # Save session
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = db_role  # lowercase 'user' or 'admin'
                session['age'] = user['age']

                # Redirect strictly based on role
                if db_role == 'user':
                    return redirect('/user_dashboard')
                else:
                    return redirect('/admin_dashboard')
        
        # If login failed
        return render_template('login.html', error="Invalid username, password, or role.")

    return render_template('login.html')

# ----------------- REGISTER -----------------
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        first_name = request.form['first_name'].strip()
        last_name = request.form['last_name'].strip()
        username = request.form['username'].strip()
        password = request.form['password']
        age = int(request.form['age'])
        role = request.form['role'].strip().lower()

        try:
            cur_user.execute(
                "INSERT INTO users (first_name, last_name, username, password, age, role) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (first_name, last_name, username, password, age, role)
            )
            conn_users.commit()
            return redirect('/login')
        except:
            return render_template('register.html', error="Username already exists")

    return render_template('register.html')


# ----------------- USER DASHBOARD -----------------
@app.route('/user_dashboard', methods=['GET', 'POST'])
def user_dashboard():
    if 'user_id' not in session or session['role'] != 'user':
        return redirect('/login')

    # Fetch all medicines from the database
    cur_meds.execute("SELECT name, dosage_mg, max_dosage_mg, purpose FROM medicines")
    medicines = cur_meds.fetchall()

    if request.method == 'POST':
        med_names = request.form.getlist('medicines')
        med_dosages = request.form.getlist('dosages')   # ✅ FIXED (was dosages_mg)

        data = []
        total_dosage = 0
        age = session['age']

        # Safe limit logic
        
        if 5 <= age <= 10:
            safe_limit = 700 
        elif 12 <= age <= 30:
            safe_limit = 3000
        elif age >=60:
            safe_limit = 1500
        else:
            safe_limit=2000


        # 🔥 FIXED LOOP (handles empty inputs properly)
        for name, dose in zip(med_names, med_dosages):

            # ✅ Skip empty fields
            if name.strip() == "" or dose.strip() == "":
                continue

            cur_meds.execute(
                "SELECT name, dosage_mg, max_dosage_mg, purpose FROM medicines WHERE name=%s",
                (name,)
            )
            med_info = cur_meds.fetchone()

            if not med_info:
                continue

            taken = int(dose)
            total_dosage += taken

            # Risk calculation
            if total_dosage <= safe_limit:
                risk = "Low"
            elif total_dosage <= safe_limit * 1.2:
                risk = "Medium"
            else:
                risk = "High"

            data.append({
                'name': med_info['name'],
                'taken': taken,
                'max': med_info['max_dosage_mg'],
                'purpose': med_info['purpose'],
                'risk': risk
            })

        # ✅ If no valid medicines entered
        if len(data) == 0:
            return render_template('user_dashboard.html',
                                   user={'username': session['username'], 'age': session['age']},
                                   medicines=medicines,
                                   error="Please enter at least one valid medicine")

        # Final result
        if total_dosage <= safe_limit:
            overall = "Low"
        elif total_dosage <= safe_limit * 1.2:
            overall = "Medium"
        else:
            overall = "High"

        analysis = f"Based on the medicines entered, your total dosage is {total_dosage}mg. Risk level is {overall}."
        conclusion = f"Combination of medicines is {overall} risk for your age ({age} years)."

        # Store in session
        session['report_data'] = data
        session['overall'] = overall
        session['analysis'] = analysis
        session['conclusion'] = conclusion

        return redirect('/report')

    return render_template('user_dashboard.html',
                           user={'username': session['username'], 'age': session['age']},
                           medicines=medicines)

# ----------------- REPORT -----------------
@app.template_filter('risk_to_number')
def risk_to_number(risk):
    return 1 if risk == 'Low' else 2 if risk == 'Medium' else 3

@app.template_filter('risk_to_color')
def risk_to_color(risk):
    return 'lightgreen' if risk == 'Low' else 'orange' if risk == 'Medium' else 'red'

@app.route('/report')
def report():
    if 'user_id' not in session or session['role'] != 'user':
        return redirect('/login')

    data = session.get('report_data', [])
    overall = session.get('overall', 'Low')
    analysis = session.get('analysis', '')
    conclusion = session.get('conclusion', '')
    user_info = {'username': session.get('username'), 'age': session.get('age')}

    # Prepare chart data
    labels = json.dumps([d['name'] for d in data])
    data_values = json.dumps([d['taken'] for d in data])
    colors = json.dumps([ 'lightgreen' if d['risk']=='Low' else 'orange' if d['risk']=='Medium' else 'red' for d in data ])

    # Fix table keys: use 'taken' and 'max' keys for dosage columns
    for d in data:
        d['dosage_mg'] = d['taken']
        d['max_dosage_mg'] = d['max']

    return render_template('report.html',
                           data=data,
                           overall=overall,
                           analysis=analysis,
                           conclusion=conclusion,
                           user=user_info,
                           labels=labels,
                           data_values=data_values,
                           colors=colors)

# ----------------- ADMIN DASHBOARD -----------------
@app.route('/admin_dashboard', methods=['GET', 'POST'])
def admin_dashboard():
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect('/login')

    if request.method == 'POST':
        name = request.form['name']
        dosage_mg = float(request.form['dosage_mg'])
        max_dosage_mg = float(request.form['max_dosage_mg'])
        purpose = request.form['purpose']

        cur_meds.execute("SELECT * FROM medicines WHERE name=%s", (name,))
        existing = cur_meds.fetchone()

        if existing:
            cur_meds.execute(
                "UPDATE medicines SET dosage_mg=%s, max_dosage_mg=%s, purpose=%s WHERE name=%s",
                (dosage_mg, max_dosage_mg, purpose, name)
            )
        else:
            cur_meds.execute(
                "INSERT INTO medicines (name, dosage_mg, max_dosage_mg, purpose) VALUES (%s,%s,%s,%s)",
                (name, dosage_mg, max_dosage_mg, purpose)
            )
        conn_meds.commit()

    cur_meds.execute("SELECT * FROM medicines")
    medicines = cur_meds.fetchall()

    return render_template('admin_dashboard.html',
                           user={'username': session['username']},
                           medicines=medicines)
@app.route('/admin_add_update', methods=['POST'])
def admin_add_update():
    # Ensure admin is logged in
    if 'user_id' not in session or session['role'] != 'admin':
        return redirect('/logout')

    # Get data from form
    name = request.form.get('name').strip()
    dosage_mg = request.form.get('dosage_mg').strip()
    max_dosage_mg = request.form.get('max_dosage_mg').strip()
    purpose = request.form.get('purpose').strip()
    status = request.form.get('status', 'Active').strip()

    # If any required field is empty, just redirect back
    if not name or not dosage_mg or not max_dosage_mg or not purpose:
        return redirect('/admin_dashboard')

    # Check if medicine exists
    cur_meds.execute("SELECT * FROM medicines WHERE name=%s", (name,))
    existing = cur_meds.fetchone()

    if existing:
        # Update existing medicine
        cur_meds.execute("""
            UPDATE medicines
            SET dosage_mg=%s, max_dosage_mg=%s, purpose=%s, status=%s
            WHERE name=%s
        """, (dosage_mg, max_dosage_mg, purpose, status, name))
    else:
        # Insert new medicine
        cur_meds.execute("""
            INSERT INTO medicines (name, dosage_mg, max_dosage_mg, purpose, status)
            VALUES (%s, %s, %s, %s, %s)
        """, (name, dosage_mg, max_dosage_mg, purpose, status))

    # Commit the changes
    conn_meds.commit()

    # Redirect back to admin dashboard
    return redirect('/admin_dashboard')


# ----------------- LOGOUT -----------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')


# ----------------- RUN APP -----------------
if __name__ == '__main__':
    app.run(debug=True)
