# Enterprise Employee Management System (EMS)

An end-to-end, full-stack internal enterprise web application built to streamline Human Resource operations, manage employee records, enforce Role-Based Access Control (RBAC), track daily attendance with work duration metrics, and process leave approvals with data integrity, security, and CSV reporting.

---

## 🌟 Executive Overview & Capabilities

### The Problem It Solves
Modern organizations require a centralized, secure system to manage workforce data, enforce role boundaries, track attendance accurately, and automate leave approval workflows. Manual paper/spreadsheet workflows lead to data fragmentation, security risks, lack of auditability, and poor employee experience.

### Key Capabilities Covered
1. **Multi-Tier Role-Based Access Control (RBAC)**: Secure access tailored for **HR Admin**, **Managers**, and **Employees**.
2. **Centralized Employee Records & Directory**: Manage profiles, designations, departments, manager hierarchies, joining dates, salary details, and account activation/deactivation.
3. **Real-time Attendance Tracking & Duration**: One-click Clock In / Clock Out console with automated late detection, daily attendance logging, and work duration tracking.
4. **Automated Leave Request Workflow**: Employees submit leave requests against real-time quotas (Casual, Sick, Paid, and Unpaid leave). Managers and HR Admins review and approve/reject with comments, automatically deducting days from balances upon approval. Employees can cancel pending requests.
5. **HR Analytics & Dashboard**: Real-time summary metrics (Total Headcount, Daily Attendance Rate, Pending Leaves, Department Distribution).
6. **Executive CSV Exports**: One-click export of Employee Directory and Attendance Logs for compliance and payroll audits.
7. **Personal Profile & Credential Management**: Update contact information and self-service secure password changes with PBKDF2 hashing.
8. **Modern Responsive UI**: Professional toast notifications (replacing browser alerts), modal dialogs, real-time search & filters, and mobile drawer navigation.

---

## 🏗️ Architecture & Tech Stack

The system follows a clean, decoupled 3-tier architecture:

```
┌─────────────────────────────────────────────────────────────┐
│                      FRONTEND TIER                          │
│   HTML5 / CSS3 (Inter Design System) / Vanilla JS (ES6+)    │
│   Single-Page Application (SPA) with Dynamic View Router    │
│   Toast Notification System & Modal Dialog Controllers      │
└──────────────────────────────┬──────────────────────────────┘
                               │ HTTP REST API (JSON / Bearer Token)
┌──────────────────────────────▼──────────────────────────────┐
│                      BACKEND TIER                           │
│   Python 3 Server & Vercel Serverless Function              │
│   Session Manager & RBAC Middleware Authorization Engine    │
└──────────────────────────────┬──────────────────────────────┘
                               │ Parameterized SQL Queries
┌──────────────────────────────▼──────────────────────────────┐
│                      DATABASE TIER                          │
│   SQLite Relational Database (6 Normalized Tables + Indexes)│
│   PBKDF2 Password Hashing (SHA256 + 100k Iterations + Salts)│
└─────────────────────────────────────────────────────────────┘
```

- **Backend**: Python 3 standard library (`http.server`, `json`, `sqlite3`, `hashlib`, `uuid`, `csv`). **Zero external npm/pip dependencies required!**
- **Vercel Serverless Ready**: Native deployment via `@vercel/python` service with zero configuration.
- **Database**: SQLite database with foreign key constraints, indexes, unique keys, and transactional integrity.
- **Frontend**: Responsive Single-Page Web Application (SPA) built with clean CSS variables, Inter typography, FontAwesome icons, and modular JavaScript API client.
- **Security**: PBKDF2 password hashing (SHA256 with 100,000 iterations and 16-byte random salts), cryptographically secure UUID v4 session tokens, parameterized SQL queries preventing SQL injection, whitelisted column mappings, and strict server-side authorization checks on every endpoint.

---

## 🗄️ Database Schema Design

The SQLite database (`ems.db`) features 6 interconnected tables with dedicated indexes:

1. **`users`**: Stores authentication credentials, password hashes, salts, and system roles (`HR_ADMIN`, `MANAGER`, `EMPLOYEE`).
2. **`employees`**: Detailed profiles linked 1:1 to `users`, including employee code, contact details, department, salary, joining date, status (`ACTIVE`, `INACTIVE`), and manager hierarchy (`manager_id`).
3. **`attendance`**: Daily attendance records tracking clock-in time, clock-out time, hours worked (`hours_worked`), status (`PRESENT`, `LATE`, `HALF_DAY`, `ABSENT`), and notes.
4. **`leave_requests`**: Employee leave applications with date ranges, leave type (`CASUAL`, `SICK`, `PAID`, `UNPAID`), reason, status (`PENDING`, `APPROVED`, `REJECTED`, `CANCELLED`), and reviewer comments.
5. **`leave_balances`**: Tracks remaining leave quotas per employee (Casual: 12, Sick: 10, Paid: 15).
6. **`sessions`**: Manages active Bearer authentication tokens and expiration timestamps.

