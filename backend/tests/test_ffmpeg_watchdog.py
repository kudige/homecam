import os
import subprocess
import time
import sys
from pathlib import Path

DB_FILE = "/tmp/homecam_test.db"
Path(DB_FILE).unlink(missing_ok=True)
os.environ["DB_PATH"] = DB_FILE

sys.path.append('backend')
from app.ffmpeg_manager import FFmpegManager, _alive
from app.db import SessionLocal, engine
from app.models import Base, Camera


def test_process_auto_restart(monkeypatch):
    mgr = FFmpegManager()

    def fake_start_hls_proc(cam_name, role, src, crf, scale_w, scale_h):
        return subprocess.Popen(['sleep', '60'])

    mgr._start_hls_proc = fake_start_hls_proc

    mgr.start_role(cam_id=1, cam_name='cam1', role='grid', src='src', crf=23)

    with mgr._lock:
        proc1 = mgr._procs[1]['grid']
    assert _alive(proc1)

    proc1.kill()
    proc1.wait()

    for _ in range(50):  # wait up to 5s for restart
        time.sleep(0.1)
        with mgr._lock:
            proc2 = mgr._procs[1]['grid']
        if proc2 is not proc1 and _alive(proc2):
            break
    else:
        raise AssertionError("process was not restarted")

    mgr.stop_camera(1, 'cam1')


def test_no_restart_when_not_should_run(monkeypatch):
    mgr = FFmpegManager()

    def fake_start_hls_proc(cam_name, role, src, crf, scale_w, scale_h):
        return subprocess.Popen(['sleep', '60'])

    mgr._start_hls_proc = fake_start_hls_proc

    lease = mgr.acquire_lease(1, 'medium')
    mgr.start_role(cam_id=1, cam_name='cam1', role='medium', src='src', crf=23)

    with mgr._lock:
        proc1 = mgr._procs[1]['medium']
    assert _alive(proc1)

    mgr.release_lease(1, 'medium', lease)
    proc1.kill()
    proc1.wait()

    for _ in range(50):  # wait up to 5s for potential restart
        time.sleep(0.1)
        with mgr._lock:
            proc2 = (mgr._procs.get(1) or {}).get('medium')
        if proc2 is None:
            break
    else:
        raise AssertionError("process restarted despite no lease")

    mgr.stop_camera(1, 'cam1')


def test_no_restart_when_config_says_stop(monkeypatch):
    Base.metadata.create_all(engine)
    session = SessionLocal()
    cam = Camera(name='camdb', rtsp_url='src', retention_days=7)
    session.add(cam)
    session.commit()
    session.refresh(cam)

    mgr = FFmpegManager()

    def fake_start_recording_proc(cam_name, src, crf):
        return subprocess.Popen(['sleep', '60'])

    mgr._start_recording_proc = fake_start_recording_proc

    mgr.start_role(cam_id=cam.id, cam_name=cam.name, role='recording', src='src', crf=23)

    with mgr._lock:
        proc1 = mgr._procs[cam.id]['recording']
    assert _alive(proc1)

    cam.retention_days = 0
    session.add(cam)
    session.commit()
    cam_id = cam.id
    cam_name = cam.name
    session.close()

    proc1.kill()
    proc1.wait()

    for _ in range(50):  # wait up to 5s for potential restart
        time.sleep(0.1)
        with mgr._lock:
            proc2 = (mgr._procs.get(cam_id) or {}).get('recording')
        if proc2 is None:
            break
    else:
        raise AssertionError("process restarted despite disabled config")

    mgr.stop_camera(cam_id, cam_name)
