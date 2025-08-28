# backend/app/ffmpeg_manager.py
import logging
import subprocess
import signal
import threading
import time
from pathlib import Path
from typing import Dict

from .config import LIVE_DIR, REC_DIR, settings

logger = logging.getLogger("homecam.ffmpeg")
if not logger.handlers:
    # Fallback basic config if the app hasn't configured logging yet
    logging.basicConfig(level=getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO),
                        format="%(asctime)s %(levelname)s [%(name)s] %(message)s")


class FFmpegManager:
    """
    One ffmpeg process per camera, fanning out to:
      - low-res live HLS (video-only)
      - high-res live HLS (audio+video)
      - rolling MP4 recordings (5-min segments by default)

    Uses filter_complex to split the decoded video into low/high branches.
    Also runs a small maintainer thread to ensure date/hour recording dirs exist.
    """

    def __init__(self):
        # cam_id -> subprocess.Popen
        self._procs: Dict[int, subprocess.Popen] = {}

    def _ensure_live_dirs(self, cam_name: str) -> None:
        (LIVE_DIR / cam_name / "low").mkdir(parents=True, exist_ok=True)
        (LIVE_DIR / cam_name / "high").mkdir(parents=True, exist_ok=True)

    def _ensure_rec_date_hour(self, cam_name: str) -> None:
        now = time.localtime()
        date_dir = REC_DIR / cam_name / time.strftime("%Y-%m-%d", now)
        hour_dir = date_dir / time.strftime("%H", now)
        if not hour_dir.exists():
            hour_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Created recording dir: %s", hour_dir)
        else:
            logger.debug("Recording dir exists: %s", hour_dir)

    def _maintain_rec_dirs(self, cam_id: int, cam_name: str, interval_sec: int = 20):
        logger.info("Maintainer thread started for cam_id=%s cam_name=%s", cam_id, cam_name)
        while True:
            p = self._procs.get(cam_id)
            if p is None:
                logger.info("Maintainer exiting (no process) cam_id=%s", cam_id)
                return
            if p.poll() is not None:
                logger.info("Maintainer exiting (process ended) cam_id=%s return=%s", cam_id, p.returncode)
                return

            try:
                now = time.localtime()
                cur_date = time.strftime("%Y-%m-%d", now)
                cur_hour = time.strftime("%H", now)
                cur_dir = REC_DIR / cam_name / cur_date / cur_hour

                nxt_epoch = time.mktime(now) + 3600
                nxt = time.localtime(nxt_epoch)
                nxt_date = time.strftime("%Y-%m-%d", nxt)
                nxt_hour = time.strftime("%H", nxt)
                next_dir = REC_DIR / cam_name / nxt_date / nxt_hour

                # Ensure both current and next hour exist
                for d in (cur_dir, next_dir):
                    if not d.exists():
                        d.mkdir(parents=True, exist_ok=True)
                        logger.info("Maintainer created: %s", d)
                    else:
                        logger.debug("Maintainer checked (exists): %s", d)
            except Exception as e:
                logger.exception("Maintainer error cam_id=%s: %s", cam_id, e)

            time.sleep(interval_sec)

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
        if cam_id in self._procs and self._procs[cam_id].poll() is None:
            logger.info("start_camera: already running cam_id=%s cam_name=%s", cam_id, cam_name)
            return

        mode = (settings.STREAM_MODE or "all").lower()
        logger.info("Starting camera %s (id=%s) with STREAM_MODE=%s", cam_name, cam_id, mode)
        SEG_DUR = "2"


        self._ensure_live_dirs(cam_name)
        # Only prepare recordings dirs when we actually produce recordings
        prepare_recordings = (mode == "all")

        low_dir = LIVE_DIR / cam_name / "low"
        high_dir = LIVE_DIR / cam_name / "high"
        rec_base = REC_DIR / cam_name
        log_path = LIVE_DIR / cam_name / "ffmpeg.log"
        SEG_DUR = "2"

        # Low-only mode: only ensure low dir; in all-mode, we’ll ensure rec dirs too
        if prepare_recordings:
            self._ensure_rec_date_hour(cam_name)

        cmd = [
            "ffmpeg", "-y", "-nostdin", "-hide_banner", "-loglevel", "warning",
            "-rtsp_transport", "tcp",
            "-i", rtsp_url,
            "-fflags", "+genpts",
        ]

        if mode == "all":
            # Two branches: high (vhi) and low (vlow)
            filter_graph = f"[0:v]split=2[vhi][vtmp];[vtmp]scale={low_w}:{low_h}[vlow]"
            cmd += ["-filter_complex", filter_graph]

            # ---- LOW (always) ----
            cmd += [
                "-map","[vlow]",
                "-c:v","libx264","-preset","veryfast","-crf",str(low_crf),
                "-g","48","-sc_threshold","0",
                "-force_key_frames", f"expr:gte(t,n_forced*{SEG_DUR})",
                "-maxrate","1200k","-bufsize","1200k",
                "-an",
                "-f","hls",
                "-hls_time", SEG_DUR,
                "-hls_list_size","12",
                "-hls_allow_cache","0",
                "-hls_flags","delete_segments+independent_segments+append_list+temp_file",
                "-hls_segment_filename", str(low_dir / "segment_%06d.ts"),
                str(low_dir / "index.m3u8"),
            ]

            # ---- HIGH HLS ----
            cmd += [
                "-map","[vhi]","-map","0:a?",
                "-c:v","libx264","-preset","veryfast","-crf",str(high_crf),
                "-g","48","-sc_threshold","0",
                "-force_key_frames", f"expr:gte(t,n_forced*{SEG_DUR})",
                "-maxrate","4000k","-bufsize","4000k",
                "-c:a","aac","-ar","44100","-ac","1",
                "-f","hls",
                "-hls_time", SEG_DUR,
                "-hls_list_size","12",
                "-hls_allow_cache","0",
                "-hls_flags","delete_segments+independent_segments+append_list+temp_file",
                "-hls_segment_filename", str(high_dir / "segment_%06d.ts"),
                str(high_dir / "index.m3u8"),
            ]

            # ---- RECORDINGS ----
            cmd += [
                "-map","0:v","-map","0:a?",
                "-c:v","libx264","-preset","veryfast","-crf",str(max(18, min(28, high_crf))),
                "-c:a","aac","-b:a","128k",
                "-f","segment",
                "-segment_time", str(settings.RECORDING_SEGMENT_SEC),
                "-reset_timestamps","1",
                "-strftime","1",
                str(rec_base / "%Y-%m-%d/%H/%Y-%m-%d_%H-%M-%S.mp4"),
            ]

        else:  # STREAM_MODE=low
            # Single branch only; no split -> no unconnected pads
            filter_graph = f"[0:v]scale={low_w}:{low_h}[vlow]"
            cmd += ["-filter_complex", filter_graph]

            cmd += [
                "-map","[vlow]",
                "-c:v","libx264","-preset","veryfast","-crf",str(low_crf),
                "-g","48","-sc_threshold","0",
                "-force_key_frames", f"expr:gte(t,n_forced*{SEG_DUR})",
                "-maxrate","1200k","-bufsize","1200k",
                "-an",
                "-f","hls",
                "-hls_time", SEG_DUR,
                "-hls_list_size","12",
                "-hls_allow_cache","0",
                "-hls_flags","delete_segments+independent_segments+append_list+temp_file",
                "-hls_segment_filename", str(low_dir / "segment_%06d.ts"),
                str(low_dir / "index.m3u8"),
            ]
            # NOTE: No maps for [vhi] or audio; no recordings branch

        logger.debug("FFmpeg cmd: %s", " ".join(str(x) for x in cmd))
        logger.info("FFmpeg stderr log: %s", log_path)

        log_file = open(log_path, "ab", buffering=0)
        proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=log_file)
        self._procs[cam_id] = proc

        if mode == "all":
            # Only maintain recording dirs when recording is enabled
            threading.Thread(target=self._maintain_rec_dirs, args=(cam_id, cam_name), daemon=True).start()
            

    def stop_camera(self, cam_id: int) -> None:
        p = self._procs.pop(cam_id, None)
        if not p:
            logger.info("stop_camera: no process for cam_id=%s", cam_id)
            return
        try:
            if p.poll() is None:
                logger.info("Stopping ffmpeg cam_id=%s", cam_id)
                p.send_signal(signal.SIGTERM)
                p.wait(timeout=5)
                logger.info("ffmpeg stopped cam_id=%s return=%s", cam_id, p.returncode)
        except Exception:
            logger.exception("Error stopping ffmpeg cam_id=%s", cam_id)
            try:
                if p.poll() is None:
                    p.kill()
                    logger.warning("ffmpeg killed cam_id=%s", cam_id)
            except Exception:
                logger.exception("Hard kill failed cam_id=%s", cam_id)

    def status(self, cam_id: int) -> dict:
        p = self._procs.get(cam_id)
        running = p is not None and p.poll() is None
        return {"running": running}

ffmpeg_manager = FFmpegManager()

