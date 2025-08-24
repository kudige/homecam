import React, { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import API from '../api'

export default function CameraCard({ cam }){
  const videoRef = useRef(null)
  const [urls, setUrls] = useState(null)
  const [status, setStatus] = useState('idle') // idle | starting | playing | error

  async function waitFor(url, { timeoutMs = 15000, intervalMs = 500 } = {}){
    const start = Date.now()
    while (Date.now() - start < timeoutMs){
      try {
        const r = await fetch(url, { method: 'HEAD', cache: 'no-store' })
        if (r.ok) return true
      } catch {}
      await new Promise(r => setTimeout(r, intervalMs))
    }
    return false
  }

  async function ensureLive(){
    setStatus('starting')
    await API.startCamera(cam.id)
    const u = await API.liveUrls(cam.id)
    setUrls(u)

    // Wait for the low-res playlist to appear
    const ok = await waitFor(u.low)
    if (!ok){
      setStatus('error')
      return u
    }

    // Attach HLS
    const url = u.low
    if (Hls.isSupported()){
	  const hls = new Hls({
		lowLatencyMode: false,          // simpler, fewer in-flight fetches
		liveSyncDurationCount: 3,       // target ~3 segments behind live
		maxLiveSyncPlaybackRate: 1.0,   // avoid speeding ahead
		maxBufferLength: 10,            // seconds
		backBufferLength: 30,
		fragLoadingTimeOut: 8000,
		manifestLoadingTimeOut: 8000,
		maxFragLookUpTolerance: 0.2,    // stricter segment edge tolerance
		capLevelToPlayerSize: true
	  });

      hls.loadSource(url)
      hls.attachMedia(videoRef.current)
      hls.on(Hls.Events.MANIFEST_PARSED, () => setStatus('playing'))
	  //      hls.on(Hls.Events.ERROR, () => setStatus('error'))
	  hls.on(Hls.Events.ERROR, (evt, data) => {
		if (data.fatal) {
		  if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
			hls.recoverMediaError();
		  } else if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
			hls.startLoad(); // retry
		  }
		}
	  });

	  videoRef.current.addEventListener('stalled', () => {
		const v = videoRef.current;
		if (v && v.readyState < 3) v.currentTime = v.currentTime + 0.01;
	  });

    } else {
      videoRef.current.src = url
      setStatus('playing')
    }
    return u
  }

  useEffect(() => { ensureLive() }, []) // auto-start on mount

  return (
    <div className="card">
      <h3>{cam.name}</h3>
      <video ref={videoRef} muted autoPlay playsInline controls></video>
      <div className="row" style={{padding:12, justifyContent:'space-between'}}>
        <span className="pill">id {cam.id}</span>
        <div className="row" style={{gap:8}}>
          <button className="btn secondary" onClick={ensureLive}>
            {status === 'starting' ? 'Starting…' : 'Start'}
          </button>
          <a className="btn" href={`/media/live/${cam.name}/high/index.m3u8`} target="_blank" rel="noreferrer">Open High</a>
        </div>
      </div>
    </div>
  )
}
