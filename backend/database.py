import sqlite3
import hashlib
import os

DB_PATH = os.environ.get('EMS_DB_PATH', '/tmp/ems.db')

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
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
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
        FOREIGN KEY (user_id) REFERENCES users(id),
        FOREIGN KEY (manager_id) REFERENCES employees(id)
    );

    CREATE TABLE IF NOT EXISTS attendance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        date TEXT NOT NULL,
        clock_in TEXT,
        clock_out TEXT,
        status TEXT DEFAULT 'PRESENT' CHECK(status IN ('PRESENT', 'LATE', 'HALF_DAY', 'ABSENT')),
        notes TEXT,
        UNIQUE(employee_id, date),
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    );

    CREATE TABLE IF NOT EXISTS leave_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER NOT NULL,
        leave_type TEXT CHECK(leave_type IN ('CASUAL', 'SICK', 'PAID', 'UNPAID')),
        start_date TEXT NOT NULL,
        end_date TEXT NOT NULL,
        days_count INTEGER NOT NULL,
        reason TEXT NOT NULL,
        status TEXT DEFAULT 'PENDING' CHECK(status IN ('PENDING', 'APPROVED', 'REJECTED')),
        reviewed_by INTEGER,
        review_comment TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (employee_id) REFERENCES employees(id),
        FOREIGN KEY (reviewed_by) REFERENCES employees(id)
    );

    CREATE TABLE IF NOT EXISTS leave_balances (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        employee_id INTEGER UNIQUE NOT NULL,
        casual_leave INTEGER DEFAULT 12,
        sick_leave INTEGER DEFAULT 10,
        paid_leave INTEGER DEFAULT 15,
        FOREIGN KEY (employee_id) REFERENCES employees(id)
    );

    CREATE TABLE IF NOT EXISTS sessions (
        token TEXT PRIMARY KEY,
        user_id INTEGER NOT NULL,
        expires_at TIMESTAMP NOT NULL,
        FOREIGN KEY (user_id) REFERENCES users(id)
    );
    ''')

    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        print("Seeding demo data into database...")
        demo_users = [
            ("hr@company.com", "Password123!", "HR_ADMIN", "EMP-101", "Sarah", "Jenkins", "HR Director", "Human Resources", "2022-01-15", 95000.0, "+15550192", "San Francisco, CA", None),
            ("manager@company.com", "Password123!", "MANAGER", "EMP-102", "David", "Miller", "Engineering Manager", "Engineering", "2022-03-01", 120000.0, "+15550193", "San Jose, CA", 1),
            ("employee1@company.com", "Password123!", "EMPLOYEE", "EMP-103", "Alex", "Rivera", "Senior Full Stack Engineer", "Engineering", "2023-05-10", 85000.0, "+15550194", "Oakland, CA", 2),
            ("employee2@company.com", "Password123!", "EMPLOYEE", "EMP-104", "Emily", "Chen", "UI/UX Designer", "Design", "2023-08-20", 78000.0, "+15550195", "Berkeley, CA", 2),
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

        import datetime
        today = datetime.date.today().strftime('%Y-%m-%d')
        yesterday = (datetime.date.today() - datetime.timedelta(days=1)).strftime('%Y-%m-%d')
        
        sample_attendances = [
            (1, today, "08:55:00", "17:05:00", "PRESENT", "On time"),
            (2, today, "09:02:00", "17:30:00", "PRESENT", "On time"),
            (3, today, "09:18:00", "17:15:00", "LATE", "Traffic delay"),
            (4, today, "08:50:00", "17:00:00", "PRESENT", "On time"),
            (1, yesterday, "09:00:00", "17:00:00", "PRESENT", "Regular"),
            (2, yesterday, "08:58:00", "17:10:00", "PRESENT", "Regular"),
            (3, yesterday, "09:00:00", "17:00:00", "PRESENT", "Regular"),
            (4, yesterday, "09:05:00", "17:00:00", "PRESENT", "Regular"),
        ]

        for emp_id, dt, cin, cout, st, nts in sample_attendances:
            cursor.execute('''INSERT INTO attendance (employee_id, date, clock_in, clock_out, status, notes)
                VALUES (?, ?, ?, ?, ?, ?)''', (emp_id, dt, cin, cout, st, nts))

        cursor.execute('''INSERT INTO leave_requests 
            (employee_id, leave_type, start_date, end_date, days_count, reason, status)
            VALUES (?, 'CASUAL', '2026-08-10', '2026-08-12', 3, 'Family function and vacation', 'PENDING')''', (3,))

    conn.commit()
    conn.close()
    print("Database initialized successfully at", DB_PATH)

if __name__ == '__main__':
    init_db()
