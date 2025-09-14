import React, { useEffect, useState, useRef } from 'react'
import API from '../api'
import Player from './Player'
import DatePicker from './DatePicker'

export default function RecordingBrowser({ cameras }){
  const videoRef = useRef(null)
  const [camId, setCamId] = useState(cameras[0]?.id || null)
  const [date, setDate] = useState(() => new Date().toISOString().slice(0,10))
  const [files, setFiles] = useState([])
  const [selected, setSelected] = useState(null)
  const [clipStart, setClipStart] = useState(null)
  const [clipEnd, setClipEnd] = useState(null)
  const [clipName, setClipName] = useState('')
  const [saved, setSaved] = useState([])

  useEffect(() => { if (cameras.length && !camId) setCamId(cameras[0].id) }, [cameras])

  async function load(){
    if (!camId || !date) return
    const items = await API.recordings(camId, date)
    setFiles(items)
    setSelected(items[0]?.path ?? null) // path is already '/api/recordings/...'
  }

  useEffect(() => { load() }, [camId, date])
  useEffect(() => { setClipStart(null); setClipEnd(null) }, [selected])
  useEffect(() => { loadSaved() }, [])

  function markStart(){ if (videoRef.current) setClipStart(videoRef.current.currentTime) }
  function markEnd(){ if (videoRef.current) setClipEnd(videoRef.current.currentTime) }

  async function exportClip(save){
    if (!selected || clipStart == null || clipEnd == null) return
    const body = { start: clipStart, end: clipEnd, name: clipName, save }
    try {
      const res = await API.exportRecording(selected, body)
      if (save){
        await loadSaved()
      } else {
        const blob = res
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = (clipName || 'clip') + '.mp4'
        a.click()
        URL.revokeObjectURL(url)
      }
    } catch (e) {
      alert(`Export failed: ${e.message}`)
    }
  }

  async function loadSaved(){
    const items = await API.savedVideos()
    setSaved(items)
  }

  return (
    <div className="row" style={{alignItems:'flex-start', gap:16}}>
      <div className="panel" style={{flex:1, display:'flex', flexDirection:'column', height:'calc(100vh - 160px)'}}>
        <div className="row" style={{gap:12, marginBottom:12}}>
          <select value={camId || ''} onChange={e=>setCamId(String(e.target.value))}>
            {cameras.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
          <DatePicker value={date} onChange={setDate} />
        </div>

        <div style={{flex:1}}>
          <Player src={selected} ref={videoRef} style={{height:'100%'}} />
        </div>

        <div className="row" style={{gap:8, marginTop:8, flexWrap:'wrap', alignItems:'center'}}>
          <button className="btn secondary" onClick={markStart}>Set Start</button>
          <button className="btn secondary" onClick={markEnd}>Set End</button>
          <span>Start: {clipStart?.toFixed(1) ?? '-'}</span>
          <span>End: {clipEnd?.toFixed(1) ?? '-'}</span>
          <input value={clipName} onChange={e=>setClipName(e.target.value)} placeholder="name" />
          <button className="btn" onClick={()=>exportClip(false)}>Download</button>
          <button className="btn" onClick={()=>exportClip(true)}>Save</button>
        </div>

        <div style={{marginTop:12, display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(120px, 1fr))', gap:8}}>
          {files.map(f => (
            <button key={f.path} className="btn secondary" onClick={()=>setSelected(f.path)}>
              {formatTimeLabel(f.start_ts)}
            </button>
          ))}
          {!files.length && <div>No recordings for this date.</div>}
        </div>
      </div>

      <div className="panel" style={{width:260, maxHeight:'calc(100vh - 160px)', overflowY:'auto'}}>
        <h3 style={{marginTop:0}}>Saved Clips</h3>
        {saved.map(s => (
          <div key={s.path} style={{marginBottom:8}}>
            <a href={s.path} target="_blank" rel="noopener">{s.name}</a>
          </div>
        ))}
        {saved.length === 0 && <div>No saved videos.</div>}
      </div>
    </div>
  )
}

function formatTimeLabel(ts){
  const d = new Date(ts*1000)
  return d.toTimeString().slice(0,5)
}
