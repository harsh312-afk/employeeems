import json
import sqlite3
import os
import sys
import uuid
import csv
import io
import urllib.parse
from datetime import datetime, timedelta, date
from wsgiref.simple_server import make_server

# Ensure backend directory is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from database import get_db_connection, verify_password, hash_password, init_db, seed_data

PORT = int(os.environ.get("PORT", 8000))

# Support both public and frontend static directories
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'public'))
if not os.path.exists(STATIC_DIR):
    STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))

# Ensure database is initialized
init_db()

def get_auth_token(environ):
    auth_header = environ.get('HTTP_AUTHORIZATION', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1].strip()
    return None

def get_current_user(token):
    if not token:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.email, u.role, e.id as employee_id, e.emp_code, e.first_name, e.last_name,
               e.department, e.designation, e.phone, e.address, e.status as employee_status
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN employees e ON e.user_id = u.id
        WHERE s.token = ? AND s.expires_at > CURRENT_TIMESTAMP
    ''', (token,))
    user = cursor.fetchone()
    conn.close()
    if user:
        user_dict = dict(user)
        # Inactive employees lose session access
        if user_dict.get('employee_status') == 'INACTIVE':
            return None
        return user_dict
    return None

def calculate_hours_worked(clock_in_str, clock_out_str):
    """Calculates hours between two HH:MM:SS or HH:MM strings."""
    try:
        t1 = datetime.strptime(clock_in_str, '%H:%M:%S' if len(clock_in_str.split(':')) == 3 else '%H:%M')
        t2 = datetime.strptime(clock_out_str, '%H:%M:%S' if len(clock_out_str.split(':')) == 3 else '%H:%M')
        diff_sec = (t2 - t1).total_seconds()
        if diff_sec > 0:
            return round(diff_sec / 3600.0, 2)
    except Exception:
        pass
    return 0.0

def send_wsgi_response(start_response, status_code, content_type, body_bytes, extra_headers=None):
    status_text = {
        200: "200 OK",
        201: "201 Created",
        400: "400 Bad Request",
        401: "401 Unauthorized",
        403: "403 Forbidden",
        404: "404 Not Found",
        500: "500 Internal Server Error"
    }.get(status_code, f"{status_code} Unknown")

    headers = [
        ('Content-Type', content_type),
        ('Content-Length', str(len(body_bytes))),
        ('Access-Control-Allow-Origin', '*'),
        ('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS'),
        ('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    ]
    if extra_headers:
        headers.extend(extra_headers)

    start_response(status_text, headers)
    return [body_bytes]

def send_json(start_response, data, status=200):
    body = json.dumps(data).encode('utf-8')
    return send_wsgi_response(start_response, status, 'application/json; charset=utf-8', body)

def send_error_json(start_response, message, status=400):
    return send_json(start_response, {'error': message, 'success': False}, status=status)

def send_csv(start_response, filename, csv_data):
    body = csv_data.encode('utf-8')
    return send_wsgi_response(start_response, 200, 'text/csv; charset=utf-8', body, [
        ('Content-Disposition', f'attachment; filename="{filename}"')
    ])

def parse_json_body(environ):
    try:
        content_length = int(environ.get('CONTENT_LENGTH', 0))
    except (ValueError, TypeError):
        content_length = 0
    if content_length > 0:
        raw = environ['wsgi.input'].read(content_length).decode('utf-8')
        try:
            return json.loads(raw)
        except Exception:
            return {}
    return {}

def serve_static_file(path, start_response):
    if path in ('/', '', '/index.html'):
        filepath = os.path.join(STATIC_DIR, 'index.html')
    else:
        filepath = os.path.join(STATIC_DIR, path.lstrip('/'))

    if path == '/favicon.ico' and not os.path.exists(filepath):
        svg_path = os.path.join(STATIC_DIR, 'favicon.svg')
        if os.path.exists(svg_path):
            with open(svg_path, 'rb') as f:
                content = f.read()
            return send_wsgi_response(start_response, 200, 'image/svg+xml', content, [
                ('Cache-Control', 'public, max-age=3600')
            ])

    if os.path.exists(filepath) and os.path.isfile(filepath):
        content_type = 'text/html; charset=utf-8'
        if filepath.endswith('.css'):
            content_type = 'text/css; charset=utf-8'
        elif filepath.endswith('.js'):
            content_type = 'application/javascript; charset=utf-8'
        elif filepath.endswith('.json'):
            content_type = 'application/json; charset=utf-8'
        elif filepath.endswith('.svg'):
            content_type = 'image/svg+xml'
        elif filepath.endswith('.png'):
            content_type = 'image/png'
        elif filepath.endswith('.ico'):
            content_type = 'image/x-icon'

        with open(filepath, 'rb') as f:
            content = f.read()

        return send_wsgi_response(start_response, 200, content_type, content, [
            ('Cache-Control', 'public, max-age=3600')
        ])
    else:
        index_path = os.path.join(STATIC_DIR, 'index.html')
        if os.path.exists(index_path):
            with open(index_path, 'rb') as f:
                content = f.read()
            return send_wsgi_response(start_response, 200, 'text/html; charset=utf-8', content)
        return send_wsgi_response(start_response, 404, 'text/plain; charset=utf-8', b'File Not Found')

# ==========================================
# WSGI APPLICATION CONTROLLER
# ==========================================
def app(environ, start_response):
    path = environ.get('PATH_INFO', '/')
    method = environ.get('REQUEST_METHOD', 'GET').upper()
    query_str = environ.get('QUERY_STRING', '')

    # Normalize rewrites if query parameter __route__ was injected
    qparams = urllib.parse.parse_qs(query_str) if query_str else {}
    if '__route__' in qparams:
        route = qparams['__route__'][0].lstrip('/')
        path = f"/api/{route}"

    # Handle CORS Preflight
    if method == 'OPTIONS':
        return send_wsgi_response(start_response, 200, 'text/plain', b'')

    # Static assets or SPA routing
    if not path.startswith('/api/'):
        return serve_static_file(path, start_response)

    # ----------------------------------------------------
    # GET Endpoints
    # ----------------------------------------------------
    if method == 'GET':
        token = get_auth_token(environ)
        user = get_current_user(token)

        if path == '/api/auth/me':
            if not user:
                return send_error_json(start_response, 'Unauthorized or session expired', 401)
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('SELECT * FROM employees WHERE user_id = ?', (user['id'],))
            emp = c.fetchone()
            emp_dict = dict(emp) if emp else {}

            c.execute('SELECT casual_leave, sick_leave, paid_leave FROM leave_balances WHERE employee_id = ?', (user['employee_id'],))
            leaves = c.fetchone()
            leaves_dict = dict(leaves) if leaves else {'casual_leave': 12, 'sick_leave': 10, 'paid_leave': 15}
            conn.close()

            return send_json(start_response, {
                'user': user,
                'employee': emp_dict,
                'leave_balances': leaves_dict
            })

        if not user:
            return send_error_json(start_response, 'Unauthorized', 401)

        conn = get_db_connection()
        c = conn.cursor()

        # Employees Directory
        if path == '/api/employees':
            dept_filter = qparams.get('department', [None])[0]
            status_filter = qparams.get('status', [None])[0]
            search_filter = qparams.get('search', [None])[0]

            query = '''
                SELECT e.*, u.email, u.role,
                       m.first_name || ' ' || m.last_name as manager_name
                FROM employees e
                JOIN users u ON e.user_id = u.id
                LEFT JOIN employees m ON e.manager_id = m.id
                WHERE 1=1
            '''
            params = []

            if user['role'] == 'MANAGER':
                query += " AND (e.manager_id = ? OR e.id = ?)"
                params.extend([user['employee_id'], user['employee_id']])
            elif user['role'] == 'EMPLOYEE':
                query += " AND e.status = 'ACTIVE'"

            if dept_filter:
                query += " AND e.department = ?"
                params.append(dept_filter)
            if status_filter:
                query += " AND e.status = ?"
                params.append(status_filter)
            if search_filter:
                search_term = f"%{search_filter}%"
                query += " AND (e.first_name LIKE ? OR e.last_name LIKE ? OR e.emp_code LIKE ? OR e.designation LIKE ?)"
                params.extend([search_term, search_term, search_term, search_term])

            query += " ORDER BY e.id DESC"
            c.execute(query, tuple(params))
            rows = [dict(r) for r in c.fetchall()]

            c.execute('''
                SELECT e.id, e.first_name || ' ' || e.last_name as name, e.designation, e.department
                FROM employees e
                JOIN users u ON e.user_id = u.id
                WHERE u.role IN ('HR_ADMIN', 'MANAGER') AND e.status = 'ACTIVE'
                ORDER BY e.first_name ASC
            ''')
            managers = [dict(r) for r in c.fetchall()]

            c.execute("SELECT DISTINCT department FROM employees ORDER BY department ASC")
            departments = [r[0] for r in c.fetchall()]

            conn.close()
            return send_json(start_response, {
                'employees': rows,
                'managers': managers,
                'departments': departments
            })

        # Attendance Tracker
        if path == '/api/attendance':
            today = date.today().strftime('%Y-%m-%d')
            status_filter = qparams.get('status', [None])[0]
            date_filter = qparams.get('date', [None])[0]

            query = '''
                SELECT a.*, e.emp_code, e.first_name, e.last_name, e.department
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                WHERE 1=1
            '''
            params = []

            if user['role'] == 'HR_ADMIN':
                pass
            elif user['role'] == 'MANAGER':
                query += " AND (e.manager_id = ? OR e.id = ?)"
                params.extend([user['employee_id'], user['employee_id']])
            else:
                query += " AND a.employee_id = ?"
                params.append(user['employee_id'])

            if status_filter:
                query += " AND a.status = ?"
                params.append(status_filter)
            if date_filter:
                query += " AND a.date = ?"
                params.append(date_filter)

            query += " ORDER BY a.date DESC, a.id DESC LIMIT 100"
            c.execute(query, tuple(params))
            rows = [dict(r) for r in c.fetchall()]

            c.execute('SELECT * FROM attendance WHERE employee_id = ? AND date = ?', (user['employee_id'], today))
            today_att = c.fetchone()
            today_att_dict = dict(today_att) if today_att else None

            current_month_prefix = today[:7]
            c.execute('''
                SELECT 
                    COUNT(*) as total_days,
                    SUM(CASE WHEN status = 'PRESENT' THEN 1 ELSE 0 END) as present_days,
                    SUM(CASE WHEN status = 'LATE' THEN 1 ELSE 0 END) as late_days,
                    SUM(COALESCE(hours_worked, 0)) as total_hours
                FROM attendance
                WHERE employee_id = ? AND date LIKE ?
            ''', (user['employee_id'], f"{current_month_prefix}%"))
            month_stats = c.fetchone()
            month_stats_dict = {
                'total_days': month_stats['total_days'] if month_stats else 0,
                'present_days': month_stats['present_days'] if month_stats else 0,
                'late_days': month_stats['late_days'] if month_stats else 0,
                'total_hours': round(month_stats['total_hours'], 1) if month_stats and month_stats['total_hours'] else 0.0
            }

            conn.close()
            return send_json(start_response, {
                'attendance': rows,
                'today_attendance': today_att_dict,
                'month_stats': month_stats_dict
            })

        # Leave Requests
        if path == '/api/leave-requests':
            status_filter = qparams.get('status', [None])[0]
            type_filter = qparams.get('leave_type', [None])[0]

            query = '''
                SELECT l.*, e.emp_code, e.first_name, e.last_name, e.department,
                       r.first_name || ' ' || r.last_name as reviewer_name
                FROM leave_requests l
                JOIN employees e ON l.employee_id = e.id
                LEFT JOIN employees r ON l.reviewed_by = r.id
                WHERE 1=1
            '''
            params = []

            if user['role'] == 'HR_ADMIN':
                pass
            elif user['role'] == 'MANAGER':
                query += " AND (e.manager_id = ? OR e.id = ?)"
                params.extend([user['employee_id'], user['employee_id']])
            else:
                query += " AND l.employee_id = ?"
                params.append(user['employee_id'])

            if status_filter:
                query += " AND l.status = ?"
                params.append(status_filter)
            if type_filter:
                query += " AND l.leave_type = ?"
                params.append(type_filter)

            query += " ORDER BY l.created_at DESC"
            c.execute(query, tuple(params))
            rows = [dict(r) for r in c.fetchall()]

            c.execute('SELECT casual_leave, sick_leave, paid_leave FROM leave_balances WHERE employee_id = ?', (user['employee_id'],))
            lb = c.fetchone()
            lb_dict = dict(lb) if lb else {'casual_leave': 12, 'sick_leave': 10, 'paid_leave': 15}

            conn.close()
            return send_json(start_response, {
                'leave_requests': rows,
                'leave_balances': lb_dict
            })

        # Dashboard Stats
        if path == '/api/dashboard/stats':
            today = date.today().strftime('%Y-%m-%d')
            c.execute("SELECT COUNT(*) FROM employees WHERE status = 'ACTIVE'")
            total_employees = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM attendance WHERE date = ? AND status IN ('PRESENT', 'LATE')", (today,))
            present_today = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM leave_requests WHERE status = 'PENDING'")
            pending_leaves = c.fetchone()[0]

            c.execute("SELECT department, COUNT(*) as count FROM employees WHERE status = 'ACTIVE' GROUP BY department ORDER BY count DESC")
            dept_counts = [dict(r) for r in c.fetchall()]

            c.execute('''
                SELECT l.id, l.leave_type, l.start_date, l.end_date, l.days_count, l.reason, l.status,
                       e.first_name, e.last_name, e.department
                FROM leave_requests l
                JOIN employees e ON l.employee_id = e.id
                ORDER BY l.created_at DESC LIMIT 5
            ''')
            recent_leaves = [dict(r) for r in c.fetchall()]

            conn.close()
            return send_json(start_response, {
                'stats': {
                    'total_employees': total_employees,
                    'present_today': present_today,
                    'pending_leaves': pending_leaves,
                    'attendance_rate': round((present_today / total_employees * 100), 1) if total_employees > 0 else 0
                },
                'dept_distribution': dept_counts,
                'recent_leaves': recent_leaves
            })

        # Export Employees CSV
        if path == '/api/export/employees':
            if user['role'] != 'HR_ADMIN':
                conn.close()
                return send_error_json(start_response, 'Forbidden: HR Admin access required', 403)

            c.execute('''
                SELECT e.emp_code, e.first_name, e.last_name, u.email, u.role,
                       e.department, e.designation, e.salary, e.joining_date,
                       e.phone, e.address, e.status,
                       m.first_name || ' ' || m.last_name as manager_name
                FROM employees e
                JOIN users u ON e.user_id = u.id
                LEFT JOIN employees m ON e.manager_id = m.id
                ORDER BY e.id ASC
            ''')
            rows = c.fetchall()
            conn.close()

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Employee Code', 'First Name', 'Last Name', 'Email', 'Role',
                             'Department', 'Designation', 'Annual Salary ($)', 'Joining Date',
                             'Phone', 'Address', 'Status', 'Reporting Manager'])
            for r in rows:
                writer.writerow([r['emp_code'], r['first_name'], r['last_name'], r['email'], r['role'],
                                 r['department'], r['designation'], r['salary'], r['joining_date'],
                                 r['phone'] or '', r['address'] or '', r['status'], r['manager_name'] or 'N/A'])

            return send_csv(start_response, f"employees_export_{date.today()}.csv", output.getvalue())

        # Export Attendance CSV
        if path == '/api/export/attendance':
            if user['role'] not in ('HR_ADMIN', 'MANAGER'):
                conn.close()
                return send_error_json(start_response, 'Forbidden: Access denied', 403)

            c.execute('''
                SELECT a.date, e.emp_code, e.first_name || ' ' || e.last_name as employee_name,
                       e.department, a.clock_in, a.clock_out, a.hours_worked, a.status, a.notes
                FROM attendance a
                JOIN employees e ON a.employee_id = e.id
                ORDER BY a.date DESC, a.id DESC
            ''')
            rows = c.fetchall()
            conn.close()

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow(['Date', 'Employee Code', 'Employee Name', 'Department',
                             'Clock In', 'Clock Out', 'Hours Worked', 'Status', 'Notes'])
            for r in rows:
                writer.writerow([r['date'], r['emp_code'], r['employee_name'], r['department'],
                                 r['clock_in'] or '', r['clock_out'] or '', r['hours_worked'] or 0,
                                 r['status'], r['notes'] or ''])

            return send_csv(start_response, f"attendance_export_{date.today()}.csv", output.getvalue())

        conn.close()
        return send_error_json(start_response, 'Endpoint not found', 404)

    # ----------------------------------------------------
    # POST Endpoints
    # ----------------------------------------------------
    if method == 'POST':
        data = parse_json_body(environ)

        # Login
        if path == '/api/auth/login':
            email = data.get('email', '').strip().lower()
            password = data.get('password', '').strip()

            if not email or not password:
                return send_error_json(start_response, 'Email and password required', 400)

            conn = get_db_connection()
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE LOWER(email) = ?', (email,))
            user_row = c.fetchone()

            if not user_row or not verify_password(user_row['password_hash'], user_row['salt'], password):
                conn.close()
                return send_error_json(start_response, 'Invalid email or password', 401)

            c.execute('SELECT * FROM employees WHERE user_id = ?', (user_row['id'],))
            emp = c.fetchone()
            emp_dict = dict(emp) if emp else {}

            if emp_dict.get('status') == 'INACTIVE':
                conn.close()
                return send_error_json(start_response, 'Account is deactivated. Please contact HR.', 403)

            token = str(uuid.uuid4())
            expires_at = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

            c.execute('INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)',
                      (token, user_row['id'], expires_at))
            conn.commit()
            conn.close()

            return send_json(start_response, {
                'message': 'Login successful',
                'token': token,
                'user': {
                    'id': user_row['id'],
                    'email': user_row['email'],
                    'role': user_row['role']
                },
                'employee': emp_dict
            })

        token = get_auth_token(environ)
        user = get_current_user(token)
        if not user:
            return send_error_json(start_response, 'Unauthorized or session expired', 401)

        conn = get_db_connection()
        c = conn.cursor()

        # Logout
        if path == '/api/auth/logout':
            c.execute('DELETE FROM sessions WHERE token = ?', (token,))
            conn.commit()
            conn.close()
            return send_json(start_response, {'message': 'Logged out successfully'})

        # Change Password
        if path == '/api/auth/change-password':
            current_pwd = data.get('current_password', '').strip()
            new_pwd = data.get('new_password', '').strip()

            if not current_pwd or not new_pwd:
                conn.close()
                return send_error_json(start_response, 'Current and new password are required', 400)

            if len(new_pwd) < 6:
                conn.close()
                return send_error_json(start_response, 'New password must be at least 6 characters long', 400)

            c.execute('SELECT password_hash, salt FROM users WHERE id = ?', (user['id'],))
            u_row = c.fetchone()
            if not u_row or not verify_password(u_row['password_hash'], u_row['salt'], current_pwd):
                conn.close()
                return send_error_json(start_response, 'Current password is incorrect', 400)

            new_hash, new_salt = hash_password(new_pwd)
            c.execute('UPDATE users SET password_hash = ?, salt = ? WHERE id = ?', (new_hash, new_salt, user['id']))
            conn.commit()
            conn.close()
            return send_json(start_response, {'message': 'Password changed successfully'})

        # Clock In
        if path == '/api/attendance/clock-in':
            today = date.today().strftime('%Y-%m-%d')
            client_time = data.get('client_time')
            now_time = client_time if client_time and len(client_time) == 8 else datetime.now().strftime('%H:%M:%S')

            c.execute('SELECT * FROM attendance WHERE employee_id = ? AND date = ?', (user['employee_id'], today))
            existing = c.fetchone()

            if existing:
                conn.close()
                return send_error_json(start_response, 'Already clocked in today', 400)

            status = 'LATE' if now_time > '09:15:00' else 'PRESENT'
            notes = data.get('notes', 'Clocked in via portal')

            c.execute('''INSERT INTO attendance (employee_id, date, clock_in, status, notes)
                         VALUES (?, ?, ?, ?, ?)''', (user['employee_id'], today, now_time, status, notes))
            conn.commit()
            conn.close()
            return send_json(start_response, {'message': 'Clocked in successfully', 'time': now_time, 'status': status})

        # Clock Out
        if path == '/api/attendance/clock-out':
            today = date.today().strftime('%Y-%m-%d')
            client_time = data.get('client_time')
            now_time = client_time if client_time and len(client_time) == 8 else datetime.now().strftime('%H:%M:%S')

            c.execute('SELECT * FROM attendance WHERE employee_id = ? AND date = ?', (user['employee_id'], today))
            existing = c.fetchone()

            if not existing:
                conn.close()
                return send_error_json(start_response, 'Must clock in before clocking out', 400)

            if existing['clock_out']:
                conn.close()
                return send_error_json(start_response, 'Already clocked out today', 400)

            hours = calculate_hours_worked(existing['clock_in'], now_time)

            c.execute('UPDATE attendance SET clock_out = ?, hours_worked = ? WHERE id = ?', (now_time, hours, existing['id']))
            conn.commit()
            conn.close()
            return send_json(start_response, {
                'message': 'Clocked out successfully',
                'time': now_time,
                'hours_worked': hours
            })

        # Add Employee (HR_ADMIN)
        if path == '/api/employees':
            if user['role'] != 'HR_ADMIN':
                conn.close()
                return send_error_json(start_response, 'Forbidden: Only HR Admin can add employees', 403)

            email = data.get('email', '').strip().lower()
            password = data.get('password', 'Password123!')
            role = data.get('role', 'EMPLOYEE')
            emp_code = data.get('emp_code', '').strip().upper()
            first_name = data.get('first_name', '').strip()
            last_name = data.get('last_name', '').strip()
            designation = data.get('designation', '').strip()
            department = data.get('department', '').strip()
            joining_date = data.get('joining_date', date.today().strftime('%Y-%m-%d'))
            phone = data.get('phone', '').strip()
            address = data.get('address', '').strip()

            try:
                salary = float(data.get('salary', 0))
            except (ValueError, TypeError):
                salary = 0.0

            mgr_raw = data.get('manager_id')
            manager_id = None
            if mgr_raw not in (None, '', 'null', 'None'):
                try:
                    manager_id = int(mgr_raw)
                except (ValueError, TypeError):
                    manager_id = None

            if not email or not emp_code or not first_name or not last_name:
                conn.close()
                return send_error_json(start_response, 'First name, last name, email, and employee code are required', 400)

            if role not in ('HR_ADMIN', 'MANAGER', 'EMPLOYEE'):
                conn.close()
                return send_error_json(start_response, 'Invalid role specified', 400)

            p_hash, salt = hash_password(password)
            try:
                c.execute('INSERT INTO users (email, password_hash, salt, role) VALUES (?, ?, ?, ?)',
                          (email, p_hash, salt, role))
                new_user_id = c.lastrowid

                c.execute('''INSERT INTO employees
                    (user_id, emp_code, first_name, last_name, designation, department, joining_date, salary, phone, address, manager_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
                        (new_user_id, emp_code, first_name, last_name, designation, department, joining_date, salary, phone, address, manager_id))
                new_emp_id = c.lastrowid

                c.execute('INSERT INTO leave_balances (employee_id, casual_leave, sick_leave, paid_leave) VALUES (?, 12, 10, 15)', (new_emp_id,))
                conn.commit()
                conn.close()
                return send_json(start_response, {'message': 'Employee registered successfully', 'employee_id': new_emp_id}, 201)
            except sqlite3.IntegrityError:
                conn.close()
                return send_error_json(start_response, 'Email or Employee Code already exists in the system', 400)

        # Submit Leave Request
        if path == '/api/leave-requests':
            leave_type = data.get('leave_type', 'CASUAL').upper()
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            reason = data.get('reason', '').strip()

            if leave_type not in ('CASUAL', 'SICK', 'PAID', 'UNPAID'):
                conn.close()
                return send_error_json(start_response, 'Invalid leave type', 400)

            if not start_date or not end_date or not reason:
                conn.close()
                return send_error_json(start_response, 'Start date, end date, and reason are required', 400)

            try:
                d1 = datetime.strptime(start_date, '%Y-%m-%d')
                d2 = datetime.strptime(end_date, '%Y-%m-%d')
                days_count = (d2 - d1).days + 1
            except ValueError:
                conn.close()
                return send_error_json(start_response, 'Dates must be in YYYY-MM-DD format', 400)

            if days_count <= 0:
                conn.close()
                return send_error_json(start_response, 'End date must be on or after start date', 400)

            if leave_type in ('CASUAL', 'SICK', 'PAID'):
                balance_col = leave_type.lower() + '_leave'
                c.execute(f'SELECT {balance_col} FROM leave_balances WHERE employee_id = ?', (user['employee_id'],))
                lb_row = c.fetchone()
                if lb_row and lb_row[0] < days_count:
                    conn.close()
                    return send_error_json(start_response, f'Insufficient {leave_type.capitalize()} leave balance ({lb_row[0]} days remaining)', 400)

            c.execute('''INSERT INTO leave_requests
                (employee_id, leave_type, start_date, end_date, days_count, reason, status)
                VALUES (?, ?, ?, ?, ?, ?, 'PENDING')''',
                (user['employee_id'], leave_type, start_date, end_date, days_count, reason))
            conn.commit()
            conn.close()
            return send_json(start_response, {'message': 'Leave application submitted successfully'}, 201)

        # Review Leave Request
        if path.startswith('/api/leave-requests/') and path.endswith('/review'):
            if user['role'] not in ('HR_ADMIN', 'MANAGER'):
                conn.close()
                return send_error_json(start_response, 'Forbidden: Only Manager or HR Admin can review leave requests', 403)

            parts = path.split('/')
            leave_id = parts[3]
            status = data.get('status')
            review_comment = data.get('review_comment', '').strip()

            if status not in ('APPROVED', 'REJECTED'):
                conn.close()
                return send_error_json(start_response, 'Status must be APPROVED or REJECTED', 400)

            c.execute('SELECT * FROM leave_requests WHERE id = ?', (leave_id,))
            req = c.fetchone()

            if not req:
                conn.close()
                return send_error_json(start_response, 'Leave request not found', 404)

            if req['status'] != 'PENDING':
                conn.close()
                return send_error_json(start_response, f'Leave request has already been reviewed ({req["status"]})', 400)

            if user['role'] == 'MANAGER':
                c.execute('SELECT manager_id FROM employees WHERE id = ?', (req['employee_id'],))
                emp_row = c.fetchone()
                if not emp_row or (emp_row['manager_id'] != user['employee_id'] and req['employee_id'] != user['employee_id']):
                    conn.close()
                    return send_error_json(start_response, 'Forbidden: You can only review leave requests for your team', 403)

            c.execute('''UPDATE leave_requests
                         SET status = ?, reviewed_by = ?, review_comment = ?
                         WHERE id = ?''', (status, user['employee_id'], review_comment, leave_id))

            LEAVE_BALANCE_COLS = {
                'CASUAL': 'casual_leave',
                'SICK': 'sick_leave',
                'PAID': 'paid_leave'
            }
            if status == 'APPROVED' and req['leave_type'] in LEAVE_BALANCE_COLS:
                col_name = LEAVE_BALANCE_COLS[req['leave_type']]
                c.execute(f'''UPDATE leave_balances
                             SET {col_name} = MAX(0, {col_name} - ?)
                             WHERE employee_id = ?''', (req['days_count'], req['employee_id']))

            conn.commit()
            conn.close()
            return send_json(start_response, {'message': f'Leave request {status.lower()} successfully'})

        # Cancel Leave Request
        if path.startswith('/api/leave-requests/') and path.endswith('/cancel'):
            parts = path.split('/')
            leave_id = parts[3]

            c.execute('SELECT * FROM leave_requests WHERE id = ?', (leave_id,))
            req = c.fetchone()

            if not req:
                conn.close()
                return send_error_json(start_response, 'Leave request not found', 404)

            if req['employee_id'] != user['employee_id'] and user['role'] != 'HR_ADMIN':
                conn.close()
                return send_error_json(start_response, 'Forbidden: You cannot cancel this leave request', 403)

            if req['status'] != 'PENDING':
                conn.close()
                return send_error_json(start_response, 'Only pending leave requests can be cancelled', 400)

            c.execute("UPDATE leave_requests SET status = 'CANCELLED' WHERE id = ?", (leave_id,))
            conn.commit()
            conn.close()
            return send_json(start_response, {'message': 'Leave request cancelled successfully'})

        # Reset Demo Data
        if path == '/api/admin/reset-demo':
            if user['role'] != 'HR_ADMIN':
                conn.close()
                return send_error_json(start_response, 'Forbidden: HR Admin access required', 403)

            c.execute('DELETE FROM sessions')
            c.execute('DELETE FROM attendance')
            c.execute('DELETE FROM leave_requests')
            c.execute('DELETE FROM leave_balances')
            c.execute('DELETE FROM employees')
            c.execute('DELETE FROM users')
            seed_data(c)
            conn.commit()
            conn.close()
            return send_json(start_response, {'message': 'Database reset to demo state successfully'})

        conn.close()
        return send_error_json(start_response, 'Endpoint not found', 404)

    # ----------------------------------------------------
    # PUT Endpoints
    # ----------------------------------------------------
    if method == 'PUT':
        token = get_auth_token(environ)
        user = get_current_user(token)
        if not user:
            return send_error_json(start_response, 'Unauthorized or session expired', 401)

        data = parse_json_body(environ)
        conn = get_db_connection()
        c = conn.cursor()

        # Update Personal Profile
        if path == '/api/auth/profile':
            phone = data.get('phone', '').strip()
            address = data.get('address', '').strip()
            c.execute('UPDATE employees SET phone = ?, address = ? WHERE id = ?', (phone, address, user['employee_id']))
            conn.commit()
            conn.close()
            return send_json(start_response, {'message': 'Profile updated successfully'})

        # Update Employee (HR_ADMIN)
        if path.startswith('/api/employees/'):
            if user['role'] != 'HR_ADMIN':
                conn.close()
                return send_error_json(start_response, 'Forbidden: HR Admin access required', 403)

            parts = path.split('/')
            emp_id = parts[3]

            c.execute('SELECT * FROM employees WHERE id = ?', (emp_id,))
            emp = c.fetchone()

            if not emp:
                conn.close()
                return send_error_json(start_response, 'Employee not found', 404)

            mgr_raw = data.get('manager_id', emp['manager_id'])
            manager_id = None
            if mgr_raw not in (None, '', 'null', 'None'):
                try:
                    manager_id = int(mgr_raw)
                except (ValueError, TypeError):
                    manager_id = None

            try:
                salary = float(data.get('salary', emp['salary']))
            except (ValueError, TypeError):
                salary = emp['salary']

            status = data.get('status', emp['status'])
            if status not in ('ACTIVE', 'INACTIVE'):
                status = emp['status']

            c.execute('''UPDATE employees SET
                first_name = ?, last_name = ?, designation = ?, department = ?,
                salary = ?, phone = ?, address = ?, manager_id = ?, status = ?
                WHERE id = ?''', (
                data.get('first_name', emp['first_name']).strip(),
                data.get('last_name', emp['last_name']).strip(),
                data.get('designation', emp['designation']).strip(),
                data.get('department', emp['department']).strip(),
                salary,
                data.get('phone', emp['phone']).strip(),
                data.get('address', emp['address']).strip(),
                manager_id,
                status,
                emp_id
            ))

            if 'role' in data and data['role'] in ('HR_ADMIN', 'MANAGER', 'EMPLOYEE'):
                c.execute('UPDATE users SET role = ? WHERE id = ?', (data['role'], emp['user_id']))

            conn.commit()
            conn.close()
            return send_json(start_response, {'message': 'Employee record updated successfully'})

        conn.close()
        return send_error_json(start_response, 'Endpoint not found', 404)

    return send_error_json(start_response, 'Method not allowed', 405)

# Entrypoint aliases for WSGI servers (Vercel, Gunicorn, uWSGI)
application = app

def run_server():
    os.chdir(STATIC_DIR)
    print(f"Employee Management System running on http://0.0.0.0:{PORT} (Serving {STATIC_DIR})", flush=True)
    with make_server("0.0.0.0", PORT, app) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.server_close()

if __name__ == '__main__':
    run_server()
