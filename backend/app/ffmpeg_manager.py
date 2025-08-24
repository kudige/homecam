# backend/app/ffmpeg_manager.py
import subprocess
import signal
from pathlib import Path
from typing import Dict

from .config import LIVE_DIR, REC_DIR, settings


class FFmpegManager:
    """
    One ffmpeg process per camera, fanning out to:
      - low-res live HLS (video-only)
      - high-res live HLS (audio+video)
      - rolling MP4 recordings (5-min segments by default)
    """

    def __init__(self):
        # cam_id -> subprocess.Popen
        self._procs: Dict[int, subprocess.Popen] = {}

    def _ensure_dirs(self, cam_name: str) -> None:
        (LIVE_DIR / cam_name / "low").mkdir(parents=True, exist_ok=True)
        (LIVE_DIR / cam_name / "high").mkdir(parents=True, exist_ok=True)
        (REC_DIR / cam_name).mkdir(parents=True, exist_ok=True)

    def start_camera(
        self,
        cam_id: int,
        cam_name: str,
        rtsp_url: str,
        low_w: int,
        low_h: int,
        low_crf: int,
        high_crf: int,
    ) -> None:
        # If already running, do nothing
        if cam_id in self._procs and self._procs[cam_id].poll() is None:
            return

        self._ensure_dirs(cam_name)

        low_dir = LIVE_DIR / cam_name / "low"
        high_dir = LIVE_DIR / cam_name / "high"
        rec_base = REC_DIR / cam_name

        SEG_DUR = "2"  # seconds

        # Build a single ffmpeg command with multiple outputs.
        # NOTE: Per-output options must appear immediately before the output URL.
        cmd = [
            "ffmpeg",
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "warning",

            # Input (RTSP over TCP)
            "-rtsp_transport", "tcp",
            # Optional timeouts (commented; enable if desired)
            # "-stimeout", "5000000",   # 5s connect timeout (microseconds)
            # "-rw_timeout", "5000000", # 5s read timeout (microseconds)
            "-i", rtsp_url,

            # ----------------- LOW RES LIVE (video-only, HLS) -----------------
            "-map", "0:v",
            "-vf", f"scale={low_w}:{low_h}",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", str(low_crf),
            "-g", "48",
            "-sc_threshold", "0",
            "-force_key_frames", f"expr:gte(t,n_forced*{SEG_DUR})",
            "-maxrate", "1200k",
            "-bufsize", "1200k",
            "-an",  # no audio on grid tiles
            "-f", "hls",
            "-hls_time", SEG_DUR,
            "-hls_list_size", "6",
            "-hls_flags",
            "delete_segments+independent_segments+split_by_time+append_list+temp_file",
            "-hls_segment_filename", str(low_dir / "segment_%06d.ts"),
            str(low_dir / "index.m3u8"),

            # ----------------- HIGH RES LIVE (av, HLS) -----------------
            "-map", "0:v",
            "-map", "0:a?",  # audio optional
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", str(high_crf),
            "-g", "48",
            "-sc_threshold", "0",
            "-force_key_frames", f"expr:gte(t,n_forced*{SEG_DUR})",
            "-maxrate", "4000k",
            "-bufsize", "4000k",
            "-c:a", "aac",
            "-ar", "44100",
            "-ac", "1",
            "-f", "hls",
            "-hls_time", SEG_DUR,
            "-hls_list_size", "6",
            "-hls_flags",
            "delete_segments+independent_segments+split_by_time+append_list+temp_file",
            "-hls_segment_filename", str(high_dir / "segment_%06d.ts"),
            str(high_dir / "index.m3u8"),

            # ----------------- RECORDINGS (MP4 segments) -----------------
            "-map", "0",
            "-c:v", "libx264",
            "-preset", "veryfast",
            "-crf", str(max(18, min(28, high_crf))),
            "-c:a", "aac",
            "-b:a", "128k",
            "-f", "segment",
            "-segment_time", str(settings.RECORDING_SEGMENT_SEC),
            "-reset_timestamps", "1",
            "-strftime", "1",
            str(rec_base / "%Y-%m-%d/%H/%Y-%m-%d_%H-%M-%S.mp4"),
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.STDOUT,
        )
        self._procs[cam_id] = proc

    def stop_camera(self, cam_id: int) -> None:
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
