import React from 'react'
import Player from './Player'

export default function OverlayPlayer({ open, role, src, loading, onClose, onToggle }) {
  if (!open) return null

  const isMedium = role === 'medium'

  return (
    <div style={wrapStyle} onClick={onClose}>
      <div style={innerStyle} onClick={e => e.stopPropagation()}>
        {loading ? (
          <div style={loadingStyle}>Loading...</div>
        ) : (
          <Player src={src} />
        )}
        {!loading && (
          <button
            onClick={onToggle}
            title={isMedium ? 'Switch to HD' : 'Switch to Standard'}
            aria-label={isMedium ? 'Switch to HD' : 'Switch to Standard'}
            style={toggleBtn}
          >
            {isMedium ? 'HD' : 'Standard'}
          </button>
        )}
        <button onClick={onClose} aria-label="Close" style={closeBtn}>
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" role="img">
            <path d="M6 6l12 12M18 6L6 18" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
          </svg>
        </button>
      </div>
    </div>
  )
}

const wrapStyle = {
  position: 'fixed',
  top: 0,
  left: 0,
  right: 0,
  bottom: 0,
  background: 'rgba(0,0,0,0.8)',
  display: 'grid',
  placeItems: 'center',
  zIndex: 1000
}

const innerStyle = {
  position: 'relative',
  width: '80%',
  maxWidth: 900
}

const loadingStyle = {
  width: '100%',
  height: 360,
  display: 'grid',
  placeItems: 'center',
  color: '#fff',
  background: '#000'
}

const toggleBtn = {
  position: 'absolute',
  top: 8,
  right: 48,
  height: 32,
  display: 'grid',
  placeItems: 'center',
  padding: '0 8px',
  border: 'none',
  borderRadius: 4,
  background: 'rgba(0,0,0,0.6)',
  color: '#fff',
  cursor: 'pointer',
  fontSize: 12,
  fontWeight: 600,
  whiteSpace: 'nowrap'
}

const closeBtn = {
  position: 'absolute',
  top: 8,
  right: 8,
  width: 32,
  height: 32,
  display: 'grid',
  placeItems: 'center',
  border: 'none',
  borderRadius: 4,
  background: 'rgba(0,0,0,0.6)',
  color: '#fff',
  cursor: 'pointer'
}
