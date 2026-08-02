// Enterprise Employee Management System - SPA Frontend Logic

const API_BASE = '/api';
let currentUser = null;
let currentEmployee = null;
let authToken = localStorage.getItem('ems_auth_token') || null;

// DOM Elements
const loginScreen = document.getElementById('login-screen');
const appScreen = document.getElementById('app-screen');
const loginForm = document.getElementById('login-form');
const loginError = document.getElementById('login-error');

// API Helper
async function apiCall(endpoint, method = 'GET', data = null) {
    const headers = { 'Content-Type': 'application/json' };
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }

    const config = { method, headers };
    if (data) {
        config.body = JSON.stringify(data);
    }

    try {
        const res = await fetch(`${API_BASE}${endpoint}`, config);
        const json = await res.json();
        if (!res.ok) {
            throw new Error(json.error || 'Server error occurred');
        }
        return json;
    } catch (err) {
        throw err;
    }
}

// Preset credentials filler
function fillCredentials(email, password) {
    document.getElementById('login-email').value = email;
    document.getElementById('login-password').value = password;
}

// Clock widget updater
function startClock() {
    setInterval(() => {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('en-US', { hour12: false });
        const timeDisp = document.getElementById('current-time-display');
        if (timeDisp) timeDisp.textContent = timeStr;
    }, 1000);
}

// App Initialization
document.addEventListener('DOMContentLoaded', () => {
    startClock();
    checkAuthStatus();
    setupEventListeners();
});

async function checkAuthStatus() {
    if (!authToken) {
        showLoginScreen();
        return;
    }

    try {
        const data = await apiCall('/auth/me');
        currentUser = data.user;
        currentEmployee = data.employee;
        showAppScreen();
        loadDashboard();
    } catch (err) {
        console.error('Session expired or invalid:', err);
        localStorage.removeItem('ems_auth_token');
        authToken = null;
        showLoginScreen();
    }
}

function showLoginScreen() {
    loginScreen.classList.remove('hidden');
    appScreen.classList.add('hidden');
}

