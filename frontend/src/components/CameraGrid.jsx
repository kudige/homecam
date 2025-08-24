import React, { useEffect, useState } from 'react'
import API from '../api'
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
