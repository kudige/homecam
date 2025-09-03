// frontend/src/components/CameraCard.jsx
import React, { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'

export default function CameraCard({ cam }) {
  const videoRef = useRef(null)
  const hlsRef = useRef(null)
  const stallTimerRef = useRef(null)
  const [status, setStatus] = useState('idle') // idle | starting | playing | error
  const [roles, setRoles] = useState({ grid: false, medium: false, high: false, rec: false })

  // --- role status polling (no backend dependency) ---
  async function headOk(url) {
    try {
      const r = await fetch(url, { method: 'HEAD', cache: 'no-store' })
      return r.ok
    } catch { return false }
  }
  async function waitFor(url, ms = 15000, step = 400) {
	const t0 = Date.now()
	while (Date.now() - t0 < ms) {
      if (await headOk(url)) return true
      await new Promise(r => setTimeout(r, step))
	}
	return false
  }

  async function openMedium() {
	const name = encodeURIComponent(cam.name)
	const url = `/media/live/${name}/medium/index.m3u8`

	// start the role
	const res = await fetch(`/api/admin/cameras/${cam.id}/medium/start`, { method: 'POST' })
	const j = await res.json()
	if (j && j.ok === false && j.reason) {
      alert(`Cannot start medium: ${j.reason}`)  // e.g. disabled or blocked by mode
      return
	}

	// wait until the playlist exists, then open
	const ok = await waitFor(url)
	if (!ok) {
      alert('Medium stream did not become ready in time.')
      return
	}
	window.open(url, '_blank', 'noopener')
  }
  async function openHigh() {
	const name = encodeURIComponent(cam.name)
	const url = `/media/live/${name}/high/index.m3u8`

	// start the role
	const res = await fetch(`/api/admin/cameras/${cam.id}/high/start`, { method: 'POST' })
	const j = await res.json()
	if (j && j.ok === false && j.reason) {
      alert(`Cannot start medium: ${j.reason}`)  // e.g. disabled or blocked by mode
      return
	}

	// wait until the playlist exists, then open
	const ok = await waitFor(url)
	if (!ok) {
      alert('High stream did not become ready in time.')
      return
	}
	window.open(url, '_blank', 'noopener')
  }  
  
  async function pollRoles() {
    const base = `/media/live/${encodeURIComponent(cam.name)}`
    const [grid, medium, high] = await Promise.all([
      headOk(`${base}/grid/index.m3u8`),
      headOk(`${base}/medium/index.m3u8`),
      headOk(`${base}/high/index.m3u8`),
    ])
    // REC heuristic: show on if retention is enabled (optional: add a real status later)
    const rec = cam.retention_days ? cam.retention_days > 0 : false
    setRoles({ grid, medium, high, rec })
  }

  useEffect(() => {
    // initial + interval poll
    pollRoles()
    const t = setInterval(pollRoles, 10000)
    return () => clearInterval(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cam.name, cam.retention_days])

  // --- watchdog helpers (keep thumbnails from stalling) ---
  function nudgePlayback() {
    const v = videoRef.current
    if (!v) return
    try {
      const buf = v.buffered
      const ct  = v.currentTime
      const end = buf.length ? buf.end(buf.length - 1) : NaN
      if (!Number.isNaN(end) && end - ct < 0.2) v.currentTime = Math.max(0, end - 0.5)
      if (v.paused) v.play().catch(()=>{})
      const hls = hlsRef.current
      if (hls && hls.media) hls.startLoad()
    } catch {}
  }
  function startWatchdog() {
    stopWatchdog()
    stallTimerRef.current = setInterval(() => {
      const v = videoRef.current
      if (!v) return
      if (!startWatchdog.lastTime) startWatchdog.lastTime = v.currentTime
      const advanced = v.currentTime > startWatchdog.lastTime + 0.2
      if (!advanced) nudgePlayback()
      startWatchdog.lastTime = v.currentTime
    }, 3000)
  }
  function stopWatchdog() {
    if (stallTimerRef.current) { clearInterval(stallTimerRef.current); stallTimerRef.current = null }
  }

  async function playStream() {
    try {
      setStatus('starting')
      // For grid thumbnails, always use the *grid* role:
      const src = `/media/live/${encodeURIComponent(cam.name)}/grid/index.m3u8`
      if (Hls.isSupported()) {
        if (hlsRef.current) { try { hlsRef.current.destroy() } catch {} hlsRef.current = null }
        const hls = new Hls({
          lowLatencyMode: false,
          liveSyncDurationCount: 4,
          liveMaxLatencyDurationCount: 10,
          liveDurationInfinity: true,
          maxBufferLength: 14,
          backBufferLength: 30,
          maxFragLookUpTolerance: 0.25,
          fragLoadingTimeOut: 10000,
          manifestLoadingTimeOut: 10000,
          capLevelToPlayerSize: true,
          enableWorker: true
        })
        hlsRef.current = hls
        hls.loadSource(src)
        hls.attachMedia(videoRef.current)
        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          setStatus('playing')
          videoRef.current.play().catch(()=>{})
          startWatchdog()
        })
        hls.on(Hls.Events.LEVEL_LOADED, () => { hls.startLoad() })
        hls.on(Hls.Events.ERROR, (_evt, data) => {
          if (data.fatal) {
            if (data.type === Hls.ErrorTypes.MEDIA_ERROR) hls.recoverMediaError()
            else if (data.type === Hls.ErrorTypes.NETWORK_ERROR) hls.startLoad()
            else setStatus('error')
          } else {
            nudgePlayback()
          }
        })
      } else {
        // Safari native HLS
        videoRef.current.src = src
        await videoRef.current.play().catch(()=>{})
        setStatus('playing'); startWatchdog()
      }
    } catch { setStatus('error') }
  }

  useEffect(() => {
    playStream()
    return () => {
      stopWatchdog()
      if (hlsRef.current) { try { hlsRef.current.destroy() } catch {} hlsRef.current = null }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cam.name])

  return (
    <div className="card">
      <h3 style={{display:'flex', alignItems:'center', justifyContent:'space-between'}}>
        <span>{cam.name}</span>
        <RolePills roles={roles} />
      </h3>

      <video
        ref={videoRef}
        muted
        autoPlay
        playsInline
        preload="auto"
        controls
        style={{ width: '100%', height: 180, background: '#000' }}
      />

      <div className="row" style={{padding:12, justifyContent:'space-between'}}>
        <span className="pill">id {cam.id}</span>
        <div className="row" style={{gap:8}}>
          <button className="btn secondary" onClick={playStream}>
            {status === 'starting' ? 'Starting…' : 'Restart'}
          </button>
          {/* Open the *medium* role by default for full view; high via its own link */}
		  <button className="btn" onClick={openMedium}>Open Medium</button>
		  <button className="btn" onClick={openHigh}>Open High</button>
        </div>
      </div>
    </div>
  )
}

function RolePills({ roles }) {
  const Item = ({ label, on }) => (
    <span
      className="pill"
      style={{
        marginLeft: 6,
        background: on ? 'rgba(34,197,94,0.2)' : 'rgba(148,163,184,0.2)',
        border: `1px solid ${on ? 'rgba(34,197,94,0.5)' : 'rgba(148,163,184,0.35)'}`,
        color: on ? '#34d399' : '#cbd5e1'
      }}
      title={on ? 'running' : 'stopped'}
    >
      {label}
    </span>
  )
  return (
    <div className="row" style={{gap:0}}>
      <Item label="GRID" on={roles.grid} />
      <Item label="MED"  on={roles.medium} />
      <Item label="HIGH" on={roles.high} />
      <Item label="REC"  on={roles.rec} />
    </div>
  )
}
