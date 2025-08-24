import React, { useEffect, useRef, useState } from 'react'
import Hls from 'hls.js'
import API from '../api'

export default function CameraCard({ cam }){
  const videoRef = useRef(null)
  const [urls, setUrls] = useState(null)

  async function ensureLive(){
    await API.startCamera(cam.id)
    const u = await API.liveUrls(cam.id)
    setUrls(u)
    return u
  }

  async function playLow(){
    const u = urls || await ensureLive()
    const url = u.low
    if (Hls.isSupported()){
      const hls = new Hls()
      hls.loadSource(url)
      hls.attachMedia(videoRef.current)
    } else {
      videoRef.current.src = url
    }
  }

  useEffect(() => { playLow() }, [])

  return (
    <div className="card">
      <h3>{cam.name}</h3>
      <video ref={videoRef} muted autoPlay playsInline controls></video>
      <div className="row" style={{padding:12, justifyContent:'space-between'}}>
        <span className="pill">id {cam.id}</span>
        <div className="row" style={{gap:8}}>
          <button className="btn secondary" onClick={ensureLive}>Start</button>
          <a className="btn" href={} target="_blank">Open High</a>
        </div>
      </div>
    </div>
  )
}
