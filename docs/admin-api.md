# Admin API

Administrative endpoints for managing cameras, streams, and encoder roles.

## Cameras

### List Cameras
`GET /api/admin/cameras`

Returns all cameras with configuration and stream metadata.

### Create Camera
`POST /api/admin/cameras`

Body fields: `name`, `rtsp_url`, optional `retention_days`.

### Update Camera
`PUT /api/admin/cameras/{cam_id}`

Updates camera settings such as RTSP URL, retention, and encoder quality.

### Delete Camera
`DELETE /api/admin/cameras/{cam_id}`

Stops FFmpeg processes and removes the camera.

### Update Role Configuration
`PUT /api/admin/cameras/{cam_id}/roles`

Adjusts stream selection and modes for grid, medium, high, and recording roles and retention.

### Start or Stop Camera
`POST /api/admin/cameras/{cam_id}/start`

`POST /api/admin/cameras/{cam_id}/stop`

Starts or stops all FFmpeg processes for the camera.

### Camera Status
`GET /api/admin/cameras/{cam_id}/status`

Returns running flags for each role.

## Streams

### List Streams
`GET /api/admin/cameras/{cam_id}/streams`

### Add Stream
`POST /api/admin/cameras/{cam_id}/streams`

Body fields: `name`, `rtsp_url`.

### Probe Stream
`POST /api/admin/cameras/{cam_id}/streams/{stream_id}/probe`

Runs ffprobe to populate stream metadata.

## On-demand Roles

Endpoints to control specific encoder roles:

- `POST /api/admin/cameras/{cam_id}/grid/start`
- `POST /api/admin/cameras/{cam_id}/medium/start`
- `POST /api/admin/cameras/{cam_id}/medium/stop`
- `POST /api/admin/cameras/{cam_id}/high/start`
- `POST /api/admin/cameras/{cam_id}/high/stop`
