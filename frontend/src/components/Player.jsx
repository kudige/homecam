import React, { useEffect, useRef } from 'react'
import Hls from 'hls.js'

export default function Player({ src, autoPlay=true }){
  const videoRef = useRef(null)
  useEffect(() => {
    if (!src || !videoRef.current) return
    if (src.endsWith('.m3u8')){
      if (Hls.isSupported()){
        const hls = new Hls({ startPosition:-1 })
        hls.loadSource(src)
        hls.attachMedia(videoRef.current)
        hls.on(Hls.Events.MANIFEST_PARSED, () => {
          const v = videoRef.current
          if (v && v.seekable && v.seekable.length) {
            try { v.currentTime = v.seekable.end(v.seekable.length-1) } catch {}
          }
          try { v?.play() } catch {}
        })
        return () => hls.destroy()
      } else {
        videoRef.current.src = src
        videoRef.current.play().catch(()=>{})
      }
    } else {
      // MP4
      videoRef.current.src = src
      videoRef.current.play().catch(()=>{})
    }
  }, [src])
  return <video ref={videoRef} controls autoPlay={autoPlay} playsInline style={{width:'100%', height:360, background:'#000'}} />
}
