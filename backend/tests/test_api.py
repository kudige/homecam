import sys
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

@pytest.fixture
def client(tmp_path, monkeypatch):
    """TestClient that uses a temporary SQLite database."""
    monkeypatch.setenv("DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))
    sys.path.append(str(Path(__file__).resolve().parents[1]))
    if "app.db" in sys.modules:
        del sys.modules["app.db"]
    if "app.main" in sys.modules:
        del sys.modules["app.main"]
    from app.main import app
    from app.db import Base, engine
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c


def test_create_and_list_cameras(client):
    # initially empty
    r = client.get("/api/admin/cameras")
    assert r.status_code == 200
    assert r.json() == []

    payload = {"name": "Cam1", "rtsp_url": "rtsp://example.com/stream"}
    r = client.post("/api/admin/cameras", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["name"] == "Cam1"
    assert data["retention_days"] == 7

    r = client.get("/api/admin/cameras")
    assert r.status_code == 200
    cams = r.json()
    assert len(cams) == 1
    assert cams[0]["name"] == "Cam1"


def test_update_camera(client):
    payload = {"name": "Cam2", "rtsp_url": "rtsp://example.com/stream"}
    r = client.post("/api/admin/cameras", json=payload)
    cam_id = r.json()["id"]

    r = client.put(f"/api/admin/cameras/{cam_id}", json={"retention_days": 3})
    assert r.status_code == 200
    assert r.json()["retention_days"] == 3