function showAppScreen() {
    loginScreen.classList.add('hidden');
    appScreen.classList.remove('hidden');

    // Update Navigation User Widget
    const initials = (currentUser.first_name ? currentUser.first_name[0] : '') + (currentUser.last_name ? currentUser.last_name[0] : 'U');
    document.getElementById('nav-user-avatar').textContent = initials || 'U';
    document.getElementById('nav-user-name').textContent = `${currentUser.first_name || ''} ${currentUser.last_name || ''}`.trim() || currentUser.email;
    document.getElementById('nav-user-role').textContent = currentUser.role;

    // RBAC UI Elements
    if (currentUser.role === 'HR_ADMIN') {
        document.getElementById('btn-add-employee').classList.remove('hidden');
    } else {
        document.getElementById('btn-add-employee').classList.add('hidden');
    }

    // Set today's date badge
    const todayStr = new Date().toLocaleDateString('en-US', { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric' });
    const badge = document.getElementById('today-date-badge');
    if (badge) badge.textContent = todayStr;
}

function setupEventListeners() {
    // Login Form Submit
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        loginError.classList.add('hidden');

        const email = document.getElementById('login-email').value;
        const password = document.getElementById('login-password').value;

        try {
            const data = await apiCall('/auth/login', 'POST', { email, password });
            authToken = data.token;
            localStorage.setItem('ems_auth_token', authToken);
            currentUser = { ...data.user, ...data.employee };
            currentEmployee = data.employee;
            showAppScreen();
            loadDashboard();
        } catch (err) {
            loginError.textContent = err.message;
            loginError.classList.remove('hidden');
        }
    });

    // Logout
    document.getElementById('logout-btn').addEventListener('click', async () => {
        try {
            await apiCall('/auth/logout', 'POST');
        } catch (err) { }
        localStorage.removeItem('ems_auth_token');
        authToken = null;
        currentUser = null;
        currentEmployee = null;
        showLoginScreen();
    });

    // Navigation Tabs
    document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('.sidebar-nav .nav-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            const view = item.getAttribute('data-view');
            switchView(view);
        });
    });

    // Quick Clock Buttons
    document.getElementById('btn-clock-in').addEventListener('click', clockIn);
    document.getElementById('btn-clock-out').addEventListener('click', clockOut);
    document.getElementById('console-clock-in-btn').addEventListener('click', clockIn);
    document.getElementById('console-clock-out-btn').addEventListener('click', clockOut);

    // Modals Close handlers
    document.querySelectorAll('.close-modal, .close-modal-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            document.querySelectorAll('.modal').forEach(m => m.classList.remove('active'));
        });
    });

    // Open Add Employee Modal
    document.getElementById('btn-add-employee').addEventListener('click', () => {
        document.getElementById('modal-add-emp').classList.add('active');
    });

    // Form Submit: Add Employee
    document.getElementById('form-add-emp').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            first_name: document.getElementById('add-fname').value,
            last_name: document.getElementById('add-lname').value,
            email: document.getElementById('add-email').value,
            emp_code: document.getElementById('add-code').value,
            role: document.getElementById('add-role').value,
            department: document.getElementById('add-dept').value,
            designation: document.getElementById('add-desig').value,
            salary: document.getElementById('add-salary').value,
            joining_date: document.getElementById('add-joining').value,
            phone: document.getElementById('add-phone').value
        };

        try {
            await apiCall('/employees', 'POST', payload);
            alert('Employee registered successfully!');
            document.getElementById('modal-add-emp').classList.remove('active');
            document.getElementById('form-add-emp').reset();
            loadEmployees();
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    });

    // Open Apply Leave Modal
    document.getElementById('btn-apply-leave').addEventListener('click', () => {
        document.getElementById('modal-apply-leave').classList.add('active');
    });

    // Form Submit: Apply Leave
    document.getElementById('form-apply-leave').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            leave_type: document.getElementById('leave-type').value,
            start_date: document.getElementById('leave-start').value,
            end_date: document.getElementById('leave-end').value,
            reason: document.getElementById('leave-reason').value
        };

        try {
            await apiCall('/leave-requests', 'POST', payload);
            alert('Leave application submitted!');
            document.getElementById('modal-apply-leave').classList.remove('active');
            document.getElementById('form-apply-leave').reset();
            loadLeaves();
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    });

    // Form Submit: Review Leave
    document.getElementById('form-review-leave').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = document.getElementById('review-leave-id').value;
        const payload = {
            status: document.getElementById('review-status').value,
            review_comment: document.getElementById('review-comment').value
        };

        try {
            await apiCall(`/leave-requests/${id}/review`, 'POST', payload);
            alert('Review decision saved!');
            document.getElementById('modal-review-leave').classList.remove('active');
            loadLeaves();
        } catch (err) {
            alert(`Error: ${err.message}`);
        }
    });

    // Search Employee
    document.getElementById('emp-search').addEventListener('input', (e) => {
        const query = e.target.value.toLowerCase();
        const rows = document.querySelectorAll('#employee-table-body tr');
        rows.forEach(row => {
            const text = row.textContent.toLowerCase();
            row.style.display = text.includes(query) ? '' : 'none';
        });
    });
}

function switchView(viewName) {
    document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
    const target = document.getElementById(`view-${viewName}`);
    if (target) target.classList.add('active');

    // Page titles
    const titles = {
        'dashboard': ['Organization Dashboard', 'Real-time metrics and company overview'],
        'employees': ['Employee Directory', 'Manage staff records and profiles'],
        'attendance': ['Attendance Tracker', 'Daily clock in/out logs and history'],
        'leaves': ['Leave Management', 'Request leave and manager approvals'],
        'profile': ['My Profile', 'Personal employee details']
    };

    if (titles[viewName]) {
        document.getElementById('page-title').textContent = titles[viewName][0];
        document.getElementById('page-subtitle').textContent = titles[viewName][1];
    }

    if (viewName === 'dashboard') loadDashboard();
    else if (viewName === 'employees') loadEmployees();
    else if (viewName === 'attendance') loadAttendance();
    else if (viewName === 'leaves') loadLeaves();
    else if (viewName === 'profile') loadProfile();
}

