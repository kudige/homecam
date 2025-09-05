import importlib
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# Ensure repository root is on sys.path so "backend" can be imported
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))


@pytest.fixture()
def api_client(tmp_path, monkeypatch):
    # Use a temporary database file for tests
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))

    # Reload configuration and database modules so they pick up the new DB_PATH
    from backend.app import config, db, ffmpeg_manager, main
    importlib.reload(config)
    importlib.reload(db)
    importlib.reload(ffmpeg_manager)
    importlib.reload(main)

    # Stub out ffmpeg operations to avoid external processes during tests
    ffmpeg_manager.ffmpeg_manager.start_by_config = lambda cam: None
    ffmpeg_manager.ffmpeg_manager.stop_camera = lambda cam_id, name: None
    ffmpeg_manager.ffmpeg_manager.start_camera_dual = lambda *args, **kwargs: None
    ffmpeg_manager.ffmpeg_manager.start_role = lambda *args, **kwargs: None
    ffmpeg_manager.ffmpeg_manager.stop_role = lambda *args, **kwargs: None

    with TestClient(main.app) as client:
        yield client, config.DB_PATH


def test_camera_crud(api_client):
    client, db_path = api_client
    # Ensure tests are using the temporary database
    assert str(db_path).endswith("test.db")

    # Initially, no cameras
    resp = client.get("/api/admin/cameras")
    assert resp.status_code == 200
    assert resp.json() == []

    # Create a new camera
    payload = {"name": "TestCam", "rtsp_url": "rtsp://example"}
    resp = client.post("/api/admin/cameras", json=payload)
    assert resp.status_code == 200
    cam = resp.json()
    assert cam["name"] == "TestCam"
    cam_id = cam["id"]

    # Verify camera appears in list
    resp = client.get("/api/admin/cameras")
    assert resp.status_code == 200
    cams = resp.json()
    assert len(cams) == 1
    assert cams[0]["id"] == cam_id

    # Delete the camera
    resp = client.delete(f"/api/admin/cameras/{cam_id}")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True

    # List should be empty again
    resp = client.get("/api/admin/cameras")
    assert resp.status_code == 200
    assert resp.json() == []
