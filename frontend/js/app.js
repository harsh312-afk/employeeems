// Enterprise Employee Management System - Modern SPA Frontend Controller

const API_BASE = '/api';
let currentUser = null;
let currentEmployee = null;
let authToken = localStorage.getItem('ems_auth_token') || null;
let allEmployees = [];
let availableManagers = [];

// DOM Elements
const loginScreen = document.getElementById('login-screen');
const appScreen = document.getElementById('app-screen');
const loginForm = document.getElementById('login-form');
const loginError = document.getElementById('login-error');
const sidebar = document.getElementById('sidebar');
const sidebarOverlay = document.getElementById('sidebar-overlay');
const mobileToggleBtn = document.getElementById('btn-mobile-toggle');

// ==========================================
// TOAST NOTIFICATION SYSTEM
// ==========================================
function showToast(message, type = 'info', duration = 3500) {
    const container = document.getElementById('toast-container');
    if (!container) return;

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    let iconClass = 'fa-solid fa-circle-info';
    if (type === 'success') iconClass = 'fa-solid fa-circle-check';
    else if (type === 'error') iconClass = 'fa-solid fa-circle-exclamation';
    else if (type === 'warning') iconClass = 'fa-solid fa-triangle-exclamation';

    toast.innerHTML = `
        <i class="${iconClass} toast-icon"></i>
        <div class="toast-message">${escapeHtml(message)}</div>
        <button class="toast-close">&times;</button>
    `;

    const closeBtn = toast.querySelector('.toast-close');
    const removeToast = () => {
        toast.classList.add('toast-hiding');
        setTimeout(() => toast.remove(), 250);
    };

    closeBtn.addEventListener('click', removeToast);
    container.appendChild(toast);

    if (duration > 0) {
        setTimeout(removeToast, duration);
    }
}

// Confirmation Dialog Modal
function showConfirmDialog(title, message, onConfirm) {
    const modal = document.getElementById('modal-confirm');
    document.getElementById('confirm-modal-title').innerHTML = `<i class="fa-solid fa-triangle-exclamation text-warning"></i> ${title}`;
    document.getElementById('confirm-modal-message').textContent = message;

    const acceptBtn = document.getElementById('btn-confirm-accept');
    const cancelBtn = document.getElementById('btn-confirm-cancel');

    const handleAccept = () => {
        cleanup();
        if (typeof onConfirm === 'function') onConfirm();
    };

    const handleCancel = () => {
        cleanup();
    };

    const cleanup = () => {
        modal.classList.remove('active');
        acceptBtn.removeEventListener('click', handleAccept);
        cancelBtn.removeEventListener('click', handleCancel);
    };

    acceptBtn.addEventListener('click', handleAccept);
    cancelBtn.addEventListener('click', handleCancel);
    modal.classList.add('active');
}

// Password Visibility Toggle
function togglePasswordVisibility(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    const btn = input.parentElement.querySelector('.btn-toggle-pwd i');
    if (input.type === 'password') {
        input.type = 'text';
        if (btn) {
            btn.classList.remove('fa-eye');
            btn.classList.add('fa-eye-slash');
        }
    } else {
        input.type = 'password';
        if (btn) {
            btn.classList.remove('fa-eye-slash');
            btn.classList.add('fa-eye');
        }
    }
}

// Helper: Escape HTML
function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// ==========================================
// API CLIENT
// ==========================================
async function apiCall(endpoint, method = 'GET', data = null, isDownload = false) {
    const headers = {};
    if (authToken) {
        headers['Authorization'] = `Bearer ${authToken}`;
    }

    const config = { method, headers };
    if (data) {
        headers['Content-Type'] = 'application/json';
        config.body = JSON.stringify(data);
    }

    try {
        const res = await fetch(`${API_BASE}${endpoint}`, config);

        if (isDownload) {
            if (!res.ok) {
                const json = await res.json().catch(() => ({}));
                throw new Error(json.error || 'Failed to download file');
            }
            return await res.blob();
        }

        const json = await res.json().catch(() => ({}));
        if (!res.ok) {
            throw new Error(json.error || 'A server error occurred');
        }
        return json;
    } catch (err) {
        throw err;
    }
}

