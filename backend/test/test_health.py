from fastapi.testclient import TestClient
from backend.main import app

# Create a test client that simulates a
# browser talking to our API
client = TestClient(app)

def test_health_check_api():
    # 1. Ping the /health endpoint
    response = client.get("/health")

    # 2. Check that the server responded
    # with a 200 OK status
    assert response.status_code == 200

    # 3. Check that the JSON response
    # says "healthy"
    data = response.json()
    assert data["status"] == "healthy"
    assert "dbConnected" in data