// frontend/src/components/CameraCard.jsx
import React, { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import OverlayPlayer from './OverlayPlayer'

export default function CameraCard({ cam }) {
  const videoRef = useRef(null)
  const hlsRef = useRef(null)
  const stallTimerRef = useRef(null)
  const [status, setStatus] = useState('idle')
  const [overlay, setOverlay] = useState({ open:false, title:'', src:'' })

  // --- helpers ---
  async function headOk(url){ try { const r=await fetch(url,{method:'HEAD',cache:'no-store'}); return r.ok } catch { return false } }
  async function waitFor(url, ms=15000, step=400){
    const t0=Date.now(); while(Date.now()-t0<ms){ if(await headOk(url)) return true; await new Promise(r=>setTimeout(r,step)) } return false
  }

  async function openRole(role, startPath){
    const name = encodeURIComponent(cam.name)
    const url = `/media/live/${name}/${role}/index.m3u8`
    // start role via admin endpoint if provided
    if (startPath){
      const res = await fetch(startPath, { method:'POST' })
      const j = await res.json().catch(()=>({}))
      if (j && j.ok === false && j.reason) { alert(`Cannot start ${role}: ${j.reason}`); return }
    }
    const ok = await waitFor(url)
    if (!ok){ alert(`${role} stream did not become ready in time.`); return }
    setOverlay({ open:true, title: `${cam.name} — ${role.toUpperCase()}`, src:url })
  }

  // --- grid thumbnail player (unchanged) ---
  function nudgePlayback() {
    const v = videoRef.current
    if (!v) return
    try {
      const buf = v.buffered, ct = v.currentTime, end = buf.length ? buf.end(buf.length-1) : NaN
      if (!Number.isNaN(end) && end - ct < 0.2) v.currentTime = Math.max(0, end - 0.5)
      if (v.paused) v.play().catch(()=>{})
      const hls = hlsRef.current; if (hls && hls.media) hls.startLoad()
    } catch {}
  }
  function startWatchdog(){
    stopWatchdog()
    stallTimerRef.current = setInterval(() => {
      const v = videoRef.current; if (!v) return
      if (!startWatchdog.last) startWatchdog.last = v.currentTime
      const advanced = v.currentTime > startWatchdog.last + 0.2
      if (!advanced) nudgePlayback()
      startWatchdog.last = v.currentTime
    }, 3000)
  }
  function stopWatchdog(){ if (stallTimerRef.current){ clearInterval(stallTimerRef.current); stallTimerRef.current=null } }

  async function playGrid(){
    try{
      setStatus('starting')
      const src = `/media/live/${encodeURIComponent(cam.name)}/grid/index.m3u8`
      if (Hls.isSupported()){
        if (hlsRef.current){ try{ hlsRef.current.destroy() }catch{}; hlsRef.current=null }
        const hls = new Hls({ lowLatencyMode:false, liveSyncDurationCount:4, liveMaxLatencyDurationCount:10, maxBufferLength:14, backBufferLength:30 })
        hlsRef.current = hls
        hls.loadSource(src); hls.attachMedia(videoRef.current)
        hls.on(Hls.Events.MANIFEST_PARSED, () => { setStatus('playing'); videoRef.current.play().catch(()=>{}); startWatchdog() })
        hls.on(Hls.Events.ERROR, (_e,d)=>{ if(d.fatal){ if(d.type===Hls.ErrorTypes.MEDIA_ERROR) hls.recoverMediaError(); else if(d.type===Hls.ErrorTypes.NETWORK_ERROR) hls.startLoad(); else setStatus('error') } })
      } else {
        videoRef.current.src = src; await videoRef.current.play().catch(()=>{}); setStatus('playing'); startWatchdog()
      }
    } catch { setStatus('error') }
  }

  useEffect(() => {
    playGrid()
    return () => { stopWatchdog(); if (hlsRef.current){ try{ hlsRef.current.destroy() }catch{}; hlsRef.current=null } }
  }, [cam.name])

  return (
    <div className="card">
      <h3>{cam.name}</h3>
      <video
        ref={videoRef}
        muted autoPlay playsInline preload="auto" controls
        style={{ width: '100%', height: 180, background: '#000' }}
      />
      <div className="row" style={{padding:12, justifyContent:'space-between'}}>
        <span className="pill">id {cam.id}</span>
        <div className="row" style={{gap:8}}>
          <button className="btn secondary" onClick={playGrid}>
            {status === 'starting' ? 'Starting…' : 'Restart Grid'}
          </button>
          <button className="btn"
            onClick={()=>openRole('medium', `/api/admin/cameras/${cam.id}/medium/start`)}
          >
            Open Medium
          </button>
          <button className="btn"
            onClick={()=>openRole('high', `/api/admin/cameras/${cam.id}/high/start`)}
          >
            Open High
          </button>
        </div>
      </div>

      <OverlayPlayer
        open={overlay.open}
        title={overlay.title}
        src={overlay.src}
        onClose={()=>setOverlay(o=>({ ...o, open:false }))}
      />
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
