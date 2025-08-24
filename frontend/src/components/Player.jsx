import React, { useEffect, useRef } from 'react'
import Hls from 'hls.js'

export default function Player({ src, autoPlay=true }){
  const videoRef = useRef(null)
  useEffect(() => {
    if (!src || !videoRef.current) return
    if (src.endsWith('.m3u8')){
      if (Hls.isSupported()){
        const hls = new Hls()
        hls.loadSource(src)
        hls.attachMedia(videoRef.current)
        return () => hls.destroy()
      } else {
        videoRef.current.src = src
      }
    } else {
      // MP4
      videoRef.current.src = src
    }
  }, [src])
  return <video ref={videoRef} controls autoPlay={autoPlay} playsInline style={{width:'100%', height:360, background:'#000'}} />
}
