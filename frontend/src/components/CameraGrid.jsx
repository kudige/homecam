import React from 'react'
import CameraCard from './CameraCard'

export default function CameraGrid({ cameras }){
  return (
    <div className="grid">
      {cameras.map(cam => (
        <CameraCard key={cam.id} cam={cam} />
      ))}
    </div>
  )
}