async function loadDashboard() {
    try {
        const data = await apiCall('/dashboard/stats');
        const s = data.stats;
        document.getElementById('stat-total-emp').textContent = s.total_employees;
        document.getElementById('stat-present-today').textContent = s.present_today;
        document.getElementById('stat-att-rate').textContent = `${s.attendance_rate}% Attendance Rate`;
        document.getElementById('stat-pending-leaves').textContent = s.pending_leaves;
        document.getElementById('stat-depts-count').textContent = data.dept_distribution.length;

        // Department list
        const deptList = document.getElementById('dept-list');
        deptList.innerHTML = data.dept_distribution.map(d => `
            <li>
                <span>${d.department}</span>
                <strong>${d.count} employees</strong>
            </li>
        `).join('');

        // Recent Leaves
        const recentTable = document.getElementById('recent-leaves-table');
        recentTable.innerHTML = data.recent_leaves.map(l => `
            <tr>
                <td><strong>${l.first_name} ${l.last_name}</strong><br><small class="text-muted">${l.department}</small></td>
                <td><span class="badge badge-info">${l.leave_type}</span></td>
                <td>${l.start_date} to ${l.end_date} (${l.days_count}d)</td>
                <td><span class="badge badge-${getLeaveBadgeClass(l.status)}">${l.status}</span></td>
            </tr>
        `).join('');
    } catch (err) {
        console.error('Error loading dashboard:', err);
    }
}

async function loadEmployees() {
    try {
        const data = await apiCall('/employees');
        const tbody = document.getElementById('employee-table-body');
        tbody.innerHTML = data.employees.map(e => `
            <tr>
                <td><code>${e.emp_code}</code></td>
                <td>
                    <strong>${e.first_name} ${e.last_name}</strong><br>
                    <small style="color:var(--text-muted);">${e.email}</small>
                </td>
                <td>${e.designation}</td>
                <td><span class="badge badge-info">${e.department}</span></td>
                <td>${e.manager_name || 'N/A'}</td>
                <td><span class="badge badge-${e.status === 'ACTIVE' ? 'success' : 'danger'}">${e.status}</span></td>
                <td>
                    ${currentUser.role === 'HR_ADMIN' ? `
                        <button class="btn btn-sm btn-outline" onclick="deactivateEmployee(${e.id})">
                            <i class="fa-solid fa-user-slash"></i>
                        </button>
                    ` : `<span style="color:var(--text-muted);">View Only</span>`}
                </td>
            </tr>
        `).join('');
    } catch (err) {
        console.error('Error loading employees:', err);
    }
}

async function loadAttendance() {
    try {
        const data = await apiCall('/attendance');
        const tbody = document.getElementById('attendance-table-body');
        tbody.innerHTML = data.attendance.map(a => `
            <tr>
                <td><strong>${a.date}</strong></td>
                <td>${a.first_name} ${a.last_name} (<code>${a.emp_code}</code>)</td>
                <td>${a.department}</td>
                <td><code>${a.clock_in || '--:--'}</code></td>
                <td><code>${a.clock_out || '--:--'}</code></td>
                <td><span class="badge badge-${getAttendanceBadgeClass(a.status)}">${a.status}</span></td>
                <td>${a.notes || ''}</td>
            </tr>
        `).join('');

        // Update Console & Header clock state
        const todayAtt = data.today_attendance;
        const consoleStatus = document.getElementById('console-status');
        const consoleTime = document.getElementById('console-time-details');

        if (todayAtt) {
            consoleStatus.textContent = todayAtt.status;
            consoleTime.textContent = `In: ${todayAtt.clock_in} ${todayAtt.clock_out ? '| Out: ' + todayAtt.clock_out : ''}`;
            
            document.getElementById('btn-clock-in').classList.add('hidden');
            document.getElementById('console-clock-in-btn').classList.add('hidden');

            if (!todayAtt.clock_out) {
                document.getElementById('btn-clock-out').classList.remove('hidden');
                document.getElementById('console-clock-out-btn').classList.remove('hidden');
            } else {
                document.getElementById('btn-clock-out').classList.add('hidden');
                document.getElementById('console-clock-out-btn').classList.add('hidden');
            }
        } else {
            consoleStatus.textContent = 'Not Clocked In';
            consoleTime.textContent = 'Clock in to mark attendance for today';
            document.getElementById('btn-clock-in').classList.remove('hidden');
            document.getElementById('console-clock-in-btn').classList.remove('hidden');
            document.getElementById('btn-clock-out').classList.add('hidden');
            document.getElementById('console-clock-out-btn').classList.add('hidden');
        }
    } catch (err) {
        console.error('Error loading attendance:', err);
    }
}

