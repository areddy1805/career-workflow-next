import sys
import json
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)

endpoints = ["/api/dashboard", "/api/runtime", "/api/jobs", "/api/runs"]

success = True
for endpoint in endpoints:
    response = client.get(endpoint)
    if response.status_code == 200:
        try:
            data = response.json()
            print(f"SUCCESS: {endpoint} returned valid JSON.")
        except json.JSONDecodeError:
            print(f"FAILED: {endpoint} did not return JSON.")
            success = False
    else:
        print(f"FAILED: {endpoint} returned status {response.status_code}")
        print(response.text)
        success = False

sys.exit(0 if success else 1)
