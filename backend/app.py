print("DEBUG: Starting app.py", flush=True)

import http.server
import socketserver
import json
import sqlite3
import os
import uuid
import urllib.parse
from datetime import datetime, timedelta, date
from database import get_db_connection, verify_password, hash_password, init_db

PORT = 8000
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))

# Ensure database initialized
init_db()

def parse_json_body(handler):
    content_length = int(handler.headers.get('Content-Length', 0))
    if content_length > 0:
        body = handler.rfile.read(content_length).decode('utf-8')
        try:
            return json.loads(body)
        except Exception:
            return {}
    return {}

def get_auth_token(handler):
    auth_header = handler.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header.split(' ', 1)[1].strip()
    return None

def get_current_user(token):
    if not token:
        return None
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT u.id, u.email, u.role, e.id as employee_id, e.emp_code, e.first_name, e.last_name, e.department, e.designation
        FROM sessions s
        JOIN users u ON s.user_id = u.id
        LEFT JOIN employees e ON e.user_id = u.id
        WHERE s.token = ? AND s.expires_at > CURRENT_TIMESTAMP
    ''', (token,))
    user = cursor.fetchone()
    conn.close()
    if user:
        return dict(user)
    return None

class EMSRequestHandler(http.server.SimpleHTTPRequestHandler):
    def send_json(self, data, status=200):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def send_error_json(self, message, status=400):
        self.send_json({'error': message}, status=status)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path

        if path.startswith('/api/'):
            self.handle_api_get(path, parsed_url.query)
        else:
            self.serve_static_file(path)

    def serve_static_file(self, path):
        if path == '/' or path == '':
            filepath = os.path.join(STATIC_DIR, 'index.html')
        else:
            filepath = os.path.join(STATIC_DIR, path.lstrip('/'))

        if os.path.exists(filepath) and os.path.isfile(filepath):
            content_type = 'text/html'
            if filepath.endswith('.css'):
                content_type = 'text/css'
            elif filepath.endswith('.js'):
                content_type = 'application/javascript'
            elif filepath.endswith('.json'):
                content_type = 'application/json'
            elif filepath.endswith('.svg'):
                content_type = 'image/svg+xml'

            with open(filepath, 'rb') as f:
                content = f.read()

            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.end_headers()
            self.wfile.write(content)
        else:
            # Fallback to index.html for SPA routing
            index_path = os.path.join(STATIC_DIR, 'index.html')
            if os.path.exists(index_path):
                with open(index_path, 'rb') as f:
                    content = f.read()
                self.send_response(200)
                self.send_header('Content-Type', 'text/html')
                self.end_headers()
                self.wfile.write(content)
            else:
                self.send_error(404, "File Not Found")

    def handle_api_get(self, path, query_str):
        token = get_auth_token(self)
        user = get_current_user(token)

        if path == '/api/auth/me':
            if not user:
                return self.send_error_json('Unauthorized', 401)
            conn = get_db_connection()
            c = conn.cursor()
            c.execute('SELECT * FROM employees WHERE user_id = ?', (user['id'],))
            emp = c.fetchone()
            emp_dict = dict(emp) if emp else {}

            c.execute('SELECT casual_leave, sick_leave, paid_leave FROM leave_balances WHERE employee_id = ?', (user['employee_id'],))
            leaves = c.fetchone()
            leaves_dict = dict(leaves) if leaves else {}
            conn.close()

            return self.send_json({
                'user': user,
                'employee': emp_dict,
                'leave_balances': leaves_dict
            })

        if not user:
            return self.send_error_json('Unauthorized', 401)

        conn = get_db_connection()
        c = conn.cursor()

        if path == '/api/employees':
            if user['role'] == 'HR_ADMIN':
                c.execute('''
                    SELECT e.*, u.email, u.role,
                           m.first_name || ' ' || m.last_name as manager_name
                    FROM employees e
                    JOIN users u ON e.user_id = u.id
                    LEFT JOIN employees m ON e.manager_id = m.id
                    ORDER BY e.id DESC
                ''')
            elif user['role'] == 'MANAGER':
                c.execute('''
                    SELECT e.*, u.email, u.role,
                           m.first_name || ' ' || m.last_name as manager_name
                    FROM employees e
                    JOIN users u ON e.user_id = u.id
                    LEFT JOIN employees m ON e.manager_id = m.id
                    WHERE e.manager_id = ? OR e.id = ?
                    ORDER BY e.id DESC
                ''', (user['employee_id'], user['employee_id']))
            else:
                c.execute('''
                    SELECT e.id, e.emp_code, e.first_name, e.last_name, e.designation, e.department, e.phone, u.email, u.role,
                           m.first_name || ' ' || m.last_name as manager_name
                    FROM employees e
                    JOIN users u ON e.user_id = u.id
                    LEFT JOIN employees m ON e.manager_id = m.id
                    WHERE e.status = 'ACTIVE'
                    ORDER BY e.id DESC
                ''')
            rows = [dict(r) for r in c.fetchall()]
            conn.close()
            return self.send_json({'employees': rows})

        if path == '/api/attendance':
            today = date.today().strftime('%Y-%m-%d')
            if user['role'] == 'HR_ADMIN':
                c.execute('''
                    SELECT a.*, e.emp_code, e.first_name, e.last_name, e.department
                    FROM attendance a
                    JOIN employees e ON a.employee_id = e.id
                    ORDER BY a.date DESC, a.id DESC
                ''')
            elif user['role'] == 'MANAGER':
                c.execute('''
                    SELECT a.*, e.emp_code, e.first_name, e.last_name, e.department
                    FROM attendance a
                    JOIN employees e ON a.employee_id = e.id
                    WHERE e.manager_id = ? OR e.id = ?
                    ORDER BY a.date DESC, a.id DESC
                ''', (user['employee_id'], user['employee_id']))
            else:
                c.execute('''
                    SELECT a.*, e.emp_code, e.first_name, e.last_name, e.department
                    FROM attendance a
                    JOIN employees e ON a.employee_id = e.id
                    WHERE a.employee_id = ?
                    ORDER BY a.date DESC
                ''', (user['employee_id'],))
            rows = [dict(r) for r in c.fetchall()]

            # Get today's clock state for logged in user
            c.execute('SELECT * FROM attendance WHERE employee_id = ? AND date = ?', (user['employee_id'], today))
            today_att = c.fetchone()
            today_att_dict = dict(today_att) if today_att else None

            conn.close()
            return self.send_json({
                'attendance': rows,
                'today_attendance': today_att_dict
            })

        if path == '/api/leave-requests':
            if user['role'] == 'HR_ADMIN':
                c.execute('''
                    SELECT l.*, e.emp_code, e.first_name, e.last_name, e.department,
                           r.first_name || ' ' || r.last_name as reviewer_name
                    FROM leave_requests l
                    JOIN employees e ON l.employee_id = e.id
                    LEFT JOIN employees r ON l.reviewed_by = r.id
                    ORDER BY l.created_at DESC
                ''')
            elif user['role'] == 'MANAGER':
                c.execute('''
                    SELECT l.*, e.emp_code, e.first_name, e.last_name, e.department,
                           r.first_name || ' ' || r.last_name as reviewer_name
                    FROM leave_requests l
                    JOIN employees e ON l.employee_id = e.id
                    LEFT JOIN employees r ON l.reviewed_by = r.id
                    WHERE e.manager_id = ? OR e.id = ?
                    ORDER BY l.created_at DESC
                ''', (user['employee_id'], user['employee_id']))
            else:
                c.execute('''
                    SELECT l.*, e.emp_code, e.first_name, e.last_name, e.department,
                           r.first_name || ' ' || r.last_name as reviewer_name
                    FROM leave_requests l
                    JOIN employees e ON l.employee_id = e.id
                    LEFT JOIN employees r ON l.reviewed_by = r.id
                    WHERE l.employee_id = ?
                    ORDER BY l.created_at DESC
                ''', (user['employee_id'],))
            rows = [dict(r) for r in c.fetchall()]

            c.execute('SELECT casual_leave, sick_leave, paid_leave FROM leave_balances WHERE employee_id = ?', (user['employee_id'],))
            lb = c.fetchone()
            lb_dict = dict(lb) if lb else {}

            conn.close()
            return self.send_json({
                'leave_requests': rows,
                'leave_balances': lb_dict
            })

        if path == '/api/dashboard/stats':
            today = date.today().strftime('%Y-%m-%d')
            c.execute("SELECT COUNT(*) FROM employees WHERE status = 'ACTIVE'")
            total_employees = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM attendance WHERE date = ? AND status IN ('PRESENT', 'LATE')", (today,))
            present_today = c.fetchone()[0]

            c.execute("SELECT COUNT(*) FROM leave_requests WHERE status = 'PENDING'")
            pending_leaves = c.fetchone()[0]

            c.execute("SELECT department, COUNT(*) as count FROM employees WHERE status = 'ACTIVE' GROUP BY department")
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
            return self.send_json({
                'stats': {
                    'total_employees': total_employees,
                    'present_today': present_today,
                    'pending_leaves': pending_leaves,
                    'attendance_rate': round((present_today / total_employees * 100), 1) if total_employees > 0 else 0
                },
                'dept_distribution': dept_counts,
                'recent_leaves': recent_leaves
            })

        conn.close()
        return self.send_error_json('Endpoint not found', 404)

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        data = parse_json_body(self)

        if path == '/api/auth/login':
            email = data.get('email', '').strip().lower()
            password = data.get('password', '').strip()

            if not email or not password:
                return self.send_error_json('Email and password required', 400)

            conn = get_db_connection()
            c = conn.cursor()
            c.execute('SELECT * FROM users WHERE LOWER(email) = ?', (email,))
            user = c.fetchone()

            if not user or not verify_password(user['password_hash'], user['salt'], password):
                conn.close()
                return self.send_error_json('Invalid email or password', 401)

            token = str(uuid.uuid4())
            expires_at = (datetime.now() + timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')

            c.execute('INSERT INTO sessions (token, user_id, expires_at) VALUES (?, ?, ?)',
                      (token, user['id'], expires_at))
            conn.commit()

            c.execute('SELECT * FROM employees WHERE user_id = ?', (user['id'],))
            emp = c.fetchone()
            emp_dict = dict(emp) if emp else {}

            conn.close()
            return self.send_json({
                'message': 'Login successful',
                'token': token,
                'user': {
                    'id': user['id'],
                    'email': user['email'],
                    'role': user['role']
                },
                'employee': emp_dict
            })

        token = get_auth_token(self)
        user = get_current_user(token)
        if not user:
            return self.send_error_json('Unauthorized', 401)

        conn = get_db_connection()
        c = conn.cursor()

        if path == '/api/auth/logout':
            c.execute('DELETE FROM sessions WHERE token = ?', (token,))
            conn.commit()
            conn.close()
            return self.send_json({'message': 'Logged out successfully'})

        if path == '/api/attendance/clock-in':
            today = date.today().strftime('%Y-%m-%d')
            now_time = datetime.now().strftime('%H:%M:%S')

            c.execute('SELECT * FROM attendance WHERE employee_id = ? AND date = ?', (user['employee_id'], today))
            existing = c.fetchone()

            if existing:
                conn.close()
                return self.send_error_json('Already clocked in today', 400)

            # Check if late (after 09:15:00)
            status = 'LATE' if now_time > '09:15:00' else 'PRESENT'
            notes = data.get('notes', 'Clocked in via dashboard')

            c.execute('''INSERT INTO attendance (employee_id, date, clock_in, status, notes)
                         VALUES (?, ?, ?, ?, ?)''', (user['employee_id'], today, now_time, status, notes))
            conn.commit()
            conn.close()
            return self.send_json({'message': 'Clocked in successfully', 'time': now_time, 'status': status})

        if path == '/api/attendance/clock-out':
            today = date.today().strftime('%Y-%m-%d')
            now_time = datetime.now().strftime('%H:%M:%S')

            c.execute('SELECT * FROM attendance WHERE employee_id = ? AND date = ?', (user['employee_id'], today))
            existing = c.fetchone()

            if not existing:
                conn.close()
                return self.send_error_json('Must clock in before clocking out', 400)

            if existing['clock_out']:
                conn.close()
                return self.send_error_json('Already clocked out today', 400)

            c.execute('UPDATE attendance SET clock_out = ? WHERE id = ?', (now_time, existing['id']))
            conn.commit()
            conn.close()
            return self.send_json({'message': 'Clocked out successfully', 'time': now_time})

        if path == '/api/employees':
            if user['role'] != 'HR_ADMIN':
                conn.close()
                return self.send_error_json('Forbidden: Only HR Admin can add employees', 403)

            email = data.get('email', '').strip().lower()
            password = data.get('password', 'Password123!')
            role = data.get('role', 'EMPLOYEE')
            emp_code = data.get('emp_code', '').strip()
            first_name = data.get('first_name', '').strip()
            last_name = data.get('last_name', '').strip()
            designation = data.get('designation', '').strip()
            department = data.get('department', '').strip()
            joining_date = data.get('joining_date', date.today().strftime('%Y-%m-%d'))
            salary = float(data.get('salary', 0))
            phone = data.get('phone', '')
            address = data.get('address', '')
            manager_id = data.get('manager_id')

            if not email or not emp_code or not first_name or not last_name:
                conn.close()
                return self.send_error_json('Missing required fields', 400)

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
                return self.send_json({'message': 'Employee created successfully', 'employee_id': new_emp_id}, 201)
            except sqlite3.IntegrityError as e:
                conn.close()
                return self.send_error_json('Email or Employee Code already exists', 400)

        if path == '/api/leave-requests':
            leave_type = data.get('leave_type', 'CASUAL')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            reason = data.get('reason', '').strip()

            if not start_date or not end_date or not reason:
                conn.close()
                return self.send_error_json('Start date, end date, and reason required', 400)

            d1 = datetime.strptime(start_date, '%Y-%m-%d')
            d2 = datetime.strptime(end_date, '%Y-%m-%d')
            days_count = (d2 - d1).days + 1

            if days_count <= 0:
                conn.close()
                return self.send_error_json('End date must be on or after start date', 400)

            # Check balance
            c.execute('SELECT * FROM leave_balances WHERE employee_id = ?', (user['employee_id'],))
            lb = c.fetchone()
            if lb:
                balance_col = leave_type.lower() + '_leave'
                if balance_col in lb.keys() and lb[balance_col] < days_count:
                    conn.close()
                    return self.send_error_json(f'Insufficient {leave_type} leave balance ({lb[balance_col]} days remaining)', 400)

            c.execute('''INSERT INTO leave_requests
                (employee_id, leave_type, start_date, end_date, days_count, reason, status)
                VALUES (?, ?, ?, ?, ?, ?, 'PENDING')''',
                (user['employee_id'], leave_type, start_date, end_date, days_count, reason))
            conn.commit()
            conn.close()
            return self.send_json({'message': 'Leave request submitted successfully'}, 201)

        if path.startswith('/api/leave-requests/') and path.endswith('/review'):
            if user['role'] not in ('HR_ADMIN', 'MANAGER'):
                conn.close()
                return self.send_error_json('Forbidden: Only Manager or HR Admin can review leave requests', 403)

            leave_id = path.split('/')[3]
            status = data.get('status') # 'APPROVED' or 'REJECTED'
            review_comment = data.get('review_comment', '')

            if status not in ('APPROVED', 'REJECTED'):
                conn.close()
                return self.send_error_json('Status must be APPROVED or REJECTED', 400)

            c.execute('SELECT * FROM leave_requests WHERE id = ?', (leave_id,))
            req = c.fetchone()

            if not req:
                conn.close()
                return self.send_error_json('Leave request not found', 404)

            c.execute('''UPDATE leave_requests
                         SET status = ?, reviewed_by = ?, review_comment = ?
                         WHERE id = ?''', (status, user['employee_id'], review_comment, leave_id))

            # Deduct from balance if approved
            if status == 'APPROVED':
                leave_col = req['leave_type'].lower() + '_leave'
                c.execute(f'''UPDATE leave_balances
                             SET {leave_col} = MAX(0, {leave_col} - ?)
                             WHERE employee_id = ?''', (req['days_count'], req['employee_id']))

            conn.commit()
            conn.close()
            return self.send_json({'message': f'Leave request {status.lower()} successfully'})

        conn.close()
        return self.send_error_json('Endpoint not found', 404)

    def do_PUT(self):
        token = get_auth_token(self)
        user = get_current_user(token)
        if not user or user['role'] != 'HR_ADMIN':
            return self.send_error_json('Forbidden: HR Admin access required', 403)

        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        data = parse_json_body(self)

        if path.startswith('/api/employees/'):
            emp_id = path.split('/')[3]
            conn = get_db_connection()
            c = conn.cursor()

            c.execute('SELECT * FROM employees WHERE id = ?', (emp_id,))
            emp = c.fetchone()

            if not emp:
                conn.close()
                return self.send_error_json('Employee not found', 404)

            c.execute('''UPDATE employees SET
                designation = ?, department = ?, salary = ?, phone = ?, address = ?, status = ?
                WHERE id = ?''', (
                data.get('designation', emp['designation']),
                data.get('department', emp['department']),
                float(data.get('salary', emp['salary'])),
                data.get('phone', emp['phone']),
                data.get('address', emp['address']),
                data.get('status', emp['status']),
                emp_id
            ))

            if 'role' in data:
                c.execute('UPDATE users SET role = ? WHERE id = ?', (data['role'], emp['user_id']))

            conn.commit()
            conn.close()
            return self.send_json({'message': 'Employee updated successfully'})

        return self.send_error_json('Endpoint not found', 404)

def run_server():
    os.chdir(STATIC_DIR)
    # Use PORT from environment variable (Render sets this) or default to 8000
    port = int(os.environ.get("PORT", 8000))
    print(f"DEBUG: Changing to {STATIC_DIR}, port={port}", flush=True)
    with socketserver.TCPServer(("0.0.0.0", port), EMSRequestHandler) as httpd:
        print(f"Employee Management System Server running on http://0.0.0.0:{port}", flush=True)
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            httpd.server_close()

if __name__ == '__main__':
    print("DEBUG: __main__ block", flush=True)
    run_server()