// Quick Preset credentials filler
function fillCredentials(email, password) {
    document.getElementById('login-email').value = email;
    document.getElementById('login-password').value = password;
    showToast(`Loaded preset credentials for ${email}`, 'info', 2000);
}

// Live Header Clock
function startClock() {
    const updateTime = () => {
        const now = new Date();
        const timeStr = now.toLocaleTimeString('en-US', { hour12: false });
        const timeDisp = document.getElementById('current-time-display');
        if (timeDisp) timeDisp.textContent = timeStr;
    };
    updateTime();
    setInterval(updateTime, 1000);
}

// ==========================================
// APPLICATION INITIALIZATION
// ==========================================
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
        console.warn('Session expired or invalid:', err.message);
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
    const firstInitial = (currentEmployee.first_name || currentUser.email || 'U')[0].toUpperCase();
    const lastInitial = (currentEmployee.last_name || '')[0] ? currentEmployee.last_name[0].toUpperCase() : '';
    document.getElementById('nav-user-avatar').textContent = (firstInitial + lastInitial) || 'U';

    const fullName = `${currentEmployee.first_name || ''} ${currentEmployee.last_name || ''}`.trim();
    document.getElementById('nav-user-name').textContent = fullName || currentUser.email;
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

// ==========================================
// EVENT LISTENERS
// ==========================================
function setupEventListeners() {
    // Mobile Drawer Toggle
    if (mobileToggleBtn && sidebar && sidebarOverlay) {
        mobileToggleBtn.addEventListener('click', () => {
            sidebar.classList.toggle('mobile-open');
            sidebarOverlay.classList.toggle('active');
        });
        sidebarOverlay.addEventListener('click', () => {
            sidebar.classList.remove('mobile-open');
            sidebarOverlay.classList.remove('active');
        });
    }

    // Login Form Submit
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        loginError.classList.add('hidden');
        const submitBtn = document.getElementById('btn-submit-login');
        const originalContent = submitBtn.innerHTML;
        submitBtn.disabled = true;
        submitBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Authenticating...';

        const email = document.getElementById('login-email').value.trim();
        const password = document.getElementById('login-password').value;

        try {
            const data = await apiCall('/auth/login', 'POST', { email, password });
            authToken = data.token;
            localStorage.setItem('ems_auth_token', authToken);
            currentUser = data.user;
            currentEmployee = data.employee;
            showAppScreen();
            loadDashboard();
            showToast('Welcome back! Signed in successfully.', 'success');
        } catch (err) {
            loginError.textContent = err.message;
            loginError.classList.remove('hidden');
            showToast(err.message, 'error');
        } finally {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalContent;
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
        showToast('Signed out successfully.', 'info');
    });

    // Sidebar Navigation Tabs
    document.querySelectorAll('.sidebar-nav .nav-item').forEach(item => {
        item.addEventListener('click', (e) => {
            e.preventDefault();
            document.querySelectorAll('.sidebar-nav .nav-item').forEach(i => i.classList.remove('active'));
            item.classList.add('active');

            // Close mobile drawer if open
            if (sidebar && sidebar.classList.contains('mobile-open')) {
                sidebar.classList.remove('mobile-open');
                sidebarOverlay.classList.remove('active');
            }

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
        populateManagerDropdown('add-manager');
        document.getElementById('modal-add-emp').classList.add('active');
    });

    // Form Submit: Add Employee
    document.getElementById('form-add-emp').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            first_name: document.getElementById('add-fname').value.trim(),
            last_name: document.getElementById('add-lname').value.trim(),
            email: document.getElementById('add-email').value.trim(),
            emp_code: document.getElementById('add-code').value.trim(),
            role: document.getElementById('add-role').value,
            department: document.getElementById('add-dept').value.trim(),
            designation: document.getElementById('add-desig').value.trim(),
            salary: document.getElementById('add-salary').value,
            joining_date: document.getElementById('add-joining').value,
            phone: document.getElementById('add-phone').value.trim(),
            manager_id: document.getElementById('add-manager').value,
            password: document.getElementById('add-pwd').value
        };

        try {
            await apiCall('/employees', 'POST', payload);
            showToast('Employee registered successfully!', 'success');
            document.getElementById('modal-add-emp').classList.remove('active');
            document.getElementById('form-add-emp').reset();
            loadEmployees();
        } catch (err) {
            showToast(err.message, 'error');
        }
    });

    // Form Submit: Edit Employee
    document.getElementById('form-edit-emp').addEventListener('submit', async (e) => {
        e.preventDefault();
        const empId = document.getElementById('edit-emp-id').value;
        const payload = {
            first_name: document.getElementById('edit-fname').value.trim(),
            last_name: document.getElementById('edit-lname').value.trim(),
            designation: document.getElementById('edit-desig').value.trim(),
            department: document.getElementById('edit-dept').value.trim(),
            salary: document.getElementById('edit-salary').value,
            manager_id: document.getElementById('edit-manager').value,
            role: document.getElementById('edit-role').value,
            status: document.getElementById('edit-status').value,
            phone: document.getElementById('edit-phone').value.trim(),
            address: document.getElementById('edit-address').value.trim()
        };

        try {
            await apiCall(`/employees/${empId}`, 'PUT', payload);
            showToast('Employee record updated successfully!', 'success');
            document.getElementById('modal-edit-emp').classList.remove('active');
            loadEmployees();
        } catch (err) {
            showToast(err.message, 'error');
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
            reason: document.getElementById('leave-reason').value.trim()
        };

        try {
            await apiCall('/leave-requests', 'POST', payload);
            showToast('Leave request submitted successfully!', 'success');
            document.getElementById('modal-apply-leave').classList.remove('active');
            document.getElementById('form-apply-leave').reset();
            loadLeaves();
        } catch (err) {
            showToast(err.message, 'error');
        }
    });

    // Form Submit: Review Leave
    document.getElementById('form-review-leave').addEventListener('submit', async (e) => {
        e.preventDefault();
        const id = document.getElementById('review-leave-id').value;
        const payload = {
            status: document.getElementById('review-status').value,
            review_comment: document.getElementById('review-comment').value.trim()
        };

        try {
            await apiCall(`/leave-requests/${id}/review`, 'POST', payload);
            showToast(`Leave request ${payload.status.toLowerCase()}!`, 'success');
            document.getElementById('modal-review-leave').classList.remove('active');
            loadLeaves();
        } catch (err) {
            showToast(err.message, 'error');
        }
    });

    // Form Submit: Update Profile Contact Info
    document.getElementById('form-update-profile').addEventListener('submit', async (e) => {
        e.preventDefault();
        const payload = {
            phone: document.getElementById('prof-edit-phone').value.trim(),
            address: document.getElementById('prof-edit-address').value.trim()
        };

        try {
            await apiCall('/auth/profile', 'PUT', payload);
            showToast('Contact details saved successfully!', 'success');
            loadProfile();
        } catch (err) {
            showToast(err.message, 'error');
        }
    });

    // Form Submit: Change Password
    document.getElementById('form-change-password').addEventListener('submit', async (e) => {
        e.preventDefault();
        const current_password = document.getElementById('pwd-current').value;
        const new_password = document.getElementById('pwd-new').value;
        const confirm_password = document.getElementById('pwd-confirm').value;

        if (new_password !== confirm_password) {
            showToast('New passwords do not match', 'warning');
            return;
        }

        try {
            await apiCall('/auth/change-password', 'POST', { current_password, new_password });
            showToast('Password changed successfully!', 'success');
            document.getElementById('form-change-password').reset();
        } catch (err) {
            showToast(err.message, 'error');
        }
    });

    // Employee Filter & Search
    document.getElementById('emp-search').addEventListener('input', filterEmployeeList);
    document.getElementById('emp-dept-filter').addEventListener('change', filterEmployeeList);
    document.getElementById('emp-status-filter').addEventListener('change', filterEmployeeList);

    // Attendance Filter
    document.getElementById('att-status-filter').addEventListener('change', (e) => {
        loadAttendance(e.target.value);
    });

    // Leave Status Filter
    document.getElementById('leave-status-filter').addEventListener('change', (e) => {
        loadLeaves(e.target.value);
    });

    // Export CSV Handlers
    document.getElementById('btn-export-employees').addEventListener('click', () => downloadCsv('/export/employees', 'employees_export.csv'));
    document.getElementById('btn-export-attendance').addEventListener('click', () => downloadCsv('/export/attendance', 'attendance_export.csv'));
}

