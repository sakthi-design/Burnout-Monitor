import json
import os
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

# Insert path to project root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.api_server import ThreadingHTTPServer, BurnoutRequestHandler
from backend.config import DB_PATH, ROOT
from backend.db import init_db, connect_db
from backend.auth import hash_password

PORT = 8081
BASE_URL = f"http://localhost:{PORT}"


def make_request(path, method="GET", body=None, token=None):
    url = f"{BASE_URL}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as res:
            return res.status, json.loads(res.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        try:
            return exc.code, json.loads(exc.read().decode("utf-8"))
        except Exception:
            return exc.code, {"error": exc.reason}
    except Exception as exc:
        return 500, {"error": str(exc)}


class ApiTests(unittest.TestCase):
    server = None
    server_thread = None

    @classmethod
    def setUpClass(cls):
        # Reset DB for tests
        if DB_PATH.exists():
            try:
                DB_PATH.unlink()
            except Exception:
                pass
        init_db()

        # Start API server in a background thread
        cls.server = ThreadingHTTPServer(("localhost", PORT), BurnoutRequestHandler)
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        # Give the server a moment to start
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        if cls.server:
            cls.server.shutdown()
            cls.server.server_close()
        # Wait for thread to terminate
        if cls.server_thread:
            cls.server_thread.join(timeout=1.0)
        # Clean up database
        if DB_PATH.exists():
            try:
                DB_PATH.unlink()
            except Exception:
                pass

    def setUp(self):
        # Clean/reset tables for each test
        with connect_db() as conn:
            conn.execute("DELETE FROM users WHERE email != 'admin@burnout.local'")
            conn.execute("DELETE FROM employees")
            conn.execute("DELETE FROM work_metrics")
            conn.execute("DELETE FROM feedback_entries")
            conn.execute("DELETE FROM burnout_predictions")
            conn.execute("DELETE FROM wellness_recommendations")
            conn.commit()

    def test_health_check(self):
        status, res = make_request("/api/health")
        self.assertEqual(status, 200)
        self.assertTrue(res["success"])
        self.assertEqual(res["service"], "burnout-api")

    def test_user_registration_and_strength_validation(self):
        # Valid user registration
        payload = {"email": "user@test.local", "password": "Password@123", "role": "user"}
        status, res = make_request("/api/register", "POST", payload)
        self.assertEqual(status, 201)
        self.assertTrue(res["success"])
        self.assertEqual(res["user"]["email"], "user@test.local")

        # Duplicate registration
        status, res = make_request("/api/register", "POST", payload)
        self.assertEqual(status, 409)

        # Invalid password strength (too short)
        payload_weak = {"email": "weak@test.local", "password": "weak", "role": "user"}
        status, res = make_request("/api/register", "POST", payload_weak)
        self.assertEqual(status, 409)
        self.assertIn("at least 8 characters", res["error"])

    def test_user_authentication_and_refresh_token(self):
        # Register a test admin
        reg_payload = {"email": "hr_admin@test.local", "password": "AdminPassword@123", "role": "admin"}
        make_request("/api/register", "POST", reg_payload)

        # Valid login
        login_payload = {"email": "hr_admin@test.local", "password": "AdminPassword@123"}
        status, res = make_request("/api/login", "POST", login_payload)
        self.assertEqual(status, 200)
        self.assertTrue(res["success"])
        self.assertIn("access_token", res)
        self.assertIn("refresh_token", res)

        access_token = res["access_token"]
        refresh_token = res["refresh_token"]

        # Token refresh flow
        refresh_payload = {"refresh_token": refresh_token}
        status, refresh_res = make_request("/api/auth/refresh", "POST", refresh_payload)
        self.assertEqual(status, 200)
        self.assertTrue(refresh_res["success"])
        self.assertIn("access_token", refresh_res)

        # Invalid login credentials
        bad_login = {"email": "hr_admin@test.local", "password": "WrongPassword"}
        status, res = make_request("/api/login", "POST", bad_login)
        self.assertEqual(status, 401)

    def test_role_based_access_control(self):
        # Register admin & user
        make_request("/api/register", "POST", {"email": "admin_user@test.local", "password": "AdminPassword@123", "role": "admin"})
        make_request("/api/register", "POST", {"email": "regular_user@test.local", "password": "UserPassword@123", "role": "user"})

        # Log in both
        _, admin_auth = make_request("/api/login", "POST", {"email": "admin_user@test.local", "password": "AdminPassword@123"})
        _, user_auth = make_request("/api/login", "POST", {"email": "regular_user@test.local", "password": "UserPassword@123"})

        admin_token = admin_auth["access_token"]
        user_token = user_auth["access_token"]

        # Admin creates employee -> success
        emp_payload = {
            "id": "EMP-001",
            "name": "John Doe",
            "department": "Engineering",
            "designation": "Backend Dev",
            "email": "john.doe@company.com",
            "age": 28,
            "experience": 4,
            "work_hours": 9.0,
            "overtime_hours": 1.5,
            "leave_days": 2,
            "meeting_hours": 6.5,
            "task_load": 75,
            "completion_rate": 80,
            "job_satisfaction": 60,
            "stress_level": 50,
            "feedback": "feeling fine"
        }
        status, res = make_request("/api/employees", "POST", emp_payload, token=admin_token)
        self.assertEqual(status, 201)

        # User attempts to create employee -> 403 Forbidden
        status, res = make_request("/api/employees", "POST", emp_payload, token=user_token)
        self.assertEqual(status, 403)
        self.assertIn("Forbidden", res["error"])

    def test_backend_validation_bounds(self):
        # Log in as admin
        make_request("/api/register", "POST", {"email": "admin_val@test.local", "password": "AdminPassword@123", "role": "admin"})
        _, admin_auth = make_request("/api/login", "POST", {"email": "admin_val@test.local", "password": "AdminPassword@123"})
        admin_token = admin_auth["access_token"]

        # Invalid field range (age > 65)
        bad_payload = {
            "id": "EMP-002",
            "name": "Jane Doe",
            "department": "Engineering",
            "designation": "Backend Dev",
            "email": "jane.doe@company.com",
            "age": 70, # Invalid
            "experience": 4,
            "work_hours": 8.0,
        }
        status, res = make_request("/api/employees", "POST", bad_payload, token=admin_token)
        self.assertEqual(status, 422)
        self.assertIn("age must be between", res["error"])

        # Invalid work metrics bounds (stress_level > 100)
        bad_metric_payload = {
            "id": "EMP-003",
            "name": "Jane Doe",
            "department": "Engineering",
            "designation": "Backend Dev",
            "email": "jane.doe@company.com",
            "age": 30,
            "experience": 4,
            "work_hours": 8.0,
            "stress_level": 150 # Invalid
        }
        status, res = make_request("/api/employees", "POST", bad_metric_payload, token=admin_token)
        self.assertEqual(status, 422)
        self.assertIn("stress_level must be between", res["error"])

    def test_employee_crud_and_persistence(self):
        # Log in as admin
        make_request("/api/register", "POST", {"email": "admin_crud@test.local", "password": "AdminPassword@123", "role": "admin"})
        _, admin_auth = make_request("/api/login", "POST", {"email": "admin_crud@test.local", "password": "AdminPassword@123"})
        admin_token = admin_auth["access_token"]

        # Create
        emp_payload = {
            "id": "EMP-005",
            "name": "Alice Smith",
            "department": "Design",
            "designation": "UI Designer",
            "email": "alice.smith@company.com",
            "age": 25,
            "experience": 2,
            "work_hours": 8.0,
            "overtime_hours": 0.5,
            "leave_days": 3,
            "meeting_hours": 4.0,
            "task_load": 60,
            "completion_rate": 90,
            "job_satisfaction": 80,
            "stress_level": 30,
            "feedback": "Loving the work"
        }
        status, res = make_request("/api/employees", "POST", emp_payload, token=admin_token)
        self.assertEqual(status, 201)

        # Read
        status, get_res = make_request("/api/employees", "GET", token=admin_token)
        self.assertEqual(status, 200)
        self.assertTrue(get_res["success"])
        employees = get_res["employees"]
        self.assertTrue(len(employees) >= 1)
        
        alice = next(e for e in employees if e["id"] == "EMP-005")
        self.assertEqual(alice["name"], "Alice Smith")
        self.assertEqual(alice["feedback"], "Loving the work")

        # Update Profile
        update_payload = {
            "id": "EMP-005",
            "name": "Alice Cooper",
            "department": "Design",
            "designation": "Lead Designer",
            "email": "alice.cooper@company.com",
            "age": 26,
            "experience": 3
        }
        status, update_res = make_request("/api/employees/update", "POST", update_payload, token=admin_token)
        self.assertEqual(status, 200)

        # Weekly Update
        weekly_payload = {
            "id": "EMP-005",
            "work_hours": 10.0,
            "overtime_hours": 3.0,
            "leave_days": 0,
            "meeting_hours": 12.0,
            "task_load": 85,
            "completion_rate": 70,
            "job_satisfaction": 40,
            "stress_level": 80,
            "feedback": "Getting stressed by late requests"
        }
        status, weekly_res = make_request("/api/employees/weekly-update", "POST", weekly_payload, token=admin_token)
        self.assertEqual(status, 200)
        self.assertTrue(weekly_res["success"])
        self.assertIn("prediction", weekly_res)

        # Verify updates persist and reflect in load
        status, reload_res = make_request("/api/employees", "GET", token=admin_token)
        reloaded_alice = next(e for e in reload_res["employees"] if e["id"] == "EMP-005")
        self.assertEqual(reloaded_alice["name"], "Alice Cooper")
        self.assertEqual(reloaded_alice["work_hours"], 10.0)
        self.assertEqual(reloaded_alice["feedback"], "Getting stressed by late requests")

    def test_sql_injection_parameterization(self):
        # Log in as admin
        make_request("/api/register", "POST", {"email": "admin_sec@test.local", "password": "AdminPassword@123", "role": "admin"})
        _, admin_auth = make_request("/api/login", "POST", {"email": "admin_sec@test.local", "password": "AdminPassword@123"})
        admin_token = admin_auth["access_token"]

        # Payload attempting SQL injection in ID field
        injection_payload = {
            "id": "EMP-999' OR '1'='1",
            "name": "Hacker",
            "department": "Engineering",
            "designation": "Hacker",
            "email": "hacker@company.com",
            "age": 30,
            "experience": 5
        }
        status, res = make_request("/api/employees", "POST", injection_payload, token=admin_token)
        self.assertEqual(status, 201) # Handled safely as a literal string ID

        # Verify employee is loaded with exact injected ID string literal
        status, get_res = make_request("/api/employees", "GET", token=admin_token)
        employees = get_res["employees"]
        hacker = next(e for e in employees if e["id"] == "EMP-999' OR '1'='1")
        self.assertIsNotNone(hacker)

    def test_machine_learning_prediction_and_metrics_api(self):
        # Log in
        make_request("/api/register", "POST", {"email": "admin_ml@test.local", "password": "AdminPassword@123", "role": "admin"})
        _, admin_auth = make_request("/api/login", "POST", {"email": "admin_ml@test.local", "password": "AdminPassword@123"})
        admin_token = admin_auth["access_token"]

        # Make prediction request
        predict_payload = {
            "work_hours": 10.0,
            "overtime_hours": 3.0,
            "leave_days": 0,
            "meeting_hours": 12.0,
            "task_load": 85,
            "completion_rate": 70,
            "job_satisfaction": 40,
            "stress_level": 80,
            "feedback": "I am feeling extremely overwhelmed and exhausted."
        }
        status, res = make_request("/api/predict", "POST", predict_payload, token=admin_token)
        self.assertEqual(status, 200)
        self.assertTrue(res["success"])
        self.assertIn("score", res["prediction"])
        self.assertIn("risk", res["prediction"])
        self.assertIn("top_driver", res["prediction"])

        # Fetch model metrics
        status, metrics_res = make_request("/api/model/metrics", "GET", token=admin_token)
        self.assertEqual(status, 200)
        self.assertTrue(metrics_res["success"])
        self.assertIn("accuracy", metrics_res["metrics"])
        self.assertIn("feature_importances", metrics_res["metrics"])


if __name__ == "__main__":
    unittest.main()
