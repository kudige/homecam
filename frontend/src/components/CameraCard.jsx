// frontend/src/components/CameraCard.jsx
import React, { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import OverlayPlayer from './OverlayPlayer'

export default function CameraCard({ cam }) {
  const videoRef = useRef(null)
  const hlsRef = useRef(null)
  const stallTimerRef = useRef(null)
  const [status, setStatus] = useState('idle') // idle | starting | playing | error
  const [overlay, setOverlay] = useState({ open:false, title:'', src:'' })

  // --- tiny helpers ---
  async function headOk(url){ try { const r=await fetch(url,{method:'HEAD',cache:'no-store'}); return r.ok } catch { return false } }
  async function waitFor(url, ms=15000, step=400){
    const t0=Date.now(); while(Date.now()-t0<ms){ if(await headOk(url)) return true; await new Promise(r=>setTimeout(r,step)) } return false
  }
  async function openRole(role, startPath){
    const name = encodeURIComponent(cam.name)
    const url = `/media/live/${name}/${role}/index.m3u8`
    if (startPath){
      const res = await fetch(startPath, { method:'POST' })
      const j = await res.json().catch(()=>({}))
      if (j && j.ok === false && j.reason) { alert(`Cannot start ${role}: ${j.reason}`); return }
    }
    const ok = await waitFor(url)
    if (!ok){ alert(`${role} stream did not become ready in time.`); return }
    setOverlay({ open:true, title: `${cam.name} — ${role.toUpperCase()}`, src:url })
  }

  // --- grid thumbnail player (compact, no controls) ---
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
        const hls = new Hls({
          lowLatencyMode:false,
          liveSyncDurationCount:4,
          liveMaxLatencyDurationCount:10,
          maxBufferLength:14,
          backBufferLength:30
        })
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

  // --- icon bar handlers ---
  const openMedium = () => openRole('medium', `/api/admin/cameras/${cam.id}/medium/start`)
  const openHigh   = () => openRole('high',   `/api/admin/cameras/${cam.id}/high/start`)

  return (
    <div className="card" style={{borderRadius:12}}>
      {/* compact header with two tiny icons */}
      <div style={headerRow}>
        <div style={title}>{cam.name}</div>
        <div style={iconRow}>
          <button title="Open Medium" aria-label="Open Medium" style={iconBtn} onClick={openMedium}>
            {/* medium icon (play triangle) */}
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" role="img">
              <path d="M8 5v14l11-7-11-7z" stroke="currentColor" strokeWidth="1.6" fill="currentColor" />
            </svg>
          </button>
          <button title="Open High" aria-label="Open High" style={iconBtn} onClick={openHigh}>
            {/* high icon (magnifier) */}
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" role="img">
              <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.6"/>
              <path d="M16.5 16.5L21 21" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
            </svg>
          </button>
        </div>
      </div>

      <video
        ref={videoRef}
        muted
        autoPlay
        playsInline
        preload="auto"
        // no controls to keep compact
        style={{ width:'100%', height:160, background:'#000', display:'block' }}
      />

      {/* Overlay player for medium/high */}
      <OverlayPlayer
        open={overlay.open}
        title={overlay.title}
        src={overlay.src}
        onClose={()=>setOverlay(o=>({ ...o, open:false }))}
      />
    </div>
  )
}

const headerRow = {
  display:'flex',
  alignItems:'center',
  justifyContent:'space-between',
  padding:'6px 8px',
  borderBottom:'1px solid #1f2630'
}
const title = { fontSize:13, fontWeight:600, whiteSpace:'nowrap', overflow:'hidden', textOverflow:'ellipsis', maxWidth:'70%' }
const iconRow = { display:'flex', gap:6 }
const iconBtn = {
  width:28, height:28,
  display:'grid', placeItems:'center',
  borderRadius:8, border:'1px solid #1f2630',
  background:'#151a21', color:'#cad5e2',
  cursor:'pointer'
}