// Download CSV Utility
async function downloadCsv(endpoint, filename) {
    try {
        showToast('Generating CSV export...', 'info', 1500);
        const blob = await apiCall(endpoint, 'GET', null, true);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        a.remove();
        showToast('Download started!', 'success');
    } catch (err) {
        showToast(`Export failed: ${err.message}`, 'error');
    }
}

// ==========================================
// VIEW ROUTER & DATA LOADERS
// ==========================================
function switchView(viewName) {
    document.querySelectorAll('.view-panel').forEach(p => p.classList.remove('active'));
    const target = document.getElementById(`view-${viewName}`);
    if (target) target.classList.add('active');

    const titles = {
        'dashboard': ['Organization Dashboard', 'Real-time metrics and company overview'],
        'employees': ['Employee Directory', 'Manage staff records and profiles'],
        'attendance': ['Attendance Tracker', 'Daily clock in/out logs and history'],
        'leaves': ['Leave Management', 'Request leave and manager approvals'],
        'profile': ['My Profile', 'Personal details and credentials']
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
                <span>${escapeHtml(d.department)}</span>
                <strong>${d.count} staff</strong>
            </li>
        `).join('') || '<li class="empty-placeholder">No departments recorded.</li>';

        // Recent Leaves
        const recentTable = document.getElementById('recent-leaves-table');
        if (data.recent_leaves.length === 0) {
            recentTable.innerHTML = '<tr><td colspan="4" class="empty-placeholder">No recent leave requests.</td></tr>';
        } else {
            recentTable.innerHTML = data.recent_leaves.map(l => `
                <tr>
                    <td><strong>${escapeHtml(l.first_name)} ${escapeHtml(l.last_name)}</strong><br><small class="text-secondary">${escapeHtml(l.department)}</small></td>
                    <td><span class="badge badge-info">${escapeHtml(l.leave_type)}</span></td>
                    <td>${escapeHtml(l.start_date)} to ${escapeHtml(l.end_date)} (${l.days_count}d)</td>
                    <td><span class="badge badge-${getLeaveBadgeClass(l.status)}">${escapeHtml(l.status)}</span></td>
                </tr>
            `).join('');
        }
    } catch (err) {
        console.error('Error loading dashboard:', err);
    }
}

async function loadEmployees() {
    try {
        const data = await apiCall('/employees');
        allEmployees = data.employees || [];
        availableManagers = data.managers || [];

        // Populate Department filter options
        const deptFilter = document.getElementById('emp-dept-filter');
        const currentSelectedDept = deptFilter.value;
        deptFilter.innerHTML = '<option value="">All Departments</option>' +
            (data.departments || []).map(d => `<option value="${escapeHtml(d)}" ${currentSelectedDept === d ? 'selected' : ''}>${escapeHtml(d)}</option>`).join('');

        renderEmployeeTable(allEmployees);
    } catch (err) {
        console.error('Error loading employees:', err);
        showToast(err.message, 'error');
    }
}

function filterEmployeeList() {
    const query = document.getElementById('emp-search').value.toLowerCase();
    const dept = document.getElementById('emp-dept-filter').value;
    const status = document.getElementById('emp-status-filter').value;

    const filtered = allEmployees.filter(e => {
        const matchQuery = !query ||
            e.first_name.toLowerCase().includes(query) ||
            e.last_name.toLowerCase().includes(query) ||
            e.emp_code.toLowerCase().includes(query) ||
            e.designation.toLowerCase().includes(query);

        const matchDept = !dept || e.department === dept;
        const matchStatus = !status || e.status === status;

        return matchQuery && matchDept && matchStatus;
    });

    renderEmployeeTable(filtered);
}

function renderEmployeeTable(employees) {
    const tbody = document.getElementById('employee-table-body');
    if (!employees || employees.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="empty-placeholder">No employees found matching filter criteria.</td></tr>';
        return;
    }

    tbody.innerHTML = employees.map(e => `
        <tr>
            <td><code>${escapeHtml(e.emp_code)}</code></td>
            <td>
                <strong>${escapeHtml(e.first_name)} ${escapeHtml(e.last_name)}</strong><br>
                <small class="text-secondary">${escapeHtml(e.email)}</small>
            </td>
            <td>${escapeHtml(e.designation)}</td>
            <td><span class="badge badge-info">${escapeHtml(e.department)}</span></td>
            <td>${escapeHtml(e.manager_name || 'N/A')}</td>
            <td><span class="badge badge-${e.status === 'ACTIVE' ? 'success' : 'danger'}">${escapeHtml(e.status)}</span></td>
            <td>
                ${currentUser.role === 'HR_ADMIN' ? `
                    <div style="display:flex; gap:0.4rem;">
                        <button class="btn btn-sm btn-outline" title="Edit Employee" onclick="openEditEmployeeModal(${e.id})">
                            <i class="fa-solid fa-pen-to-square"></i>
                        </button>
                        <button class="btn btn-sm ${e.status === 'ACTIVE' ? 'btn-outline text-danger' : 'btn-outline text-success'}" 
                                title="${e.status === 'ACTIVE' ? 'Deactivate' : 'Activate'}" 
                                onclick="toggleEmployeeStatus(${e.id}, '${e.first_name} ${e.last_name}', '${e.status}')">
                            <i class="fa-solid ${e.status === 'ACTIVE' ? 'fa-user-slash' : 'fa-user-check'}"></i>
                        </button>
                    </div>
                ` : `<span class="text-secondary" style="font-size:0.8rem;">View Only</span>`}
            </td>
        </tr>
    `).join('');
}

function populateManagerDropdown(selectId, selectedId = null) {
    const select = document.getElementById(selectId);
    if (!select) return;
    select.innerHTML = '<option value="">No Manager (Top Level)</option>' +
        availableManagers.map(m => `
            <option value="${m.id}" ${selectedId == m.id ? 'selected' : ''}>
                ${escapeHtml(m.name)} (${escapeHtml(m.department)})
            </option>
        `).join('');
}

function openEditEmployeeModal(empId) {
    const emp = allEmployees.find(e => e.id === empId);
    if (!emp) return;

    document.getElementById('edit-emp-id').value = emp.id;
    document.getElementById('edit-fname').value = emp.first_name || '';
    document.getElementById('edit-lname').value = emp.last_name || '';
    document.getElementById('edit-desig').value = emp.designation || '';
    document.getElementById('edit-dept').value = emp.department || '';
    document.getElementById('edit-salary').value = emp.salary || '';
    document.getElementById('edit-role').value = emp.role || 'EMPLOYEE';
    document.getElementById('edit-status').value = emp.status || 'ACTIVE';
    document.getElementById('edit-phone').value = emp.phone || '';
    document.getElementById('edit-address').value = emp.address || '';

    populateManagerDropdown('edit-manager', emp.manager_id);
    document.getElementById('modal-edit-emp').classList.add('active');
}

function toggleEmployeeStatus(empId, name, currentStatus) {
    const newStatus = currentStatus === 'ACTIVE' ? 'INACTIVE' : 'ACTIVE';
    const actionText = newStatus === 'ACTIVE' ? 'activate' : 'deactivate';

    showConfirmDialog(
        `${actionText.toUpperCase()} Employee`,
        `Are you sure you want to ${actionText} ${name}? Inactive employees cannot sign in.`,
        async () => {
            try {
                await apiCall(`/employees/${empId}`, 'PUT', { status: newStatus });
                showToast(`Employee ${name} is now ${newStatus.toLowerCase()}.`, 'success');
                loadEmployees();
            } catch (err) {
                showToast(err.message, 'error');
            }
        }
    );
}

async function loadAttendance(statusFilter = '') {
    try {
        const query = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : '';
        const data = await apiCall(`/attendance${query}`);
        const tbody = document.getElementById('attendance-table-body');

        if (!data.attendance || data.attendance.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-placeholder">No attendance records found.</td></tr>';
        } else {
            tbody.innerHTML = data.attendance.map(a => `
                <tr>
                    <td><strong>${escapeHtml(a.date)}</strong></td>
                    <td>${escapeHtml(a.first_name)} ${escapeHtml(a.last_name)} (<code>${escapeHtml(a.emp_code)}</code>)</td>
                    <td>${escapeHtml(a.department)}</td>
                    <td><code>${escapeHtml(a.clock_in || '--:--')}</code></td>
                    <td><code>${escapeHtml(a.clock_out || '--:--')}</code></td>
                    <td><strong>${a.hours_worked ? `${a.hours_worked} hrs` : (a.clock_in && !a.clock_out ? 'In Progress' : '--')}</strong></td>
                    <td><span class="badge badge-${getAttendanceBadgeClass(a.status)}">${escapeHtml(a.status)}</span></td>
                    <td>${escapeHtml(a.notes || '')}</td>
                </tr>
            `).join('');
        }

        // Monthly Summary card
        if (data.month_stats) {
            document.getElementById('month-stat-present').textContent = data.month_stats.present_days;
            document.getElementById('month-stat-late').textContent = data.month_stats.late_days;
            document.getElementById('month-stat-hours').textContent = `${data.month_stats.total_hours}h`;
        }

        // Clock State UI
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
            consoleTime.textContent = 'Click below to mark your attendance for today';
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
        const localTime = new Date().toTimeString().split(' ')[0];
        const res = await apiCall('/attendance/clock-in', 'POST', {
            notes: 'Clocked in via portal',
            client_time: localTime
        });
        showToast(`Clocked in at ${res.time} (${res.status})!`, 'success');
        loadAttendance();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function clockOut() {
    try {
        const localTime = new Date().toTimeString().split(' ')[0];
        const res = await apiCall('/attendance/clock-out', 'POST', {
            client_time: localTime
        });
        showToast(`Clocked out successfully at ${res.time} (${res.hours_worked || 0} hrs logged)!`, 'success');
        loadAttendance();
    } catch (err) {
        showToast(err.message, 'error');
    }
}

async function loadLeaves(statusFilter = '') {
    try {
        const query = statusFilter ? `?status=${encodeURIComponent(statusFilter)}` : '';
        const data = await apiCall(`/leave-requests${query}`);
        const lb = data.leave_balances;

        document.getElementById('bal-casual').textContent = lb.casual_leave !== undefined ? lb.casual_leave : 12;
        document.getElementById('bal-sick').textContent = lb.sick_leave !== undefined ? lb.sick_leave : 10;
        document.getElementById('bal-paid').textContent = lb.paid_leave !== undefined ? lb.paid_leave : 15;

        const tbody = document.getElementById('leave-table-body');
        if (!data.leave_requests || data.leave_requests.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-placeholder">No leave requests found.</td></tr>';
            return;
        }

        tbody.innerHTML = data.leave_requests.map(l => {
            const canReview = l.status === 'PENDING' && (currentUser.role === 'HR_ADMIN' || currentUser.role === 'MANAGER');
            const canCancel = l.status === 'PENDING' && (l.employee_id === currentUser.employee_id || currentUser.role === 'HR_ADMIN');

            return `
                <tr>
                    <td><strong>${escapeHtml(l.first_name)} ${escapeHtml(l.last_name)}</strong><br><small class="text-secondary">${escapeHtml(l.department)}</small></td>
                    <td><span class="badge badge-info">${escapeHtml(l.leave_type)}</span></td>
                    <td>${escapeHtml(l.start_date)} to ${escapeHtml(l.end_date)}</td>
                    <td><strong>${l.days_count} d</strong></td>
                    <td>${escapeHtml(l.reason)}</td>
                    <td><span class="badge badge-${getLeaveBadgeClass(l.status)}">${escapeHtml(l.status)}</span></td>
                    <td>${escapeHtml(l.reviewer_name || '--')}</td>
                    <td>
                        <div style="display:flex; gap:0.4rem;">
                            ${canReview ? `
                                <button class="btn btn-sm btn-primary" onclick="openReviewModal(${l.id}, '${escapeHtml(l.first_name)} ${escapeHtml(l.last_name)}', '${l.leave_type}', ${l.days_count})">
                                    <i class="fa-solid fa-gavel"></i> Review
                                </button>
                            ` : ''}
                            ${canCancel ? `
                                <button class="btn btn-sm btn-outline text-danger" title="Cancel Request" onclick="cancelLeaveRequest(${l.id})">
                                    <i class="fa-solid fa-ban"></i> Cancel
                                </button>
                            ` : (!canReview ? `<span class="text-secondary" style="font-size:0.8rem;">Finished</span>` : '')}
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    } catch (err) {
        console.error('Error loading leaves:', err);
    }
}

