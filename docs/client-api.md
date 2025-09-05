# Client API

Endpoints for frontend clients to discover cameras and retrieve recordings. Authentication is currently not enforced.

## List Cameras

`GET /api/cameras`

Returns an object containing all cameras and the relative URLs to their low and high HLS feeds.

**Sample response**

```json
{
  "front": {
    "low": "/streams/front-low.m3u8",
    "high": "/streams/front-high.m3u8"
  },
  "garage": {
    "low": "/streams/garage-low.m3u8",
    "high": "/streams/garage-high.m3u8"
  }
}
```

## List Recordings for a Date

`GET /api/cameras/{cam_id}/recordings/{date}`

Lists recording files for the specified camera on the given `YYYY-MM-DD` date. Each entry includes:

- `path` – API path to the MP4 file.
- `start_ts` – recording start timestamp in epoch seconds.
- `size_bytes` – file size in bytes.

**Sample response**

```json
[
  {
    "path": "/api/recordings/front/2024-04-06/00/front-000000.mp4",
    "start_ts": 1712361600,
    "size_bytes": 1048576
  },
  {
    "path": "/api/recordings/front/2024-04-06/01/front-010000.mp4",
    "start_ts": 1712365200,
    "size_bytes": 2097152
  }
]
```

## Fetch a Recording File

`GET /api/recordings/{camera}/{date}/{hour}/{filename}`

Streams or downloads the requested MP4 recording.

**Sample response**

```http
HTTP/1.1 200 OK
Content-Type: video/mp4

<binary mp4 data>
```
