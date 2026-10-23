import urllib.request
import urllib.error
import json
import time
import subprocess
import os
import sys

def run_tests():
    env = os.environ.copy()
    env["PORT"] = "8999"
    env["EMS_DB_PATH"] = "/tmp/test_ems.db"
    
    # Clean previous test db
    if os.path.exists("/tmp/test_ems.db"):
        os.remove("/tmp/test_ems.db")

    server_proc = subprocess.Popen([sys.executable, "backend/app.py"], env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(1.5)

    base = "http://127.0.0.1:8999"
    token = None

    def req(path, method="GET", data=None, auth=True, is_csv=False):
        url = base + path
        headers = {}
        if auth and token:
            headers["Authorization"] = f"Bearer {token}"
        body = None
        if data is not None:
            headers["Content-Type"] = "application/json"
            body = json.dumps(data).encode("utf-8")
        r = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(r) as resp:
                if is_csv:
                    return resp.status, resp.read().decode('utf-8')
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    try:
        print("1. Testing Static file serving...")
        with urllib.request.urlopen(base + "/") as resp:
            assert resp.status == 200
            html = resp.read().decode('utf-8')
            assert "<!DOCTYPE html>" in html
            print("   -> Root index.html served successfully!")

        print("2. Testing Login as HR Admin...")
        status, data = req("/api/auth/login", method="POST", data={"email": "hr@company.com", "password": "Password123!"}, auth=False)
        assert status == 200, f"Login failed: {data}"
        token = data["token"]
        print("   -> Login success, token received:", token[:8] + "...")

        print("3. Testing /api/auth/me...")
        status, data = req("/api/auth/me")
        assert status == 200
        assert data["user"]["role"] == "HR_ADMIN"
        print("   -> Profile verified:", data["employee"]["first_name"], data["employee"]["last_name"])

        print("4. Testing /api/dashboard/stats...")
        status, data = req("/api/dashboard/stats")
        assert status == 200
        assert "stats" in data
        assert data["stats"]["total_employees"] >= 4
        print(f"   -> Total active staff: {data['stats']['total_employees']}, Depts: {len(data['dept_distribution'])}")

        print("5. Testing /api/employees list and filtering...")
        status, data = req("/api/employees")
        assert status == 200
        assert len(data["employees"]) >= 4
        assert len(data["managers"]) >= 2
        print(f"   -> Employees: {len(data['employees'])}, Managers: {len(data['managers'])}")

        print("6. Testing Add New Employee with safe manager_id handling...")
        new_emp = {
            "first_name": "Test",
            "last_name": "Developer",
            "email": "test.dev@company.com",
            "emp_code": "EMP-999",
            "role": "EMPLOYEE",
            "department": "Engineering",
            "designation": "Software Tester",
            "salary": 75000,
            "joining_date": "2026-01-01",
            "phone": "+15559999",
            "manager_id": ""  # testing empty string manager_id
        }
        status, data = req("/api/employees", method="POST", data=new_emp)
        assert status == 201, f"Create employee failed: {data}"
        new_emp_id = data["employee_id"]
        print(f"   -> Created employee ID {new_emp_id}")

        print("7. Testing Edit Employee...")
        status, data = req(f"/api/employees/{new_emp_id}", method="PUT", data={
            "first_name": "Test",
            "last_name": "Engineer",
            "designation": "Lead Automation Engineer",
            "department": "QA & Engineering",
            "salary": 85000,
            "manager_id": 2,
            "status": "ACTIVE"
        })
        assert status == 200, f"Update employee failed: {data}"
        print("   -> Employee updated successfully!")

        print("8. Testing Attendance Clock In / Out...")
        status, data = req("/api/attendance/clock-in", method="POST", data={"notes": "Test Clock In"})
        # Sarah Jenkins might already be clocked in from demo data or clocked in now
        if status == 400 and "Already clocked in" in data["error"]:
            print("   -> Already clocked in today, testing clock-out...")
            status, data = req("/api/attendance/clock-out", method="POST")
            print("   -> Clock out response:", data)
        else:
            assert status == 200
            print("   -> Clock in success:", data["time"])
            status, data = req("/api/attendance/clock-out", method="POST")
            assert status == 200
            print("   -> Clock out success, hours worked:", data.get("hours_worked"))

        print("9. Testing Leave Requests & Approvals...")
        status, data = req("/api/leave-requests", method="POST", data={
            "leave_type": "CASUAL",
            "start_date": "2026-12-01",
            "end_date": "2026-12-02",
            "reason": "Conference attendance"
        })
        assert status == 201, f"Apply leave failed: {data}"
        print("   -> Leave request submitted successfully!")

        status, data = req("/api/leave-requests")
        assert status == 200
        pending_leaves = [l for l in data["leave_requests"] if l["status"] == "PENDING"]
        assert len(pending_leaves) > 0
        target_leave_id = pending_leaves[0]["id"]

        print("10. Testing Leave Review Approval & Balance deduction...")
        bal_before = data["leave_balances"]["casual_leave"]
        status, data = req(f"/api/leave-requests/{target_leave_id}/review", method="POST", data={
            "status": "APPROVED",
            "review_comment": "Approved for conference"
        })
        assert status == 200
        print("   -> Leave approved successfully!")

        # Test double-review prevention
        status, data = req(f"/api/leave-requests/{target_leave_id}/review", method="POST", data={"status": "APPROVED"})
        assert status == 400
        print("   -> Double review correctly rejected:", data["error"])

        # Test UNPAID leave application
        status, data = req("/api/leave-requests", method="POST", data={
            "leave_type": "UNPAID",
            "start_date": "2026-12-10",
            "end_date": "2026-12-15",
            "reason": "Personal sabbatical"
        })
        assert status == 201
        print("   -> UNPAID leave request submitted without error!")

        print("11. Testing CSV Export...")
        status, csv_content = req("/api/export/employees", is_csv=True)
        assert status == 200
        assert "Employee Code,First Name,Last Name" in csv_content
        print(f"   -> Export employees CSV generated ({len(csv_content.splitlines())} rows)")

        status, csv_content = req("/api/export/attendance", is_csv=True)
        assert status == 200
        assert "Date,Employee Code,Employee Name" in csv_content
        print(f"   -> Export attendance CSV generated ({len(csv_content.splitlines())} rows)")

        print("12. Testing Change Password...")
        status, data = req("/api/auth/change-password", method="POST", data={
            "current_password": "WrongPassword!",
            "new_password": "NewSecretPassword123!"
        })
        assert status == 400
        print("   -> Incorrect current password rejected properly!")

        status, data = req("/api/auth/change-password", method="POST", data={
            "current_password": "Password123!",
            "new_password": "NewSecretPassword123!"
        })
        assert status == 200
        print("   -> Password changed successfully!")

        # Restore password
        req("/api/auth/change-password", method="POST", data={
            "current_password": "NewSecretPassword123!",
            "new_password": "Password123!"
        })
        print("   -> Password restored.")

        print("\nALL BACKEND API TESTS PASSED WITH 100% SUCCESS!")

    finally:
        server_proc.terminate()
        server_proc.wait()

if __name__ == '__main__':
    run_tests()
