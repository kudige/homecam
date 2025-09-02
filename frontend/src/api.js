// Unified API client with separate client vs admin surfaces.
// NOTE: getCamerasClient unwraps the { cameras: [...] } shape.

const API = {
  // CLIENT (no RTSP)
  getCamerasClient() {
    return fetch('/api/cameras')
      .then(r => r.json())
      .then(json => json && Array.isArray(json.cameras) ? json.cameras : []);
  },

  // recordings
  recordings(camId, date) {
    return fetch(`/api/cameras/${camId}/recordings/${date}`)
      .then(r => r.json());
  },

  // ADMIN (manage cameras)
  getCamerasAdmin() {
    return fetch('/api/admin/cameras').then(r => r.json());
  },

  addCameraAdmin({ name, rtsp_url, retention_days }) {
    return fetch('/api/admin/cameras', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, rtsp_url, retention_days })
    }).then(async r => {
      if (!r.ok) throw new Error(await r.text());
      return r.json();
    });
  },

  updateCameraAdmin(id, body) {
    return fetch(`/api/admin/cameras/${id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    }).then(r => r.json());
  },

  deleteCameraAdmin(id) {
    return fetch(`/api/admin/cameras/${id}`, { method: 'DELETE' })
      .then(r => r.json());
  },

  startCameraAdmin(id) {
    return fetch(`/api/admin/cameras/${id}/start`, { method: 'POST' })
      .then(r => r.json());
  },

  stopCameraAdmin(id) {
    return fetch(`/api/admin/cameras/${id}/stop`, { method: 'POST' })
      .then(r => r.json());
  },

  // ADMIN (streams)
  addStreamAdmin(camId, { name, rtsp_url }) {
    return fetch(`/api/admin/cameras/${camId}/streams`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, rtsp_url })
    }).then(r => r.json());
  },

  listStreamsAdmin(camId) {
    return fetch(`/api/admin/cameras/${camId}/streams`).then(r => r.json());
  },

  probeStreamAdmin(camId, streamId) {
    return fetch(`/api/admin/cameras/${camId}/streams/${streamId}/probe`, { method: 'POST' })
      .then(r => r.json());
  },
};

export default API;
