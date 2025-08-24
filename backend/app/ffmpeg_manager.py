import subprocess, threading, time, os, signal
from pathlib import Path
from typing import Dict, Optional

from .config import LIVE_DIR, REC_DIR, settings

class FFmpegManager:
    """
    Single ffmpeg process per camera that fans out to:
      - low-res live HLS (video-only)
      - high-res live HLS (av)
      - rolling MP4 recordings (5-min segments)
    """

    def __init__(self):
        # cam_id -> subprocess
        self._procs: Dict[int, subprocess.Popen] = {}

    def _ensure_dirs(self, cam_name: str):
        (LIVE_DIR / cam_name / "low").mkdir(parents=True, exist_ok=True)
        (LIVE_DIR / cam_name / "high").mkdir(parents=True, exist_ok=True)
        # Recordings live under REC_DIR/<cam>/YYYY-MM-DD (strftime will create per-day/hour files)
        (REC_DIR / cam_name).mkdir(parents=True, exist_ok=True)

    def start_camera(self, cam_id: int, cam_name: str, rtsp_url: str, low_w: int, low_h: int, low_crf: int, high_crf: int):
        if cam_id in self._procs and self._procs[cam_id].poll() is None:
            return  # already running

        self._ensure_dirs(cam_name)

        low_dir = LIVE_DIR / cam_name / "low"
        high_dir = LIVE_DIR / cam_name / "high"
        rec_base = REC_DIR / cam_name

        # Build a SINGLE ffmpeg with multiple outputs (no tee needed)
        # Input options
        cmd = [
            "ffmpeg", "-nostdin",
            "-rtsp_transport", "tcp",
            # keep timeouts modest, but you can remove if you prefer
            # "-stimeout", "5000000",  # 5s input connect timeout (µs) — optional
            "-i", rtsp_url,
        ]

        # ---- LOW RES LIVE HLS (video only) ----
        cmd += [
            "-map", "0:v",
            "-vf", f"scale={low_w}:{low_h}",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(low_crf),
            "-g", "48", "-sc_threshold", "0",
            "-an",
            "-f", "hls",
            "-hls_time", "2", "-hls_list_size", "60",
            "-hls_flags", "delete_segments+program_date_time+independent_segments",
            "-hls_segment_filename", str(low_dir / "segment_%06d.ts"),
            str(low_dir / "index.m3u8"),
        ]

        # ---- HIGH RES LIVE HLS (audio + video) ----
        cmd += [
            "-map", "0:v",
            "-map", "0:a?",  # make audio optional
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(high_crf),
            "-c:a", "aac", "-ar", "44100", "-ac", "1",
            "-g", "48", "-sc_threshold", "0",
            "-f", "hls",
            "-hls_time", "2", "-hls_list_size", "60",
            "-hls_flags", "delete_segments+program_date_time+independent_segments",
            "-hls_segment_filename", str(high_dir / "segment_%06d.ts"),
            str(high_dir / "index.m3u8"),
        ]

        # ---- RECORDINGS: MP4 segments (5 min) ----
        # Use strftime to partition by day/hour automatically, no manual rotation needed
        cmd += [
            "-map", "0",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", str(max(18, min(28, high_crf))),
            "-c:a", "aac", "-b:a", "128k",
            "-f", "segment",
            "-segment_time", str(settings.RECORDING_SEGMENT_SEC),
            "-reset_timestamps", "1",
            "-strftime", "1",
            str(rec_base / "%Y-%m-%d/%H/%Y-%m-%d_%H-%M-%S.mp4"),
        ]

        # Launch single process
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        self._procs[cam_id] = proc

    def stop_camera(self, cam_id: int):
        p = self._procs.pop(cam_id, None)
        if not p:
            return
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

    def status(self, cam_id: int) -> dict:
        p = self._procs.get(cam_id)
        return {"running": p is not None and p.poll() is None}

ffmpeg_manager = FFmpegManager()
