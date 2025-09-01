// frontend/src/components/CameraCard.jsx
import React, { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'

export default function CameraCard({ cam }) {
  const videoRef = useRef(null)
  const hlsRef = useRef(null)
  const stallTimerRef = useRef(null)
  const [status, setStatus] = useState('idle') // idle | starting | playing | error

  // --- watchdog helpers ---
  function nudgePlayback() {
    const v = videoRef.current
    if (!v) return
    try {
      const buf = v.buffered
      const ct = v.currentTime
      const end = buf.length ? buf.end(buf.length - 1) : NaN
      if (!Number.isNaN(end) && end - ct < 0.2) {
        v.currentTime = Math.max(0, end - 0.5)
      }
      if (v.paused) v.play().catch(() => {})
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
    if (stallTimerRef.current) {
      clearInterval(stallTimerRef.current)
      stallTimerRef.current = null
    }
  }

  async function playStream() {
    try {
      setStatus('starting')
      const src = cam.low_url
      if (Hls.isSupported()) {
        if (hlsRef.current) {
          try { hlsRef.current.destroy() } catch {}
          hlsRef.current = null
        }
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
          videoRef.current.play().catch(() => {})
          startWatchdog()
        })
        hls.on(Hls.Events.LEVEL_LOADED, () => {
          hls.startLoad()
        })
        hls.on(Hls.Events.ERROR, (_evt, data) => {
          if (data.fatal) {
            if (data.type === Hls.ErrorTypes.MEDIA_ERROR) {
              hls.recoverMediaError()
            } else if (data.type === Hls.ErrorTypes.NETWORK_ERROR) {
              hls.startLoad()
            } else {
              setStatus('error')
            }
          } else {
            nudgePlayback()
          }
        })
      } else {
        // Safari native HLS
        videoRef.current.src = src
        videoRef.current.play().catch(() => {})
        setStatus('playing')
        startWatchdog()
      }
    } catch (e) {
      setStatus('error')
    }
  }

  useEffect(() => {
    playStream()
    return () => {
      stopWatchdog()
      if (hlsRef.current) { try { hlsRef.current.destroy() } catch {} hlsRef.current = null }
    }
  }, [cam.hls_low])

  return (
    <div className="card">
      <h3>{cam.name}</h3>
      <video
        ref={videoRef}
        muted
        autoPlay
        playsInline
        preload="auto"
        controls
        style={{ width: '100%', height: 180, background: '#000' }}
      />
      <div className="row" style={{ padding: 12, justifyContent: 'space-between' }}>
        <span className="pill">id {cam.id}</span>
        <div className="row" style={{ gap: 8 }}>
          <button className="btn secondary" onClick={playStream}>
            {status === 'starting' ? 'Starting…' : 'Restart'}
          </button>
          <a
            className="btn"
            href={cam.high_url}
            target="_blank"
            rel="noreferrer"
          >
            Open High
          </a>
        </div>
      </div>
    </div>
  )
}
