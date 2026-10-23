import sqlite3
import hashlib
import os
import datetime

def get_db_path():
    if 'EMS_DB_PATH' in os.environ:
        return os.environ['EMS_DB_PATH']
    # Check Vercel serverless environment or Unix /tmp
    if os.environ.get('VERCEL') or os.path.exists('/tmp'):
        return '/tmp/ems.db'
    return os.path.join(os.path.dirname(__file__), 'ems.db')

DB_PATH = get_db_path()

def hash_password(password, salt=None):
    if salt is None:
        salt = os.urandom(16).hex()
    hashed = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        100000
    ).hex()
    return hashed, salt

def verify_password(stored_hash, salt, password):
    hashed, _ = hash_password(password, salt)
    return stored_hash == hashed

def get_db_connection():
    db_file = get_db_path()
    needs_init = not os.path.exists(db_file)
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    if needs_init:
        init_db(conn)
    return conn

def init_db(existing_conn=None):
    conn = existing_conn or sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.executescript('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('HR_ADMIN', 'MANAGER', 'EMPLOYEE')),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS employees (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER UNIQUE NOT NULL,
        emp_code TEXT UNIQUE NOT NULL,
        first_name TEXT NOT NULL,
        last_name TEXT NOT NULL,
        designation TEXT NOT NULL,
        department TEXT NOT NULL,
        joining_date TEXT NOT NULL,
        salary REAL NOT NULL,
        phone TEXT,
        address TEXT,
        manager_id INTEGER,
        status TEXT DEFAULT 'ACTIVE' CHECK(status IN ('ACTIVE', 'INACTIVE')),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (manager_id) REFERENCES employees(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        clock_in TEXT,
        clock_out TEXT,
        hours_worked REAL DEFAULT 0,
        status TEXT DEFAULT 'PRESENT' CHECK(status IN ('PRESENT', 'LATE', 'HALF_DAY', 'ABSENT')),
        notes TEXT,
        UNIQUE(employee_id, date),
        FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        leave_type TEXT CHECK(leave_type IN ('CASUAL', 'SICK', 'PAID', 'UNPAID')),
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        days_count INTEGER NOT NULL,
        reason TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED', 'CANCELLED')),
        reviewed_by INTEGER,
        review_comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE,
        FOREIGN KEY (reviewed_by) REFERENCES employees(id) ON DELETE SET NULL
    );

    CREATE TABLE IF NOT EXISTS leave_balances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER UNIQUE NOT NULL,
        casual_leave INTEGER DEFAULT 12,
        sick_leave INTEGER DEFAULT 10,
        paid_leave INTEGER DEFAULT 15,
        FOREIGN KEY (employee_id) REFERENCES employees(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
    CREATE INDEX IF NOT EXISTS idx_sessions_token ON sessions(token);
    CREATE INDEX IF NOT EXISTS idx_employees_user_id ON employees(user_id);
    CREATE INDEX IF NOT EXISTS idx_employees_manager_id ON employees(manager_id);
    CREATE INDEX IF NOT EXISTS idx_employees_status ON employees(status);
    CREATE INDEX IF NOT EXISTS idx_attendance_emp_date ON attendance(employee_id, date);
    CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date);
    CREATE INDEX IF NOT EXISTS idx_leave_requests_emp ON leave_requests(employee_id);
    CREATE INDEX IF NOT EXISTS idx_leave_requests_status ON leave_requests(status);
    ''')

    # Migration check for hours_worked column in case table already existed
    cursor.execute("PRAGMA table_info(attendance)")
    att_cols = [row['name'] if isinstance(row, sqlite3.Row) else row[1] for row in cursor.fetchall()]
    if 'hours_worked' not in att_cols:
        try:
            cursor.execute("ALTER TABLE attendance ADD COLUMN hours_worked REAL DEFAULT 0")
        except Exception:
            pass

    cursor.execute("SELECT COUNT(*) FROM users")
    user_count = cursor.fetchone()[0]
    if user_count == 0:
        seed_data(cursor)

    conn.commit()
    if not existing_conn:
        conn.close()
    print("Database initialized successfully at", get_db_path())

def seed_data(cursor):
    print("Seeding demo data into database...")
    demo_users = [
        ("hr@company.com", "Password123!", "HR_ADMIN", "EMP-101", "Sarah", "Jenkins", "HR Director", "Human Resources", "2022-01-15", 95000.0, "+1 (555) 019-2001", "100 Market St, San Francisco, CA", None),
        ("manager@company.com", "Password123!", "MANAGER", "EMP-102", "David", "Miller", "Engineering Manager", "Engineering", "2022-03-01", 125000.0, "+1 (555) 019-2002", "450 1st St, San Jose, CA", 1),
        ("employee1@company.com", "Password123!", "EMPLOYEE", "EMP-103", "Alex", "Rivera", "Senior Full Stack Engineer", "Engineering", "2023-05-10", 92000.0, "+1 (555) 019-2003", "720 Broadway, Oakland, CA", 2),
        ("employee2@company.com", "Password123!", "EMPLOYEE", "EMP-104", "Emily", "Chen", "UI/UX Product Designer", "Design", "2023-08-20", 82000.0, "+1 (555) 019-2004", "180 Shattuck Ave, Berkeley, CA", 2),
        ("finance@company.com", "Password123!", "MANAGER", "EMP-105", "Michael", "Chang", "Finance Lead", "Finance", "2022-06-12", 110000.0, "+1 (555) 019-2005", "300 Montgomery St, San Francisco, CA", 1),
        ("devops@company.com", "Password123!", "EMPLOYEE", "EMP-106", "Sophia", "Patel", "Cloud DevOps Specialist", "Infrastructure", "2023-11-01", 96000.0, "+1 (555) 019-2006", "550 University Ave, Palo Alto, CA", 2),
    ]

    for email, pwd, role, code, fname, lname, desig, dept, join_dt, sal, phone, addr, mgr_id in demo_users:
        p_hash, salt = hash_password(pwd)
        cursor.execute("INSERT INTO users (email, password_hash, salt, role) VALUES (?, ?, ?, ?)",
                       (email, p_hash, salt, role))
        user_id = cursor.lastrowid

        cursor.execute('''INSERT INTO employees 
            (user_id, emp_code, first_name, last_name, designation, department, joining_date, salary, phone, address, manager_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
            (user_id, code, fname, lname, desig, dept, join_dt, sal, phone, addr, mgr_id))
        emp_id = cursor.lastrowid

        cursor.execute("INSERT INTO leave_balances (employee_id, casual_leave, sick_leave, paid_leave) VALUES (?, 12, 10, 15)", (emp_id,))

    today = datetime.date.today().strftime('%Y-%m-%d')
    yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
    day_before = (datetime.date.today() - datetime.timedelta(days=2)).strftime('%Y-%m-%d')
    
    sample_attendances = [
        (1, today, "08:55:00", "17:05:00", 8.16, "PRESENT", "On time"),
        (2, today, "09:02:00", "17:30:00", 8.46, "PRESENT", "On time"),
        (3, today, "09:22:00", "17:15:00", 7.88, "LATE", "Public transit delay"),
        (4, today, "08:50:00", "17:00:00", 8.16, "PRESENT", "On time"),
        (5, today, "08:45:00", "16:45:00", 8.00, "PRESENT", "Early arrival"),
        (6, today, "09:05:00", None, 0.0, "PRESENT", "In office"),
        (1, yesterday, "09:00:00", "17:00:00", 8.0, "PRESENT", "Regular schedule"),
        (2, yesterday, "08:58:00", "17:10:00", 8.2, "PRESENT", "Regular schedule"),
        (3, yesterday, "09:00:00", "17:00:00", 8.0, "PRESENT", "Regular schedule"),
        (4, yesterday, "09:05:00", "17:00:00", 7.9, "PRESENT", "Regular schedule"),
        (5, yesterday, "09:12:00", "17:30:00", 8.3, "PRESENT", "Regular schedule"),
        (1, day_before, "08:50:00", "17:00:00", 8.16, "PRESENT", "Regular schedule"),
        (2, day_before, "08:55:00", "17:00:00", 8.08, "PRESENT", "Regular schedule"),
        (3, day_before, "09:30:00", "17:30:00", 8.00, "LATE", "Dentist appointment"),
    ]

    for emp_id, dt, cin, cout, hrs, st, nts in sample_attendances:
        cursor.execute('''INSERT OR IGNORE INTO attendance (employee_id, date, clock_in, clock_out, hours_worked, status, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?)''', (emp_id, dt, cin, cout, hrs, st, nts))

    sample_leaves = [
        (3, 'CASUAL', '2026-11-10', '2026-11-12', 3, 'Attending family wedding ceremony', 'PENDING', None, None),
        (4, 'SICK', yesterday, yesterday, 1, 'Severe flu and medical recovery', 'APPROVED', 2, 'Approved, feel better soon!'),
        (6, 'PAID', '2026-12-24', '2026-12-28', 5, 'Year-end holiday vacation', 'PENDING', None, None),
    ]

    for emp_id, ltype, sdate, edate, days, reason, st, rby, rcomm in sample_leaves:
        cursor.execute('''INSERT INTO leave_requests 
            (employee_id, leave_type, start_date, end_date, days_count, reason, status, reviewed_by, review_comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)''', (emp_id, ltype, sdate, edate, days, reason, st, rby, rcomm))

def reset_database():
    db_file = get_db_path()
    if os.path.exists(db_file):
        try:
            os.remove(db_file)
        except Exception:
            pass
    init_db()

if __name__ == '__main__':
    init_db()
