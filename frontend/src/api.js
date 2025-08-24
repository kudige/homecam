const API = {
  async getCameras() {
    const r = await fetch('/api/cameras');
    return r.json();
  },
  async startCamera(id) {
    const r = await fetch(`/api/cameras/${id}/start`, { method: 'POST' });
    return r.json();
  },
  async stopCamera(id) {
    const r = await fetch(`/api/cameras/${id}/stop`, { method: 'POST' });
    return r.json();
  },
  liveUrls(camId) {
    return fetch(`/api/cameras/${camId}/live`).then(r => r.json());
  },
  recordings(camId, date) {
    return fetch(`/api/cameras/${camId}/recordings/${date}`).then(r => r.json());
  },
  async addCamera({ name, rtsp_url, retention_days }) {
    const r = await fetch('/api/cameras', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, rtsp_url, retention_days })
    });
    if (!r.ok) throw new Error(await r.text());
    return r.json();
  }
};
export default API;
