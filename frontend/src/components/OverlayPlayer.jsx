import React from 'react'
import Player from './Player'

export default function OverlayPlayer({ open, role, src, onClose, onToggle }) {
  if (!open) return null

  const isMedium = role === 'medium'

  return (
    <div style={wrapStyle} onClick={onClose}>
      <div style={innerStyle} onClick={e => e.stopPropagation()}>
        <Player src={src} />
        <button
          onClick={onToggle}
          title={isMedium ? 'Switch to High' : 'Switch to Medium'}
          aria-label={isMedium ? 'Switch to High' : 'Switch to Medium'}
          style={toggleBtn}
        >
          {isMedium ? (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" role="img">
              <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="1.6"/>
              <path d="M16.5 16.5L21 21" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round"/>
            </svg>
          ) : (
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" role="img">
              <path d="M8 5v14l11-7-11-7z" stroke="currentColor" strokeWidth="1.6" fill="currentColor" />
            </svg>
          )}
        </button>
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

const toggleBtn = {
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

const closeBtn = {
  position: 'absolute',
  top: 8,
  right: 48,
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
