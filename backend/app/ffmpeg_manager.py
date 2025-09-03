# backend/app/ffmpeg_manager.py
import logging
import subprocess
import signal
import threading
import time
from pathlib import Path
from typing import Dict
from .roles import resolve_role
from .config import LIVE_DIR, REC_DIR, settings

logger = logging.getLogger("homecam.ffmpeg")
if not logger.handlers:
    # Fallback basic config if the app hasn't configured logging yet
    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

def _spawn(cmd: list[str], log_path: Path) -> subprocess.Popen:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logf = open(log_path, "ab", buffering=0)
    logger.debug("FFmpeg cmd: %s", " ".join(str(x) for x in cmd))
    logger.info("FFmpeg stderr log: %s", log_path)
    return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=logf)

def _hls_low_options(seg_dur="2", list_size="12"):
    # common HLS opts for low branch (atomic segments, no-cache)
    return [
        "-f", "hls",
        "-hls_time", seg_dur,
        "-hls_list_size", list_size,
        "-hls_allow_cache", "0",
        "-hls_flags", "delete_segments+independent_segments+append_list+temp_file",
    ]

def _low_encoder_opts(low_crf: int, grid_w: int | None, grid_h: int | None):
    # Encoder opts for low branch. Scale only if an explicit grid target is provided.
    opts = [
        "-c:v", "libx264", "-preset", "veryfast", "-crf", str(low_crf),
        "-g", "48", "-sc_threshold", "0",
        "-maxrate", "1200k", "-bufsize", "1200k",
        "-an",
    ]
    if grid_w and grid_h and grid_w > 0 and grid_h > 0:
        opts = ["-vf", f"scale={grid_w}:{grid_h}",
                "-force_key_frames", f"expr:gte(t,n_forced*2)"] + opts
    else:
        opts = ["-force_key_frames", f"expr:gte(t,n_forced*2)"] + opts
    return opts    

