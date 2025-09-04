// Unified API client with separate client vs admin surfaces.
// CLIENT: /api/cameras returns { cameras: [...] } with low_url/high_url
// ADMIN: camera CRUD, streams, roles, and medium/high on-demand controls.

const API = {
  // CLIENT (no RTSP)
  getCamerasClient() {
    return fetch('/api/cameras')
      .then(r => r.json())
      .then(json => json && Array.isArray(json.cameras) ? json.cameras : []);
  },

  // Recordings (paths are already /api/recordings/...)
  recordings(camId, date) {
    return fetch(`/api/cameras/${camId}/recordings/${date}`).then(r => r.json());
  },

  // ADMIN — cameras
  getCamerasAdmin() {
    return fetch('/api/admin/cameras').then(r => r.json());
  },
  addCameraAdmin({ name, rtsp_url, retention_days }) {
    return fetch('/api/admin/cameras', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, rtsp_url, retention_days })
    }).then(async r => { if (!r.ok) throw new Error(await r.text()); return r.json(); });
  },
  updateCameraAdmin(id, body) {
    return fetch(`/api/admin/cameras/${id}`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(r => r.json());
  },
  deleteCameraAdmin(id) {
    return fetch(`/api/admin/cameras/${id}`, { method: 'DELETE' }).then(r => r.json());
  },

  // ADMIN — streams
  listStreamsAdmin(camId) {
    return fetch(`/api/admin/cameras/${camId}/streams`).then(r => r.json());
  },
  addStreamAdmin(camId, { name, rtsp_url }) {
    return fetch(`/api/admin/cameras/${camId}/streams`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, rtsp_url })
    }).then(r => r.json());
  },
  probeStreamAdmin(camId, streamId) {
    return fetch(`/api/admin/cameras/${camId}/streams/${streamId}/probe`, { method: 'POST' })
      .then(r => r.json());
  },

  // ADMIN — roles (grid/medium/high/recording)
  updateRolesAdmin(camId, body) {
    return fetch(`/api/admin/cameras/${camId}/roles`, {
      method: 'PUT', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(r => r.json());
  },

  getCameraStatusAdmin(camId) {
	return fetch(`/api/admin/cameras/${camId}/status`).then(r => r.json());
  },
  
  // ADMIN — medium/high on-demand start/stop
  startMedium(camId) { return fetch(`/api/admin/cameras/${camId}/medium/start`, { method: 'POST' }).then(r => r.json()); },
  stopMedium(camId)  { return fetch(`/api/admin/cameras/${camId}/medium/stop`,  { method: 'POST' }).then(r => r.json()); },
  startHigh(camId)   { return fetch(`/api/admin/cameras/${camId}/high/start`,   { method: 'POST' }).then(r => r.json()); },
  stopHigh(camId)    { return fetch(`/api/admin/cameras/${camId}/high/stop`,    { method: 'POST' }).then(r => r.json()); },
};

export default API;
