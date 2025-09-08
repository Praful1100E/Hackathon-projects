from flask import Flask, request, redirect, url_for, flash, send_file, render_template_string
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import pandas as pd
from ortools.sat.python import cp_model
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

EXCEL_DATA_FILE = 'data.xlsx'
EXCEL_TIMETABLE_FILE = 'timetable.xlsx'

USERS = {
    'admin': {'password': generate_password_hash('admin123'), 'role': 'admin'},
    'faculty1': {'password': generate_password_hash('faculty123'), 'role': 'faculty'},
    'depthead': {'password': generate_password_hash('dept123'), 'role': 'dept_head'}
}

class User(UserMixin):
    def __init__(self, username):
        self.id = username
        self.role = USERS[username]['role']
    def check_password(self, password):
        return check_password_hash(USERS[self.id]['password'], password)

@login_manager.user_loader
def load_user(user_id):
    if user_id in USERS:
        return User(user_id)
    return None

def load_excel_sheets():
    if not os.path.exists(EXCEL_DATA_FILE):
        dfs = {
            'Faculty': pd.DataFrame(columns=['ID', 'Name', 'Department', 'Availability', 'Max_Load']),
            'Classroom': pd.DataFrame(columns=['ID', 'Name', 'Capacity', 'Type']),
            'Subject': pd.DataFrame(columns=['ID', 'Name', 'Department', 'Credits', 'Weekly_Classes']),
            'Batch': pd.DataFrame(columns=['ID', 'Program', 'Semester', 'Students'])
        }
        with pd.ExcelWriter(EXCEL_DATA_FILE) as writer:
            for sheet, df in dfs.items():
                df.to_excel(writer, sheet_name=sheet, index=False)
        return dfs
    xls = pd.ExcelFile(EXCEL_DATA_FILE)
    return {sheet: xls.parse(sheet) for sheet in xls.sheet_names}

def save_excel_sheets(dfs):
    with pd.ExcelWriter(EXCEL_DATA_FILE) as writer:
        for sheet, df in dfs.items():
            df.to_excel(writer, sheet_name=sheet, index=False)

