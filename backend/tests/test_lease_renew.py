import sys
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append('backend')
from app.lease_static import LeaseRenewStaticFiles
from app.ffmpeg_manager import ffmpeg_manager


def test_lease_renew_on_medium_request(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    live_dir = media_root / "live" / "cam1" / "medium"
    live_dir.mkdir(parents=True)
    (live_dir / "index.m3u8").write_text("dummy")

    # prepare manager mapping
    ffmpeg_manager._cam_names[1] = "cam1"  # type: ignore[attr-defined]

    called = {}

    def fake_renew(cam_id, role, lease_id):
        called["args"] = (cam_id, role, lease_id)

    monkeypatch.setattr(ffmpeg_manager, "renew_lease", fake_renew)

    app = FastAPI()
    app.mount("/media", LeaseRenewStaticFiles(directory=str(media_root)), name="media")

    client = TestClient(app)
    resp = client.get("/media/live/cam1/medium/index.m3u8?lease=abc123")
    assert resp.status_code == 200
    assert called["args"] == (1, "medium", "abc123")
