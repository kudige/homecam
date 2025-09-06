import sys
from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.append('backend')
from app.lease_static import LeaseRenewStaticFiles
from app.ffmpeg_manager import ffmpeg_manager


def test_auto_acquire_and_renew(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    live_dir = media_root / "live" / "cam1" / "medium"
    live_dir.mkdir(parents=True)
    (live_dir / "index.m3u8").write_text("dummy")

    # prepare manager mapping
    ffmpeg_manager._cam_names[1] = "cam1"  # type: ignore[attr-defined]

    calls = {"acquire": [], "renew": []}

    def fake_acquire(cam_id, role):
        calls["acquire"].append((cam_id, role))
        return "lease123"

    def fake_renew(cam_id, role, lease_id):
        calls["renew"].append((cam_id, role, lease_id))
        return True

    monkeypatch.setattr(ffmpeg_manager, "acquire_lease", fake_acquire)
    monkeypatch.setattr(ffmpeg_manager, "renew_lease", fake_renew)

    app = FastAPI()
    app.mount("/media", LeaseRenewStaticFiles(directory=str(media_root)), name="media")

    client = TestClient(app)
    resp1 = client.get("/media/live/cam1/medium/index.m3u8")
    assert resp1.status_code == 200
    assert calls["acquire"] == [(1, "medium")]
    assert calls["renew"] == []

    resp2 = client.get("/media/live/cam1/medium/index.m3u8")
    assert resp2.status_code == 200
    assert calls["acquire"] == [(1, "medium")]
    assert calls["renew"] == [(1, "medium", "lease123")]


def test_reacquire_after_expired_lease(tmp_path, monkeypatch):
    media_root = tmp_path / "media"
    live_dir = media_root / "live" / "cam1" / "medium"
    live_dir.mkdir(parents=True)
    (live_dir / "index.m3u8").write_text("dummy")

    ffmpeg_manager._cam_names[1] = "cam1"  # type: ignore[attr-defined]

    acquire_calls = []
    renew_calls = []

    acquire_ids = iter(["lease1", "lease2"])

    def fake_acquire(cam_id, role):
        lid = next(acquire_ids)
        acquire_calls.append((cam_id, role, lid))
        return lid

    renew_results = iter([False, True])

    def fake_renew(cam_id, role, lease_id):
        renew_calls.append((cam_id, role, lease_id))
        return next(renew_results)

    monkeypatch.setattr(ffmpeg_manager, "acquire_lease", fake_acquire)
    monkeypatch.setattr(ffmpeg_manager, "renew_lease", fake_renew)

    app = FastAPI()
    app.mount("/media", LeaseRenewStaticFiles(directory=str(media_root)), name="media")

    client = TestClient(app)
    client.get("/media/live/cam1/medium/index.m3u8")
    client.get("/media/live/cam1/medium/index.m3u8")
    client.get("/media/live/cam1/medium/index.m3u8")

    assert acquire_calls == [(1, "medium", "lease1"), (1, "medium", "lease2")]
    assert renew_calls == [
        (1, "medium", "lease1"),
        (1, "medium", "lease2"),
    ]
