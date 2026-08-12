from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_health_check() -> None:
    """
    Test that the GET /health endpoint returns the correct status and payload.
    """
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "packready-api"
    }