---

## 🔌 REST API Specification

| HTTP Method | Endpoint | Authorization | Description |
| :--- | :--- | :--- | :--- |
| **POST** | `/api/auth/login` | Public | Authenticate user credentials & receive session token |
| **POST** | `/api/auth/logout` | Authenticated | Terminate session & revoke token |
| **GET** | `/api/auth/me` | Authenticated | Retrieve current user profile, employee data & leave balances |
| **PUT** | `/api/auth/profile` | Authenticated | Update personal contact info (phone, address) |
| **POST** | `/api/auth/change-password` | Authenticated | Change user password with current password verification |
| **GET** | `/api/dashboard/stats` | Authenticated | Get dashboard metrics, dept counts, and recent leaves |
| **GET** | `/api/employees` | Authenticated | Fetch employee list (Supports `department`, `status`, `search` filters) |
| **POST** | `/api/employees` | `HR_ADMIN` | Register a new employee & user account |
| **PUT** | `/api/employees/<id>` | `HR_ADMIN` | Update employee record, manager, salary, or status |
| **GET** | `/api/attendance` | Authenticated | Fetch attendance history, today's clock state, and monthly summary |
| **POST** | `/api/attendance/clock-in` | Authenticated | Log daily Clock In time with automated late detection |
| **POST** | `/api/attendance/clock-out` | Authenticated | Log daily Clock Out time and compute hours worked |
| **GET** | `/api/leave-requests` | Authenticated | Fetch leave applications (Supports `status`, `leave_type` filters) |
| **POST** | `/api/leave-requests` | Authenticated | Submit new leave application against quota |
| **POST** | `/api/leave-requests/<id>/review` | `MANAGER`, `HR_ADMIN` | Approve or reject a pending leave request |
| **POST** | `/api/leave-requests/<id>/cancel` | Authenticated | Cancel personal pending leave request |
| **GET** | `/api/export/employees` | `HR_ADMIN` | Download Employee Directory as CSV |
| **GET** | `/api/export/attendance` | `MANAGER`, `HR_ADMIN` | Download Attendance Log as CSV |
| **POST** | `/api/admin/reset-demo` | `HR_ADMIN` | Reset database to initial demo state |

---

## 🚀 Quick Start & Execution Guide

### 1. Launch the Server Locally
Run the backend server using Python 3:

```bash
python3 backend/app.py
```

Output:
```text
Seeding demo data into database...
Database initialized successfully at /tmp/ems.db
Employee Management System running on http://0.0.0.0:8000 (Serving .../frontend)
```

### 2. Access the Web Application
Open your web browser and navigate to:
`http://localhost:8000`

### 3. Run Automated API Test Suite
Run the comprehensive test suite verifying all routes, permissions, data integrity, and exports:

```bash
python3 backend/test_api.py
```

---

## 🌐 Live Deployment on Vercel

The application is deployed and publicly available on Vercel:

🔗 **Production URL**: [https://employeeems.vercel.app](https://employeeems.vercel.app)

Deploy updates with:
```bash
vercel --prod
```

`vercel.json` coordinates serverless execution and static assets without requiring extra configurations or external build tools.

---

## 🔑 Demo Credentials

Use any of the pre-seeded accounts to experience role-specific features:

| Role | Email | Password | Primary Capabilities |
| :--- | :--- | :--- | :--- |
| **HR Admin** | `hr@company.com` | `Password123!` | Company-wide visibility, add/edit employees, toggle active status, review leaves, export CSV, full HR analytics |
| **Manager** | `manager@company.com` | `Password123!` | View team members, track team attendance, approve/reject team leave requests, export attendance |
| **Employee** | `employee1@company.com` | `Password123!` | View personal profile, clock in/out, check leave balances, apply for leave, cancel requests |
| **Designer** | `employee2@company.com` | `Password123!` | Employee role with Design department context |

---

## 🎯 Key Engineering Highlights

- **Enterprise Security**: Industry-standard PBKDF2 password hashing, Bearer Token authentication, defense-in-depth authorization, sanitized SQL queries.
- **Role-Based Access Control**: Strict multi-level RBAC enforced across REST API endpoints and responsive frontend views.
- **Zero Dependencies**: Pure Python 3 standard library backend and native ES6+ frontend.
- **Resilient Serverless Architecture**: Ephemeral and persistent SQLite handling tailored for cloud environments.
- **Production UI/UX**: In-app Toast notifications, confirmation modals, CSV exports, duration tracking, and responsive design for desktop and mobile.
