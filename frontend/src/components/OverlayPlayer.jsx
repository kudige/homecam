// frontend/src/components/OverlayPlayer.jsx
import React, { useEffect } from 'react'
import Player from './Player'

export default function OverlayPlayer({ open, title, src, onClose }) {
  useEffect(() => {
    function onKey(e){ if (e.key === 'Escape') onClose?.() }
    if (open) window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, onClose])

  if (!open) return null
  return (
    <div style={backdrop}>
      <div style={modal}>
        <div style={header}>
          <div style={{fontWeight:700}}>{title}</div>
          <button className="btn secondary" onClick={onClose}>Close</button>
        </div>
        <div style={{padding:12}}>
          <Player src={src} autoPlay />
        </div>
      </div>
    </div>
  )
}

const backdrop = {
  position:'fixed', inset:0, background:'rgba(0,0,0,0.6)',
  display:'flex', alignItems:'center', justifyContent:'center', zIndex:1000
}
const modal = {
  width:'min(960px, 92vw)', background:'#0f1318', border:'1px solid #1f2630',
  borderRadius:12, boxShadow:'0 20px 60px rgba(0,0,0,0.45)'
}
const header = {
  display:'flex', alignItems:'center', justifyContent:'space-between',
  padding:'12px 16px', borderBottom:'1px solid #1f2630'
}
