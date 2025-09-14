# Motion Events Integration

This guide outlines how to add motion events to recorded video so that users can quickly jump to the relevant sections. The focus is on using the camera's own motion notifications to avoid expensive CPU-bound video processing.

## 1. Listen for ONVIF Motion Events

Most IP cameras expose motion notifications through the ONVIF Events service. The `motion.py` script in this directory demonstrates how to subscribe to these events.

Steps:

1. Install dependencies:
   ```bash
   pip install onvif-zeep
   ```
2. Run the script against your camera to confirm that motion events are received:
   ```bash
   python motion.py 192.168.1.50 --user admin --password yourpass
   ```
3. The script prints event messages when motion is detected. Run it as a long-lived service to capture events continuously.

## 2. Record Motion Event Timestamps

1. When a motion event starts, record its timestamp (and optionally when it ends) in a new database table, e.g. `motion_events(camera_id, start_ts, end_ts)`.
2. Store events in UTC to align with recording filenames.
3. Because motion events come from the camera, no video decoding or computer vision processing is required, keeping CPU usage minimal.

## 3. Map Events to Recording Segments

Recording files are saved in 5-minute MP4 chunks (`media/recordings/<camera>/YYYY-MM-DD/HH/HH-MM-SS.mp4`). To tie motion events to files:

1. For each event, compute the corresponding file path based on the timestamp.
2. Optionally store the filename or an offset into the file to allow the UI to jump directly to the motion.
3. If an event spans multiple segments, create one row per segment or store start/end offsets for each.

## 4. Expose Motion Data via the API

1. Add a backend endpoint such as `GET /api/cameras/{id}/motions?start=&end=` that returns the motion events for a time range.
2. When returning recordings, include any associated motion events so the client knows which files contain motion.

## 5. Frontend Playback

1. When displaying the recording timeline, fetch motion events for the visible range.
2. Highlight motion sections on the timeline and allow clicking on a marker to jump to that timestamp.
3. Consider preloading short clips around each motion event for quicker playback.

## 6. Keep CPU Usage Low

- Use the camera's own motion detection rather than analyzing video frames.
- Avoid transcoding recordings; copy streams (`-c copy`) in FFmpeg.
- Batch database writes if events are frequent.
- Run the motion listener as a lightweight Python process or small container.

With these steps, the system can provide motion markers for recorded video with minimal additional CPU overhead.
