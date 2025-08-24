import subprocess, threading, time, os, signal
from pathlib import Path
from typing import Dict, Optional
from dataclasses import dataclass

from .config import LIVE_DIR, REC_DIR, settings

@dataclass
class ProcGroup:
    low: Optional[subprocess.Popen] = None
    high: Optional[subprocess.Popen] = None
    rec: Optional[subprocess.Popen] = None

class FFmpegManager:
    def __init__(self):
        self._procs: Dict[int, ProcGroup] = {}
        self._lock = threading.Lock()

    def live_dir(self, cam_name: str, quality: str) -> Path:
        d = LIVE_DIR / cam_name / quality
        d.mkdir(parents=True, exist_ok=True)
        return d

    def rec_dir_for_now(self, cam_name: str) -> Path:
        # recordings/camera/YYYY-MM-DD/HH
        now = time.localtime()
        d = REC_DIR / cam_name / time.strftime("%Y-%m-%d", now) / time.strftime("%H", now)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def start_camera(self, cam_id: int, cam_name: str, rtsp_url: str, low_w: int, low_h: int, low_crf: int, high_crf: int):
        with self._lock:
            if cam_id in self._procs:
                return

            # LOW-RES live HLS
            low_dir = self.live_dir(cam_name, "low")
            low_cmd = [
                "ffmpeg", "-nostdin", "-rtsp_transport", "tcp", "-i", rtsp_url,
                "-vf", f"scale={low_w}:{low_h}",
                "-c:v", "libx264", "-crf", str(low_crf), "-preset", "veryfast", "-g", "48", "-sc_threshold", "0",
                "-an",  # ignore audio for grid
                "-f", "hls",
                "-hls_time", "2", "-hls_list_size", "60",
                "-hls_flags", "delete_segments+program_date_time+independent_segments",
                "-hls_segment_filename", str(low_dir / "segment_%06d.ts"),
                str(low_dir / "index.m3u8")
            ]

            # HIGH-RES live HLS (re-encode for compatibility)
            high_dir = self.live_dir(cam_name, "high")
            high_cmd = [
                "ffmpeg", "-nostdin", "-rtsp_transport", "tcp", "-i", rtsp_url,
                "-c:v", "libx264", "-crf", str(high_crf), "-preset", "veryfast", "-g", "48", "-sc_threshold", "0",
                "-c:a", "aac", "-ar", "44100", "-ac", "1",
                "-f", "hls",
                "-hls_time", "2", "-hls_list_size", "60",
                "-hls_flags", "delete_segments+program_date_time+independent_segments",
                "-hls_segment_filename", str(high_dir / "segment_%06d.ts"),
                str(high_dir / "index.m3u8")
            ]

            # RECORDINGS — MP4 chunks (5 min)
            rec_dir = self.rec_dir_for_now(cam_name)
            rec_cmd = [
                "ffmpeg", "-nostdin", "-rtsp_transport", "tcp", "-i", rtsp_url,
                "-c:v", "libx264", "-crf", str(max(18, min(28, high_crf))), "-preset", "veryfast",
                "-c:a", "aac", "-b:a", "128k",
                "-f", "segment",
                "-segment_time", str(settings.RECORDING_SEGMENT_SEC),
                "-reset_timestamps", "1",
                "-strftime", "1",
                str(rec_dir / "%Y-%m-%d_%H-%M-%S.mp4")
            ]

            def launch(cmd):
                return subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

            procs = ProcGroup(
                low=launch(low_cmd),
                high=launch(high_cmd),
                rec=launch(rec_cmd),
            )
            self._procs[cam_id] = procs

            # Watchdog thread for recording path rotation per hour
            threading.Thread(target=self._rotate_rec_dir, args=(cam_id, cam_name, rtsp_url, high_crf), daemon=True).start()

    def _rotate_rec_dir(self, cam_id: int, cam_name: str, rtsp_url: str, high_crf: int):
        # Re-create recording process when the hour changes to keep files neatly grouped
        cur_hour = time.strftime("%Y-%m-%d-%H", time.localtime())
        while True:
            time.sleep(10)
            with self._lock:
                pg = self._procs.get(cam_id)
                if not pg:
                    return
            new_hour = time.strftime("%Y-%m-%d-%H", time.localtime())
            if new_hour != cur_hour:
                cur_hour = new_hour
                # Restart rec process with a new output directory
                with self._lock:
                    pg = self._procs.get(cam_id)
                    if not pg:
                        return
                    try:
                        if pg.rec and pg.rec.poll() is None:
                            pg.rec.send_signal(signal.SIGTERM)
                            pg.rec.wait(timeout=5)
                    except Exception:
                        pass
                    rec_dir = self.rec_dir_for_now(cam_name)
                    rec_cmd = [
                        "ffmpeg", "-nostdin", "-rtsp_transport", "tcp", "-i", rtsp_url,
                        "-c:v", "libx264", "-crf", str(max(18, min(28, high_crf))), "-preset", "veryfast",
                        "-c:a", "aac", "-b:a", "128k",
                        "-f", "segment",
                        "-segment_time", str(settings.RECORDING_SEGMENT_SEC),
                        "-reset_timestamps", "1",
                        "-strftime", "1",
                        str(rec_dir / "%Y-%m-%d_%H-%M-%S.mp4")
                    ]
                    pg.rec = subprocess.Popen(rec_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)

    def stop_camera(self, cam_id: int):
        with self._lock:
            pg = self._procs.pop(cam_id, None)
        if not pg:
            return
        for p in [pg.low, pg.high, pg.rec]:
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

    def status(self, cam_id: int) -> dict:
        with self._lock:
            pg = self._procs.get(cam_id)
        if not pg:
            return {"running": False}
        def alive(p):
            return p is not None and p.poll() is None
        return {
            "running": True,
            "low": alive(pg.low),
            "high": alive(pg.high),
            "rec": alive(pg.rec)
        }

ffmpeg_manager = FFmpegManager()
