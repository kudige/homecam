import React from 'react'
import CameraCard from './CameraCard'

export default function CameraGrid({ cameras }){
  const items = Array.isArray(cameras) ? cameras : []
  return (
    <div className="grid">
      {items.map(cam => (
        <CameraCard key={cam.id} cam={cam} />
      ))}
    </div>
  )
}
