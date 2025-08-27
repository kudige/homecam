import React, { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import API from '../api'

export default function CameraCard({ cam }){
  const videoRef = useRef(null)
  const hlsRef = useRef(null)          // keep Hls instance alive
  const stallTimerRef = useRef(null)
  const [status, setStatus] = useState('idle') // idle | starting | playing | error

  // Nudge playback if we detect we’re stuck near the live edge
  function nudgePlayback() {
    const v = videoRef.current
    if (!v) return
    try {
      const buf = v.buffered
      const ct  = v.currentTime
      const end = buf.length ? buf.end(buf.length - 1) : NaN
      // If we’re within 0.2s of the buffered end and not advancing, jump 0.5s ahead
      if (!Number.isNaN(end) && end - ct < 0.2) {
        v.currentTime = Math.max(0, end - 0.5)
      }
      if (v.paused) v.play().catch(()=>{})
      const hls = hlsRef.current
      if (hls && hls.media) hls.startLoad() // ensure loader is active
    } catch {}
  }

  function installVideoHandlers() {
    const v = videoRef.current
    if (!v) return
    const onStalled  = () => nudgePlayback()
    const onWaiting  = () => nudgePlayback()
    const onPause    = () => { /* keep paused if user paused */ }
    v.addEventListener('stalled', onStalled)
    v.addEventListener('waiting', onWaiting)
    v.addEventListener('pause', onPause)
    return () => {
      v.removeEventListener('stalled', onStalled)
      v.removeEventListener('waiting', onWaiting)
      v.removeEventListener('pause', onPause)
    }
  }

  function startWatchdog() {
    stopWatchdog()
    stallTimerRef.current = setInterval(() => {
      const v = videoRef.current
      if (!v) return
      // If video time hasn’t advanced in ~3s, try a gentle push
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

  async function ensureLive(){
    try {
      setStatus('starting')
      await API.startCamera(cam.id)
      const u = await API.liveUrls(cam.id)
      const src = u.low

      if (Hls.isSupported()){
        // Tear down old instance if any
        if (hlsRef.current) {
          try { hlsRef.current.destroy() } catch {}
          hlsRef.current = null
        }
        const hls = new Hls({
          // Safer live settings
          lowLatencyMode: false,
          liveSyncDurationCount: 4,          // target ~4 segments behind live
          liveMaxLatencyDurationCount: 10,   // cap max latency
          liveDurationInfinity: true,
          maxBufferLength: 14,               // seconds
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
        hls.on(Hls.Events.LEVEL_LOADED, () => {
          // periodic event while live; keep loader awake
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
            // non-fatal: try a small nudge
            nudgePlayback()
          }
        })
      } else {
        // Native HLS (Safari)
        videoRef.current.src = src
        videoRef.current.play().catch(()=>{})
        setStatus('playing')
        startWatchdog()
      }
    } catch (e) {
      setStatus('error')
    }
  }

  useEffect(() => {
    const cleanupVideo = installVideoHandlers()
    ensureLive()
    return () => {
      stopWatchdog()
      if (hlsRef.current) { try { hlsRef.current.destroy() } catch {} hlsRef.current = null }
      if (cleanupVideo) cleanupVideo()
    }
  }, [])

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
      <div className="row" style={{padding:12, justifyContent:'space-between'}}>
        <span className="pill">id {cam.id}</span>
        <div className="row" style={{gap:8}}>
          <button className="btn secondary" onClick={ensureLive}>
            {status === 'starting' ? 'Starting…' : 'Restart'}
          </button>
          <a className="btn" href={`/media/live/${cam.name}/high/index.m3u8`} target="_blank" rel="noreferrer">
            Open High
          </a>
        </div>
      </div>
    </div>
  )
}
