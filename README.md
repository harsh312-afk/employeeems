# Enterprise Employee Management System (EMS)

An end-to-end, full-stack internal enterprise web application built to streamline Human Resource operations, manage employee records, enforce Role-Based Access Control (RBAC), track daily attendance, and process leave approvals with data integrity and security.

---

## 🌟 Executive Overview & Benefits

### The Problem It Solves
Modern organizations require a centralized, secure system to manage workforce data, enforce role boundaries, track attendance accurately, and automate leave approval workflows. Manual paper/spreadsheet workflows lead to data fragmentation, security risks, lack of auditability, and poor employee experience.

### Key Capabilities Covered
1. **Multi-Tier Role-Based Access Control (RBAC)**: Secure access tailored for **HR Admin**, **Managers**, and **Employees**.
2. **Centralized Employee Records**: Manage profiles, designations, departments, manager hierarchies, joining dates, and salary details.
3. **Real-time Attendance Tracking**: One-click Clock In / Clock Out console with automated late detection and daily attendance logging.
4. **Automated Leave Request Workflow**: Employees submit leave requests against real-time quotas (Casual, Sick, Paid leave). Managers and HR Admins review and approve/reject with comments, automatically deducting days from balances upon approval.
5. **HR Analytics & Dashboard**: Real-time summary metrics (Total Staff, Daily Attendance Rate, Pending Leaves, Department Distribution).

---

## 🏗️ Architecture & Tech Stack

The system follows a clean, decoupled 3-tier architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                      FRONTEND TIER                          │
│   HTML5 / CSS3 (Inter Design System) / Vanilla JS (ES6+)    │
│   Single-Page Application (SPA) with Dynamic View Router    │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP REST API (JSON / Bearer Token)
┌──────────────────────────────▼──────────────────────────────┐
│                      BACKEND TIER                           │
│   Python 3 REST API Server (http.server & Custom Handler)   │
│   Session Manager & RBAC Middleware Authorization Engine    │
└──────────────────────────────┬──────────────────────────────┘
                               │ Parameterized SQL Queries
┌──────────────────────────────▼──────────────────────────────┐
│                      DATABASE TIER                          │
│   SQLite Relational Database (6 Normalized Tables)          │
│   PBKDF2 Password Hashing (SHA256 + 100k Iterations + Salts)│
└─────────────────────────────────────────────────────────────┘
```

- **Backend**: Python 3 standard library (`http.server`, `json`, `sqlite3`, `hashlib`, `uuid`). Zero external npm/pip dependencies required!
- **Database**: SQLite database with foreign key constraints, indexes, unique keys, and transactional integrity.
- **Frontend**: Responsive Single-Page Web Application (SPA) built with clean CSS variables, Inter typography, FontAwesome icons, and modular JavaScript API client.
- **Security**: PBKDF2 password hashing (SHA256 with 100,000 iterations and 16-byte random salts), cryptographically secure UUID v4 session tokens, parameterized SQL queries preventing SQL injection, and strict server-side authorization checks on every endpoint.

---

## 🗄️ Database Schema Design

The SQLite database (`ems.db`) features 6 interconnected tables:

1. **`users`**: Stores authentication credentials, password hashes, salts, and system roles (`HR_ADMIN`, `MANAGER`, `EMPLOYEE`).
2. **`employees`**: Detailed profiles linked 1:1 to `users`, including employee code, contact details, department, salary, joining date, and manager hierarchy (`manager_id`).
3. **`attendance`**: Daily attendance records tracking clock-in time, clock-out time, status (`PRESENT`, `LATE`, `HALF_DAY`, `ABSENT`), and notes.
4. **`leave_requests`**: Employee leave applications with date ranges, leave type, reason, status (`PENDING`, `APPROVED`, `REJECTED`), and reviewer comments.
5. **`leave_balances`**: Tracks remaining leave quotas per employee (Casual: 12, Sick: 10, Paid: 15).
6. **`sessions`**: Manages active Bearer authentication tokens and expiration timestamps.

---

## 🔌 REST API Specification

| HTTP Method | Endpoint | Authorization | Description |
| :--- | :--- | :--- | :--- |
| **POST** | `/api/auth/login` | Public | Authenticate user credentials & receive session token |
| **POST** | `/api/auth/logout` | Authenticated | Terminate session & revoke token |
| **GET** | `/api/auth/me` | Authenticated | Retrieve current user profile, employee data & leave balances |
| **GET** | `/api/dashboard/stats` | Authenticated | Get dashboard metrics, dept counts, and recent leaves |
| **GET** | `/api/employees` | Authenticated | Fetch employee list (Filtered by RBAC level) |
| **POST** | `/api/employees` | `HR_ADMIN` | Register a new employee & user account |
| **PUT** | `/api/employees/<id>` | `HR_ADMIN` | Update employee record or deactivate status |
| **GET** | `/api/attendance` | Authenticated | Fetch attendance history & current day's clock state |
| **POST** | `/api/attendance/clock-in` | Authenticated | Log daily Clock In time with late check |
| **POST** | `/api/attendance/clock-out` | Authenticated | Log daily Clock Out time |
| **GET** | `/api/leave-requests` | Authenticated | Fetch leave applications & quotas |
| **POST** | `/api/leave-requests` | Authenticated | Submit new leave application |
| **POST** | `/api/leave-requests/<id>/review` | `MANAGER`, `HR_ADMIN` | Approve or reject a leave request |

---

## 🚀 Quick Start & Execution Guide

### 1. Launch the Server
Run the backend server using Python 3:

```bash
python3 backend/app.py
```

Output:
```text
Seeding demo data into database...
Database initialized successfully at /tmp/ems.db
Employee Management System Server running on http://localhost:8000
```

### 2. Access the Web Application
Open your web browser and navigate to:
`http://localhost:8000`

### 3. Demo Credentials

Use any of the pre-seeded accounts to experience role-specific features:

| Role | Email | Password | Primary Capabilities |
| :--- | :--- | :--- | :--- |
| **HR Admin** | `hr@company.com` | `Password123!` | Company-wide visibility, add/edit employees, approve leaves, full HR analytics |
| **Manager** | `manager@company.com` | `Password123!` | View team members, track team attendance, approve/reject team leave requests |
| **Employee** | `employee1@company.com` | `Password123!` | View personal profile, clock in/out, check leave balances, apply for leave |

---

## 🎯 How This Showcases Full-Stack Engineering Excellence

- **Enterprise Security**: Implements industry-standard PBKDF2 password hashing, Bearer Token authentication, and defense-in-depth authorization.
- **Role-Based Access Control**: Strict multi-level RBAC enforced on both backend REST API routes and adaptive frontend UI rendering.
- **Data Integrity & Automation**: Automated leave balance deduction upon approval, late clock-in detection, and strict database constraints.
- **Modern Responsive UI**: Clean Inter design system with dashboard stat cards, responsive tables, real-time clock console, and modal dialogs.
- **Zero External Overhead**: High-performance architecture leveraging native web standards and Python standard libraries.