async function clockIn() {
    try {
        const res = await apiCall('/attendance/clock-in', 'POST', { notes: 'Clocked in via Web App' });
        alert(`Clocked In successfully at ${res.time}! Status: ${res.status}`);
        loadAttendance();
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
}

async function clockOut() {
    try {
        const res = await apiCall('/attendance/clock-out', 'POST');
        alert(`Clocked Out successfully at ${res.time}!`);
        loadAttendance();
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
}

async function loadLeaves() {
    try {
        const data = await apiCall('/leave-requests');
        const lb = data.leave_balances;

        document.getElementById('bal-casual').textContent = lb.casual_leave !== undefined ? lb.casual_leave : 12;
        document.getElementById('bal-sick').textContent = lb.sick_leave !== undefined ? lb.sick_leave : 10;
        document.getElementById('bal-paid').textContent = lb.paid_leave !== undefined ? lb.paid_leave : 15;

        const tbody = document.getElementById('leave-table-body');
        tbody.innerHTML = data.leave_requests.map(l => `
            <tr>
                <td><strong>${l.first_name} ${l.last_name}</strong><br><small class="text-muted">${l.department}</small></td>
                <td><span class="badge badge-info">${l.leave_type}</span></td>
                <td>${l.start_date} to ${l.end_date}</td>
                <td><strong>${l.days_count} d</strong></td>
                <td>${l.reason}</td>
                <td><span class="badge badge-${getLeaveBadgeClass(l.status)}">${l.status}</span></td>
                <td>${l.reviewer_name || '--'}</td>
                <td>
                    ${(l.status === 'PENDING' && (currentUser.role === 'HR_ADMIN' || currentUser.role === 'MANAGER')) ? `
                        <button class="btn btn-sm btn-primary" onclick="openReviewModal(${l.id}, '${l.first_name} ${l.last_name}', '${l.leave_type}', ${l.days_count})">
                            <i class="fa-solid fa-gavel"></i> Review
                        </button>
                    ` : `<span style="color:var(--text-muted); font-size:0.8rem;">Completed</span>`}
                </td>
            </tr>
        `).join('');
    } catch (err) {
        console.error('Error loading leaves:', err);
    }
}

function openReviewModal(id, empName, leaveType, days) {
    document.getElementById('review-leave-id').value = id;
    document.getElementById('review-leave-details').innerHTML = `Reviewing <strong>${leaveType}</strong> request from <strong>${empName}</strong> (${days} days).`;
    document.getElementById('modal-review-leave').classList.add('active');
}

async function loadProfile() {
    try {
        const data = await apiCall('/auth/me');
        const e = data.employee;
        const initials = (e.first_name ? e.first_name[0] : '') + (e.last_name ? e.last_name[0] : 'U');

        document.getElementById('prof-avatar').textContent = initials;
        document.getElementById('prof-fullname').textContent = `${e.first_name} ${e.last_name}`;
        document.getElementById('prof-designation').textContent = e.designation;
        document.getElementById('prof-role-badge').textContent = data.user.role;

        document.getElementById('prof-code').textContent = e.emp_code;
        document.getElementById('prof-dept').textContent = e.department;
        document.getElementById('prof-email').textContent = data.user.email;
        document.getElementById('prof-phone').textContent = e.phone || 'N/A';
        document.getElementById('prof-joining').textContent = e.joining_date;
        document.getElementById('prof-address').textContent = e.address || 'N/A';
    } catch (err) {
        console.error('Error loading profile:', err);
    }
}

async function deactivateEmployee(empId) {
    if (!confirm('Are you sure you want to deactivate this employee?')) return;
    try {
        await apiCall(`/employees/${empId}`, 'PUT', { status: 'INACTIVE' });
        alert('Employee deactivated.');
        loadEmployees();
    } catch (err) {
        alert(`Error: ${err.message}`);
    }
}

function getLeaveBadgeClass(status) {
    if (status === 'APPROVED') return 'success';
    if (status === 'REJECTED') return 'danger';
    return 'warning';
}

function getAttendanceBadgeClass(status) {
    if (status === 'PRESENT') return 'success';
    if (status === 'LATE') return 'warning';
    if (status === 'HALF_DAY') return 'info';
    return 'danger';
}