BASE_TEMPLATE = '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <title>{{ title }}</title>
    <style>
        body { background-color:#121212; color:#00ffff; font-family: Arial, sans-serif; margin: 0; padding: 0;}
        nav { background-color:#222; padding: 0.5em 1em; display:flex; justify-content: space-between; align-items: center;}
        nav a {color:#00ced1; margin-left:1em; text-decoration:none;}
        nav a:hover {color:#009999;}
        .container { max-width: 900px; margin: 2em auto; padding: 1em; background:#222; border-radius:8px;}
        input, select, textarea, button {background:#222; color:#00ffff; border:1px solid #00ced1; padding:0.4em; margin-top:0.5em; width:100%;}
        button {background:#00ced1; border:none; cursor:pointer; margin-top:1em;}
        button:hover {background:#009999;}
        table {width:100%; border-collapse: collapse; margin-top:1em;}
        th, td {border:1px solid #00ced1; padding:0.5em; text-align:left;}
        th {background:#009999;}
        .flash {background:#00ffff; color:#000; padding:1em; border-radius:6px; margin-bottom:1em;}
        .logout {margin-left:auto;}
    </style>
</head>
<body>
<nav>
    <div><strong>Smart Timetable</strong></div>
    <div>
    {% if current_user.is_authenticated %}
        <a href="{{ url_for('dashboard') }}">Dashboard</a>
        <a href="{{ url_for('view_data') }}">View Data</a>
        <a href="{{ url_for('generate_timetable') }}">Generate Timetable</a>
        <a href="{{ url_for('view_timetable') }}">View Timetable</a>
        <a href="{{ url_for('logout') }}" class="logout">Logout</a>
    {% else %}
        <a href="{{ url_for('login') }}">Login</a>
    {% endif %}
    </div>
</nav>
<div class="container">
    {% with messages = get_flashed_messages() %}
      {% if messages %}
        <div class="flash">
          {% for message in messages %}
            <div>{{ message }}</div>
          {% endfor %}
        </div>
      {% endif %}
    {% endwith %}
    {{ content|safe }}
</div>
</body>
</html>
'''

@app.route('/')
def home():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        u = request.form['username']
        p = request.form['password']
        if u in USERS and User(u).check_password(p):
            login_user(User(u))
            return redirect(url_for('dashboard'))
        flash('Invalid username or password')
    content = '''
    <h2>Login</h2>
    <form method="post">
        <label>Username</label><input name="username" required />
        <label>Password</label><input type="password" name="password" required />
        <button type="submit">Login</button>
    </form>
    '''
    return render_template_string(BASE_TEMPLATE, title='Login', content=content)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    content = f'''
    <h2>Dashboard ({current_user.role})</h2>
    <p>Welcome, {current_user.id}</p>
    '''
    if current_user.role == 'admin':
        content += '''
        <p><a href="/add_entity/faculty">Add Faculty</a></p>
        <p><a href="/add_entity/classroom">Add Classroom</a></p>
        <p><a href="/add_entity/subject">Add Subject</a></p>
        <p><a href="/add_entity/batch">Add Batch</a></p>
        '''
    content += '''
    <p><a href="/view_data">View All Data</a></p>
    <p><a href="/generate_timetable">Generate Timetable</a></p>
    <p><a href="/view_timetable">View Timetable</a></p>
    '''
    return render_template_string(BASE_TEMPLATE, title='Dashboard', content=content)

@app.route('/add_entity/<entity>', methods=['GET','POST'])
@login_required
def add_entity(entity):
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('dashboard'))
    dfs = load_excel_sheets()
    df = dfs.get(entity.capitalize())
    if df is None:
        flash('Unknown entity')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        new_id = int(df['ID'].max() or 0) + 1 if not df.empty else 1
        if entity == 'faculty':
            row = {
                'ID': new_id,
                'Name': request.form['name'],
                'Department': request.form['department'],
                'Availability': request.form.get('availability', ''),
                'Max_Load': int(request.form.get('max_load', 18)),
            }
        elif entity == 'classroom':
            row = {
                'ID': new_id,
                'Name': request.form['name'],
                'Capacity': int(request.form['capacity']),
                'Type': request.form['type']
            }
        elif entity == 'subject':
            row = {
                'ID': new_id,
                'Name': request.form['name'],
                'Department': request.form['department'],
                'Credits': int(request.form['credits']),
                'Weekly_Classes': int(request.form['weekly_classes'])
            }
        elif entity == 'batch':
            row = {
                'ID': new_id,
                'Program': request.form['program'],
                'Semester': int(request.form['semester']),
                'Students': int(request.form['students'])
            }
        else:
            flash('Entity not supported')
            return redirect(url_for('dashboard'))
        df.loc[len(df)] = row
        dfs[entity.capitalize()] = df
        save_excel_sheets(dfs)
        flash(f'{entity.capitalize()} added successfully')
        return redirect(url_for('add_entity', entity=entity))
    fields = {
        'faculty': [('name','text'), ('department','text'), ('availability','text'), ('max_load','number')],
        'classroom': [('name','text'), ('capacity','number'), ('type','text')],
        'subject': [('name','text'), ('department','text'), ('credits','number'), ('weekly_classes','number')],
        'batch': [('program','text'), ('semester','number'), ('students','number')]
    }.get(entity, [])
    rows = ''
    for label, typ in fields:
        rows += f'<label>{label.replace("_"," ").title()}</label><input name="{label}" type="{typ}" required />'
    content = f'''
    <h2>Add {entity.capitalize()}</h2>
    <form method="post">{rows}<button type="submit">Add {entity.capitalize()}</button></form>
    <p><a href="/dashboard">Back to Dashboard</a></p>
    '''
    return render_template_string(BASE_TEMPLATE, title=f'Add {entity.capitalize()}', content=content)

@app.route('/view_data')
@login_required
def view_data():
    dfs = load_excel_sheets()
    content = '<h2>All Data</h2>'
    for sheet, df in dfs.items():
        content += f'<h3>{sheet}</h3>'
        if not df.empty:
            content += '<table><thead><tr>'
            for col in df.columns: content += f'<th>{col}</th>'
            content += '</tr></thead><tbody>'
            for row in df.itertuples(index=False): 
                content += '<tr>' + ''.join(f'<td>{cell}</td>' for cell in row) + '</tr>'
            content += '</tbody></table>'
        else:
            content += f'<p>No data in {sheet}</p>'
    content += '<p><a href="/dashboard">Back to Dashboard</a></p>'
    return render_template_string(BASE_TEMPLATE, title="View Data", content=content)

@app.route('/generate_timetable')
@login_required
def generate_timetable():
    if current_user.role != 'admin':
        flash('Access denied')
        return redirect(url_for('dashboard'))
    dfs = load_excel_sheets()
    faculty = dfs['Faculty']
    classrooms = dfs['Classroom']
    subjects = dfs['Subject']
    batches = dfs['Batch']
    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
    hours = ['9-10am', '10-11am', '11-12am', '1-2pm', '2-3pm']
    slots = [f"{d} {h}" for d in days for h in hours]
    model = cp_model.CpModel()
    timetable_vars = {}
    for _, batch in batches.iterrows():
        for _, subject in subjects.iterrows():
            for slot in slots:
                varname = f"b{batch['ID']}s{subject['ID']}t{slot.replace(' ', '')}"
                timetable_vars[(batch['ID'], subject['ID'], slot)] = model.NewBoolVar(varname)
    for _, batch in batches.iterrows():
        for _, subject in subjects.iterrows():
            vars = [timetable_vars[(batch['ID'], subject['ID'], slot)] for slot in slots]
            model.Add(sum(vars) == subject['Weekly_Classes'])
    solver = cp_model.CpSolver()
    status = solver.Solve(model)
    timetable_rows = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for _, batch in batches.iterrows():
            for _, subject in subjects.iterrows():
                for slot in slots:
                    if solver.Value(timetable_vars[(batch['ID'], subject['ID'], slot)]) == 1:
                        timetable_rows.append({
                            'Batch_ID': batch['ID'],
                            'Subject_ID': subject['ID'],
                            'Slot_Time': slot,
                            'Faculty_ID': faculty['ID'].iloc[0] if not faculty.empty else 1,
                            'Classroom_ID': classrooms['ID'].iloc[0] if not classrooms.empty else 1
                        })
        timetable_df = pd.DataFrame(timetable_rows)
        timetable_df.to_excel(EXCEL_TIMETABLE_FILE, index=False)
        flash('Timetable generated and saved to Excel')
    else:
        flash('No feasible timetable found')
    return redirect(url_for('view_timetable'))

@app.route('/view_timetable')
@login_required
def view_timetable():
    if os.path.exists(EXCEL_TIMETABLE_FILE):
        timetable_df = pd.read_excel(EXCEL_TIMETABLE_FILE)
        dfs = load_excel_sheets()
        faculty = dfs['Faculty']
        classrooms = dfs['Classroom']
        subjects = dfs['Subject']
        batches = dfs['Batch']
        def get_name(df, id, field='Name', id_field=None):
            if id_field is None: id_field = df.columns[0]
            rec = df[df[id_field] == id]
            if not rec.empty: return rec.iloc[0][field]
            return "Unknown"
        timetable_df['Faculty'] = timetable_df['Faculty_ID'].apply(lambda x: get_name(faculty, x))
        timetable_df['Classroom'] = timetable_df['Classroom_ID'].apply(lambda x: get_name(classrooms, x))
        timetable_df['Subject'] = timetable_df['Subject_ID'].apply(lambda x: get_name(subjects, x))
        timetable_df['Batch'] = timetable_df['Batch_ID'].apply(lambda x: get_name(batches, x, 'Program'))
        timetable_records = timetable_df.to_dict(orient='records')
    else:
        timetable_records = []
    content = '<h2>Generated Timetable</h2>'
    if timetable_records:
        content += '''<table><thead><tr>
        <th>Batch</th><th>Subject</th><th>Slot</th><th>Faculty</th><th>Classroom</th>
        </tr></thead><tbody>'''
        for row in timetable_records:
            content += f"<tr><td>{row['Batch']}</td><td>{row['Subject']}</td><td>{row['Slot_Time']}</td><td>{row['Faculty']}</td><td>{row['Classroom']}</td></tr>"
        content += "</tbody></table>"
        content += '<p><a href="/download_timetable">Download Timetable as Excel</a></p>'
    else:
        content += '<p>No timetable generated yet</p>'
    content += '<p><a href="/dashboard">Back to Dashboard</a></p>'
    return render_template_string(BASE_TEMPLATE, title="Timetable", content=content)

@app.route('/download_timetable')
@login_required
def download_timetable():
    if os.path.exists(EXCEL_TIMETABLE_FILE):
        return send_file(EXCEL_TIMETABLE_FILE, as_attachment=True)
    flash('No timetable file found to download')
    return redirect(url_for('view_timetable'))

if __name__ == '__main__':
    app.run(debug=True)
