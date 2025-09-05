import json, subprocess, shlex, datetime as dt

def probe_rtsp(rtsp_url: str) -> dict:
    """
    Returns: dict(width, height, fps, bitrate_kbps)
    """
    # -rtsp_transport tcp improves reliability
    cmd = f'ffprobe -v error -select_streams v:0 -show_entries stream=width,height,avg_frame_rate,bit_rate ' \
          f'-of json -rtsp_transport tcp "{rtsp_url}"'
    p = subprocess.run(shlex.split(cmd), stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=15)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", "ignore"))
    data = json.loads(p.stdout.decode())
    st = (data.get("streams") or [{}])[0]
    width = st.get("width")
    height = st.get("height")
    # avg_frame_rate like "30/1"
    afr = st.get("avg_frame_rate")
    fps = None
    if afr and isinstance(afr, str) and "/" in afr:
        num, den = afr.split("/")
        try:
            fps = int(round(float(num) / float(den)))
        except Exception:
            fps = None
    bitrate = st.get("bit_rate")
    kbps = int(round(int(bitrate)/1000)) if bitrate else None
    return {"width": width, "height": height, "fps": fps, "bitrate_kbps": kbps, "probed_at": dt.datetime.utcnow()}
