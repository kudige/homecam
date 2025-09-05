# Client API

Endpoints for frontend clients to discover cameras and retrieve recordings. Authentication is currently not enforced.

## List Cameras

`GET /api/cameras`

Returns an object containing all cameras and the relative URLs to their low and high HLS feeds.

## List Recordings for a Date

`GET /api/cameras/{cam_id}/recordings/{date}`

Lists recording files for the specified camera on the given `YYYY-MM-DD` date. Each entry includes:

- `path` – API path to the MP4 file.
- `start_ts` – recording start timestamp in epoch seconds.
- `size_bytes` – file size in bytes.

## Fetch a Recording File

`GET /api/recordings/{camera}/{date}/{hour}/{filename}`

Streams or downloads the requested MP4 recording.
