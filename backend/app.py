print("DEBUG: Starting app.py", flush=True)

import http.server
import socketserver
import json
import sqlite3
import os
import uuid
import urllib.parse
from datetime import datetime, timedelta, date
try:
    from database import get_db_connection, verify_password, hash_password, init_db
except Exception as e:
    print(f"DEBUG: Import error: {e}", flush=True)
    raise

PORT = 8000
STATIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'frontend'))

print(f"DEBUG: STATIC_DIR = {STATIC_DIR}", flush=True)

# Ensure database initialized
try:
    init_db()
    print("DEBUG: init_db completed", flush=True)
except Exception as e:
    print(f"DEBUG: init_db error: {e}", flush=True)
    raise

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