# backend/app/ffmpeg_manager.py
import logging
import shutil
import signal
import subprocess
import threading
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from .roles import resolve_role

from .config import LIVE_DIR, REC_DIR, settings

logger = logging.getLogger("homecam.ffmpeg")
if not logger.handlers:
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )

# ----------------------------- helpers -----------------------------

def _alive(p: Optional[subprocess.Popen]) -> bool:
    return p is not None and p.poll() is None

def _spawn(cmd: list[str], log_path: Path) -> subprocess.Popen:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logf = open(log_path, "ab", buffering=0)
    logger.debug("FFmpeg cmd: %s", " ".join(str(x) for x in cmd))
    logger.info("FFmpeg stderr log: %s", log_path)
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=logf)

def _hls_opts(seg_dur="2", list_size="12"):
    return [
        "-f", "hls",
        "-hls_time", seg_dur,
        "-hls_list_size", list_size,
        "-hls_allow_cache", "0",
        "-hls_flags", "delete_segments+independent_segments+append_list+temp_file",
    ]


# ----------------------------- Lease Tracker -----------------------------

class LeaseTracker:
    """
    Tracks 'leases' per (cam_id, role) to decide when a role is in-use.
    - acquire() -> lease_id
    - renew()   -> bump last-seen
    - release() -> drop; when no leases remain, we remember the 'idle_since' time
    Also exposes counts and last_seen/idle_since for reaper logic.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._leases: Dict[Tuple[int, str], Dict[str, float]] = {}
        self._idle_since: Dict[Tuple[int, str], float] = {}
        self._last_seen: Dict[Tuple[int, str], float] = {}
        self._ttl = getattr(settings, "LEASE_TIMEOUT_SEC", 60)

    def acquire(self, cam_id: int, role: str) -> str:
        import uuid
        lid = uuid.uuid4().hex
        now = time.time()
        with self._lock:
            self._leases.setdefault((cam_id, role), {})[lid] = now
            self._last_seen[(cam_id, role)] = now
            # while leased, clear idle_since
            self._idle_since.pop((cam_id, role), None)
        return lid

    def renew(self, cam_id: int, role: str, lease_id: str) -> bool:
        now = time.time()
        success = False
        with self._lock:
            leases = self._leases.get((cam_id, role))
            if leases and lease_id in leases:
                leases[lease_id] = now
                self._last_seen[(cam_id, role)] = now
                success = True
        logger.info("lease renew cam_id %s role %s leases %s", cam_id, role, str(leases))
        return success
        
    def release(self, cam_id: int, role: str, lease_id: str):
        with self._lock:
            leases = self._leases.get((cam_id, role))
            if leases and leases.pop(lease_id, None) is not None:
                if not leases:
                    # became idle now
                    self._idle_since[(cam_id, role)] = time.time()

    def _prune_expired(self, key: Tuple[int, str]):
        leases = self._leases.get(key)
        if not leases:
            return
        now = time.time()
        expired = [lid for lid, ts in leases.items() if now - ts > self._ttl]
        for lid in expired:
            leases.pop(lid, None)
        if expired:
            if leases:
                self._last_seen[key] = max(leases.values())
            else:
                self._idle_since[key] = now

    def snap_count(self, cam_id: int, role: str) -> int:
        key = (cam_id, role)
        with self._lock:
            self._prune_expired(key)
            return len(self._leases.get(key, {}))

    def count(self, cam_id: int, role: str) -> int:
        return self.snap_count(cam_id, role)

    def mark_activity(self, cam_id: int, role: str):
        """Record activity (e.g., on start); clears idle timer while active."""
        now = time.time()
        with self._lock:
            self._last_seen[(cam_id, role)] = now
            # clear any prior idle time so reaper doesn't stop immediately
            self._idle_since.pop((cam_id, role), None)

    def idle_for(self, cam_id: int, role: str) -> float:
        """Seconds since idle (no leases). 0 if not idle."""
        with self._lock:
            t = self._idle_since.get((cam_id, role))
            return time.time() - t if t else 0.0

    def snapshot_counts(self, cam_id: int) -> Dict[str, int]:
        with self._lock:
            out: Dict[str, int] = {}
            for r in ("grid", "medium", "high", "recording"):
                key = (cam_id, r)
                self._prune_expired(key)
                out[r] = len(self._leases.get(key, {}))
            return out


# ----------------------------- Manager -----------------------------

class FFmpegManager:
    """
    Role-based process manager:
      - Roles: grid (HLS), medium (HLS), high (HLS), recording (MP4 segments)
      - One ffmpeg per (cam_id, role) max; start is idempotent & race-safe
      - Leases for medium/high auto-stop when idle > timeout
      - Cleans HLS files on stop
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._procs: Dict[int, Dict[str, subprocess.Popen]] = {}
        self._inflight: set[Tuple[int, str]] = set()
        self._cam_names: Dict[int, str] = {}  # cam_id -> cam_name
        self._leases = LeaseTracker()
        self._configs: Dict[int, Dict[str, dict]] = {}
        self._shutting_down = False

        threading.Thread(target=self._idle_reaper, daemon=True).start()

    # ---------- public: leases ----------

    def acquire_lease(self, cam_id: int, role: str) -> str:
        return self._leases.acquire(cam_id, role)

    def renew_lease(self, cam_id: int, role: str, lease_id: str) -> bool:
        return self._leases.renew(cam_id, role, lease_id)

    def release_lease(self, cam_id: int, role: str, lease_id: str):
        self._leases.release(cam_id, role, lease_id)

    # ---------- start/stop/status ----------

    def start_role(
        self,
        cam_id: int,
        cam_name: str,
        role: str,
        src: str,
        crf: int,
        scale_w: Optional[int] = None,
        scale_h: Optional[int] = None,
    ):
        """
        Safe, idempotent start. Only one ffmpeg per (cam_id, role).
        """
        key = (cam_id, role)

        # CS1
        with self._lock:
            if key in self._inflight:
                return {"ok": False, "reason": "start_in_progress"}

            self._inflight.add(key)
            self._procs.setdefault(cam_id, {})
            self._cam_names[cam_id] = cam_name  # keep the mapping up-to-date

            existing = self._procs[cam_id].get(role)
            if _alive(existing):
                self._inflight.discard(key)
                return {"ok": True, "already_running": True}

            if existing and not _alive(existing):
                self._procs[cam_id].pop(role, None)

        # build/spawn outside lock
        try:
            if role == "recording":
                new_proc = self._start_recording_proc(cam_name, src, crf)
            else:
                new_proc = self._start_hls_proc(cam_name, role, src, crf, scale_w, scale_h)
        except Exception:
            with self._lock:
                self._inflight.discard(key)
            raise

        # CS2
        with self._lock:
            existing_now = self._procs.get(cam_id, {}).get(role)
            if _alive(existing_now):
                # someone else beat us; kill ours
                try:
                    if _alive(new_proc):
                        new_proc.send_signal(signal.SIGTERM); new_proc.wait(timeout=5)
                except Exception:
                    try:
                        if _alive(new_proc): new_proc.kill()
                    except Exception:
                        pass
                self._inflight.discard(key)
                return {"ok": True, "already_running": True}

            self._procs[cam_id][role] = new_proc
            self._inflight.discard(key)
            # mark role active so reaper doesn't stop immediately
            self._leases.mark_activity(cam_id, role)
            self._configs.setdefault(cam_id, {})[role] = {
                "cam_name": cam_name,
                "src": src,
                "crf": crf,
                "scale_w": scale_w,
                "scale_h": scale_h,
            }
            threading.Thread(
                target=self._wait_and_restart,
                args=(cam_id, role, new_proc),
                daemon=True,
            ).start()
            logger.info("Started cam_id=%s role=%s", cam_id, role)
            return {"ok": True}

    def stop_role(self, cam_id: int, cam_name: str, role: str):
        with self._lock:
            p = (self._procs.get(cam_id) or {}).pop(role, None)
            cfgs = self._configs.get(cam_id)
            if cfgs:
                cfgs.pop(role, None)
                if not cfgs:
                    self._configs.pop(cam_id, None)
        if p:
            try:
                if _alive(p):
                    p.send_signal(signal.SIGTERM)
                    p.wait(timeout=5)
            except Exception:
                try:
                    if _alive(p): p.kill()
                except Exception:
                    pass
        # cleanup files
        self._cleanup_live_role(cam_name, role)
        logger.info("Stopped cam_id=%s role=%s", cam_id, role)

    def stop_camera(self, cam_id: int, cam_name: str):
        with self._lock:
            procs_by_role = self._procs.pop(cam_id, {}) or {}
            self._cam_names.pop(cam_id, None)
            self._configs.pop(cam_id, None)
        for role, p in procs_by_role.items():
            try:
                if _alive(p):
                    p.send_signal(signal.SIGTERM)
                    p.wait(timeout=5)
            except Exception:
                try:
                    if _alive(p): p.kill()
                except Exception:
                    pass
        self._cleanup_live_all(cam_name)
        logger.info("Stopped camera %s cam_id=%s", cam_name, cam_id)

    def shutdown(self):
        """Stop all running ffmpeg processes without triggering restarts."""
        logger.info("FFmpegManager shutdown initiated")
        self._shutting_down = True
        with self._lock:
            cam_ids = list(self._procs.keys())
        for cam_id in cam_ids:
            cam_name = self._cam_names.get(cam_id) or str(cam_id)
            self.stop_camera(cam_id, cam_name)

    def status(self, cam_id: int) -> dict:
        with self._lock:
            procs_by_role = self._procs.get(cam_id) or {}
            roles = {r: _alive(p) for r, p in procs_by_role.items()}
        lease_counts = self._leases.snapshot_counts(cam_id)
        return {"running": any(roles.values()), "roles": roles, "leases": lease_counts}
        
    # ---------- spawn routines (no registry writes here) ----------

    def _start_hls_proc(
        self,
        cam_name: str,
        role: str,
        src: str,
        crf: int,
        scale_w: Optional[int],
        scale_h: Optional[int],
    ) -> subprocess.Popen:
        (LIVE_DIR / cam_name / role).mkdir(parents=True, exist_ok=True)
        out_dir = LIVE_DIR / cam_name / role
        log = LIVE_DIR / cam_name / f"ffmpeg_{role}.log"
        seg = "2"

        enc = [
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(crf),
            "-g", "48", "-sc_threshold", "0",
            "-force_key_frames", f"expr:gte(t,n_forced*{seg})",
            "-maxrate", "4000k" if role != "grid" else "1200k",
            "-bufsize", "4000k" if role != "grid" else "1200k",
        ]
        vf = []
        if scale_w and scale_h:
            vf = ["-vf", f"scale={scale_w}:{scale_h}"]  # only used for grid/auto

        mapping = ["-map", "0:v"]
        audio = ["-an"]
        if role != "grid":
            mapping += ["-map", "0:a?"]
            audio = ["-c:a", "aac", "-ar", "44100", "-ac", "1"]

        cmd = [
            "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "warning",
            "-rtsp_transport", "tcp",
            "-i", src,
            "-fflags", "+genpts",
            *mapping,
            *vf, *enc, *audio,
            *_hls_opts(seg, "12"),
            "-hls_segment_filename", str(out_dir / "segment_%06d.ts"),
            str(out_dir / "index.m3u8"),
        ]
        return _spawn(cmd, log)

    def _start_recording_proc(self, cam_name: str, src: str, crf: int) -> subprocess.Popen:
        self._ensure_rec_date_hour(cam_name)
        rec_base = REC_DIR / cam_name
        log = LIVE_DIR / cam_name / f"ffmpeg_recording.log"
        cmd = [
            "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "warning",
            "-rtsp_transport", "tcp",
            "-i", src,
            "-fflags", "+genpts",
            "-map", "0:v", "-map", "0:a?",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(max(18, min(28, crf))),
            "-c:a", "aac", "-b:a", "128k",
            "-f", "segment",
            "-segment_time", str(settings.RECORDING_SEGMENT_SEC),
            "-reset_timestamps", "1",
            "-strftime", "1",
            str(rec_base / "%Y-%m-%d/%H/%Y-%m-%d_%H-%M-%S.mp4"),
        ]
        return _spawn(cmd, log)

    def start_by_config(self, cam):
        """
        Start roles that should always be on based on current config:
          - grid: always on (according to auto/manual selection & optional scaling)
          - recording: only if retention > 0 and role not disabled
        This method intentionally takes a 'resolver' callable (cam, role) -> (src, scale_w, scale_h, run)
        so ffmpeg_manager stays model-agnostic.
        """
        # Grid
        src, sw, sh, run = resolve_role(cam, "grid")
        if run and src:
            self.start_role(
                cam_id=cam.id,
                cam_name=cam.name,
                role="grid",
                src=src,
                crf=cam.low_crf,
                scale_w=sw, scale_h=sh,
            )
    
        # Recording (honor retention inside resolver)
        src, sw, sh, run = resolve_role(cam, "recording")
        if run and src:
            self.start_role(
                cam_id=cam.id,
                cam_name=cam.name,
                role="recording",
                src=src,
                crf=cam.high_crf,
                # no scaling for recording; sw/sh ignored
            )
        
    # ---------- filesystem helpers ----------

    def _ensure_rec_date_hour(self, cam_name: str):
        now = time.localtime()
        date_dir = REC_DIR / cam_name / time.strftime("%Y-%m-%d", now)
        hour_dir = date_dir / time.strftime("%H", now)
        hour_dir.mkdir(parents=True, exist_ok=True)

    def _cleanup_live_role(self, cam_name: str, role: str):
        try:
            d = LIVE_DIR / cam_name / role
            if d.exists():
                shutil.rmtree(d)
        except Exception:
            pass

    def _cleanup_live_all(self, cam_name: str):
        try:
            base = LIVE_DIR / cam_name
            if base.exists():
                shutil.rmtree(base)
        except Exception:
            pass

    # ---------- idle reaper ----------

    def _idle_reaper(self):
        interval = getattr(settings, "IDLE_REAPER_INTERVAL_SEC", 10)
        timeout = getattr(settings, "ROLE_IDLE_TIMEOUT_SEC", 120)
        logger.info("Idle reaper started: interval=%ss timeout=%ss", interval, timeout)
        while True:
            time.sleep(interval)
            try:
                # snapshot keys to avoid holding lock during stops
                with self._lock:
                    cam_ids = list(self._procs.keys())
                for cam_id in cam_ids:
                    cam_name = None
                    with self._lock:
                        roles_map = dict(self._procs.get(cam_id, {}))
                        cam_name = self._cam_names.get(cam_id)
                    for role in ("medium", "high"):
                        p = roles_map.get(role)
                        if not _alive(p):
                            # not running anyway; continue
                            continue
                        # if anyone is watching, keep it
                        lease_count = self._leases.snap_count(cam_id, role)
                        logger.info(
                            "Reaper keep cam_id=%s role=%s active_leases=%s",
                            cam_id,
                            role,
                            lease_count,
                        )
                        if lease_count > 0:
                            continue
                        # no leases: check idle duration
                        idle_s = self._leases.idle_for(cam_id, role)
                        logger.info(
                            "Reaper idle cam_id=%s role=%s idle=%ss", cam_id, role, int(idle_s)
                        )
                        if idle_s and idle_s > timeout:
                            logger.info(
                                "Auto-stopping cam_id=%s role=%s after idle %ss",
                                cam_id,
                                role,
                                int(idle_s),
                            )
                            # prefer full stop with cleanup if we have cam_name
                            if cam_name:
                                self.stop_role(cam_id, cam_name, role)
                            else:
                                # fallback: just stop the proc
                                self._stop_role_internal(cam_id, role)
            except Exception:
                logger.exception("Idle reaper error")

    def _wait_and_restart(self, cam_id: int, role: str, proc: subprocess.Popen):
        rc = proc.wait()
        with self._lock:
            current = (self._procs.get(cam_id) or {}).get(role)
            cfg = (self._configs.get(cam_id) or {}).get(role)
            lease_count = self._leases.snap_count(cam_id, role)
        cam_obj = None
        try:
            from .db import SessionLocal  # pylint: disable=import-outside-toplevel
            from .models import Camera  # pylint: disable=import-outside-toplevel
            with SessionLocal() as session:
                cam_obj = session.get(Camera, cam_id)
        except Exception:  # pragma: no cover - best effort
            cam_obj = None

        if cam_obj:
            try:
                src, sw, sh, run = resolve_role(cam_obj, role)
                if run and src:
                    cfg = {
                        "cam_name": cam_obj.name,
                        "src": src,
                        "crf": cam_obj.low_crf if role in {"grid", "medium"} else cam_obj.high_crf,
                        "scale_w": sw,
                        "scale_h": sh,
                    }
                else:
                    cfg = None
            except Exception:  # pragma: no cover - resolver errors shouldn't crash watcher
                cfg = cfg

        should_run = cfg is not None
        if role in {"medium", "high"}:
            should_run = should_run and lease_count > 0
        if self._shutting_down:
            should_run = False

        if not should_run:
            # Remove stale bookkeeping; thread exits without restart
            with self._lock:
                procs = self._procs.get(cam_id)
                if procs and procs.get(role) is proc:
                    procs.pop(role, None)
                    if not procs:
                        self._procs.pop(cam_id, None)
                cfgs = self._configs.get(cam_id)
                if cfgs:
                    cfgs.pop(role, None)
                    if not cfgs:
                        self._configs.pop(cam_id, None)
            return

        if current is proc:
            logger.warning(
                "FFmpeg process exited rc=%s; restarting cam_id=%s role=%s",
                rc,
                cam_id,
                role,
            )
            self.start_role(
                cam_id=cam_id,
                cam_name=cfg["cam_name"],
                role=role,
                src=cfg["src"],
                crf=cfg["crf"],
                scale_w=cfg.get("scale_w"),
                scale_h=cfg.get("scale_h"),
            )

    def _stop_role_internal(self, cam_id: int, role: str):
        with self._lock:
            p = (self._procs.get(cam_id) or {}).pop(role, None)
            cfgs = self._configs.get(cam_id)
            if cfgs:
                cfgs.pop(role, None)
                if not cfgs:
                    self._configs.pop(cam_id, None)
        if p:
            try:
                if _alive(p):
                    p.send_signal(signal.SIGTERM)
                    p.wait(timeout=5)
            except Exception:
                try:
                    if _alive(p): p.kill()
                except Exception:
                    pass
        # (no cleanup here; used only when cam_name is unknown)

ffmpeg_manager = FFmpegManager()
