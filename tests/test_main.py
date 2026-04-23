import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

# ---------------------------------------------------------------------------
# Test database — SQLite in-memory
# ---------------------------------------------------------------------------

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

engine_test = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db

client = TestClient(app)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def setup_database():
    """Create tables before each test, drop them after."""
    Base.metadata.create_all(bind=engine_test)
    yield
    Base.metadata.drop_all(bind=engine_test)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_health():
    """GET /health should return 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "redis" in data


def test_shorten_url():
    """POST /shorten should create a short URL and return 201."""
    response = client.post("/shorten", json={"url": "https://www.google.com"})
    assert response.status_code == 201
    data = response.json()
    assert "short_url" in data
    assert "short_code" in data
    assert data["original_url"] == "https://www.google.com/"


def test_redirect():
    """GET /{short_code} should redirect (307) to the original URL."""
    # First, create a short URL
    create_resp = client.post("/shorten", json={"url": "https://www.github.com"})
    short_code = create_resp.json()["short_code"]

    # Then, follow the redirect
    response = client.get(f"/{short_code}", follow_redirects=False)
    assert response.status_code == 307
    assert "github.com" in response.headers["location"]


def test_stats():
    """GET /stats/{short_code} should return click statistics."""
    # Create a short URL
    create_resp = client.post("/shorten", json={"url": "https://www.example.com"})
    short_code = create_resp.json()["short_code"]

    # Click it once
    client.get(f"/{short_code}", follow_redirects=False)

    # Check stats
    stats_resp = client.get(f"/stats/{short_code}")
    assert stats_resp.status_code == 200
    data = stats_resp.json()
    assert data["clicks"] == 1
    assert data["short_code"] == short_code
    assert "example.com" in data["original_url"]


def test_invalid_short_code():
    """GET /{invalid_code} should return 404."""
    response = client.get("/nonexistent123")
    assert response.status_code == 404
    assert response.json()["detail"] == "Short URL not found"


def test_invalid_stats():
    """GET /stats/{invalid_code} should return 404."""
    response = client.get("/stats/nonexistent123")
    assert response.status_code == 404