function openReviewModal(id, empName, leaveType, days) {
    document.getElementById('review-leave-id').value = id;
    document.getElementById('review-leave-details').innerHTML = `Reviewing <strong>${leaveType}</strong> request from <strong>${empName}</strong> (${days} days total).`;
    document.getElementById('modal-review-leave').classList.add('active');
}

function cancelLeaveRequest(leaveId) {
    showConfirmDialog(
        'Cancel Leave Request',
        'Are you sure you want to cancel this pending leave request?',
        async () => {
            try {
                await apiCall(`/leave-requests/${leaveId}/cancel`, 'POST');
                showToast('Leave request cancelled.', 'info');
                loadLeaves();
            } catch (err) {
                showToast(err.message, 'error');
            }
        }
    );
}

async function loadProfile() {
    try {
        const data = await apiCall('/auth/me');
        const e = data.employee;
        currentUser = data.user;
        currentEmployee = data.employee;

        const firstInitial = (e.first_name || 'U')[0].toUpperCase();
        const lastInitial = (e.last_name || '')[0] ? e.last_name[0].toUpperCase() : '';
        document.getElementById('prof-avatar').textContent = firstInitial + lastInitial;
        document.getElementById('prof-fullname').textContent = `${e.first_name} ${e.last_name}`;
        document.getElementById('prof-designation').textContent = e.designation;
        document.getElementById('prof-role-badge').textContent = data.user.role;

        document.getElementById('prof-code').textContent = e.emp_code;
        document.getElementById('prof-dept').textContent = e.department;
        document.getElementById('prof-email').textContent = data.user.email;
        document.getElementById('prof-phone').textContent = e.phone || 'N/A';
        document.getElementById('prof-joining').textContent = e.joining_date;
        document.getElementById('prof-address').textContent = e.address || 'N/A';

        // Pre-fill edit fields
        document.getElementById('prof-edit-phone').value = e.phone || '';
        document.getElementById('prof-edit-address').value = e.address || '';
    } catch (err) {
        console.error('Error loading profile:', err);
    }
}

function getLeaveBadgeClass(status) {
    if (status === 'APPROVED') return 'success';
    if (status === 'REJECTED') return 'danger';
    if (status === 'CANCELLED') return 'secondary';
    return 'warning';
}

function getAttendanceBadgeClass(status) {
    if (status === 'PRESENT') return 'success';
    if (status === 'LATE') return 'warning';
    if (status === 'HALF_DAY') return 'info';
    return 'danger';
}