class FFmpegManager:
    # store per-cam map of role->proc
    def __init__(self):
        self._procs: dict[int, dict[str, subprocess.Popen]] = {}

    def _ensure_dirs(self, cam_name: str) -> None:
        (LIVE_DIR / cam_name / "low").mkdir(parents=True, exist_ok=True)
        (LIVE_DIR / cam_name / "high").mkdir(parents=True, exist_ok=True)
        (REC_DIR / cam_name).mkdir(parents=True, exist_ok=True)

    # NEW: ensure date/hour dirs exist
    def _ensure_rec_date_hour(self, cam_name: str) -> None:
        now = time.localtime()
        date_dir = REC_DIR / cam_name / time.strftime("%Y-%m-%d", now)
        hour_dir = date_dir / time.strftime("%H", now)
        hour_dir.mkdir(parents=True, exist_ok=True)

    # NEW: small maintainer thread to survive hour rollovers
    def _maintain_rec_dirs(self, cam_id: int, cam_name: str):
        while True:
            p = self._procs.get(cam_id)
            if p is None or p.poll() is not None:
                return  # process ended
            now = time.localtime()
            date_dir = REC_DIR / cam_name / time.strftime("%Y-%m-%d", now)
            cur_hour = date_dir / time.strftime("%H", now)
            nxt_epoch = time.mktime(now) + 3600
            nxt = time.localtime(nxt_epoch)
            next_hour = (REC_DIR / cam_name / time.strftime("%Y-%m-%d", nxt)) / time.strftime("%H", nxt)
            cur_hour.mkdir(parents=True, exist_ok=True)
            next_hour.mkdir(parents=True, exist_ok=True)
            time.sleep(20)
        
    def stop_role(self, cam_id: int, role: str):
        procs_by_role = self._procs.get(cam_id) or {}
        p = procs_by_role.pop(role, None)
        if p:
            try:
                if p.poll() is None:
                    p.send_signal(signal.SIGTERM)
                    p.wait(timeout=5)
            except Exception:
                try:
                    if p.poll() is None:
                        p.kill()
                except Exception:
                    pass
        # clean up empty maps
        if cam_id in self._procs and not self._procs[cam_id]:
            self._procs.pop(cam_id, None)
    
    def stop_camera(self, cam_id: int):
        """Backward-compatible: stop ALL roles for this camera."""
        procs_by_role = self._procs.pop(cam_id, {}) or {}
        for role, p in list(procs_by_role.items()):
            try:
                if p and p.poll() is None:
                    p.send_signal(signal.SIGTERM)
                    p.wait(timeout=5)
            except Exception:
                try:
                    if p and p.poll() is None:
                        p.kill()
                except Exception:
                    pass
    
    def stop_all(self):
        """Stop everything for all cameras."""
        for cam_id in list(self._procs.keys()):
            self.stop_camera(cam_id)
    
    def status(self, cam_id: int) -> dict:
        """Report which roles are running."""
        procs_by_role = self._procs.get(cam_id) or {}
        roles = {r: (p is not None and p.poll() is None) for r, p in procs_by_role.items()}
        return {"running": any(roles.values()), "roles": roles}

    def start_role(self, cam_id:int, cam_name:str, role:str, src:str,
                   crf:int, scale_w:int|None=None, scale_h:int|None=None):
        """
        role in {"grid","medium","high"} → HLS; "recording" → segment mp4
        scale_* only applied for HLS roles (grid only in our resolver).
        """
        self.stop_role(cam_id, role)
        (LIVE_DIR / cam_name / role).mkdir(parents=True, exist_ok=True)

        if role == "recording":
            # MP4 segments
            rec_base = REC_DIR / cam_name
            self._ensure_rec_date_hour(cam_name)
            log = LIVE_DIR / cam_name / f"ffmpeg_{role}.log"
            cmd = [
                "ffmpeg","-y","-nostdin","-hide_banner","-loglevel","warning",
                "-rtsp_transport","tcp","-i", src, "-fflags","+genpts",
                "-map","0:v","-map","0:a?",
                "-c:v","libx264","-preset","veryfast","-crf",str(max(18,min(28,crf))),
                "-c:a","aac","-b:a","128k",
                "-f","segment",
                "-segment_time", str(settings.RECORDING_SEGMENT_SEC),
                "-reset_timestamps","1",
                "-strftime","1",
                str(rec_base / "%Y-%m-%d/%H/%Y-%m-%d_%H-%M-%S.mp4"),
            ]
            p = _spawn(cmd, log)
        else:
            # HLS roles
            out_dir = LIVE_DIR / cam_name / role
            log = LIVE_DIR / cam_name / f"ffmpeg_{role}.log"
            seg="2"
            enc = [
                "-c:v","libx264","-preset","veryfast","-crf",str(crf),
                "-g","48","-sc_threshold","0",
                "-force_key_frames", f"expr:gte(t,n_forced*{seg})",
                "-maxrate","4000k" if role!="grid" else "1200k",
                "-bufsize","4000k" if role!="grid" else "1200k",
            ]
            vf = []
            if scale_w and scale_h:  # only grid auto will pass these
                vf = ["-vf", f"scale={scale_w}:{scale_h}"]
            # audio only for medium/high
            audio = ["-an"] if role=="grid" else ["-c:a","aac","-ar","44100","-ac","1"]
            cmd = [
                "ffmpeg","-y","-nostdin","-hide_banner","-loglevel","warning",
                "-rtsp_transport","tcp","-i", src, "-fflags","+genpts",
                "-map","0:v", *vf, *enc, *audio,
                "-f","hls","-hls_time",seg,"-hls_list_size","12","-hls_allow_cache","0",
                "-hls_flags","delete_segments+independent_segments+append_list+temp_file",
                "-hls_segment_filename", str(out_dir/"segment_%06d.ts"),
                str(out_dir/"index.m3u8"),
            ]
            p = _spawn(cmd, log)

        self._procs.setdefault(cam_id, {})[role] = p

    def start_by_config(self, cam: "Camera"):
        # grid: always on
        src, sw, sh, run = resolve_role(cam, "grid")
        if run and src: self.start_role(cam.id, cam.name, "grid", src, cam.low_crf, sw, sh)
        # medium/high only on demand (endpoints below)
        # recording: governed by retention and mode; start/stop with retention changes


ffmpeg_manager = FFmpegManager()

