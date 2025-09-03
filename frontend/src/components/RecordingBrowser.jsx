import React, { useEffect, useState } from 'react'
import API from '../api'
import Player from './Player'
import DatePicker from './DatePicker'

export default function RecordingBrowser({ cameras }){
  const [camId, setCamId] = useState(cameras[0]?.id || null)
  const [date, setDate] = useState(() => new Date().toISOString().slice(0,10))
  const [files, setFiles] = useState([])
  const [selected, setSelected] = useState(null)

  useEffect(() => { if (cameras.length && !camId) setCamId(cameras[0].id) }, [cameras])

  async function load(){
    if (!camId || !date) return
    const items = await API.recordings(camId, date)
    setFiles(items)
    setSelected(items[0]?.path ?? null) // path is already '/api/recordings/...'
  }

  useEffect(() => { load() }, [camId, date])

  return (
    <div className="panel">
      <div className="row" style={{gap:12, marginBottom:12}}>
        <select value={camId || ''} onChange={e=>setCamId(String(e.target.value))}>
          {cameras.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
        </select>
        <DatePicker value={date} onChange={setDate} />
      </div>

      <Player src={selected} autoPlay={false} />

      <div style={{marginTop:12, display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(120px, 1fr))', gap:8}}>
        {files.map(f => (
          <button key={f.path} className="btn secondary" onClick={()=>setSelected(f.path)}>
            {formatTimeLabel(f.start_ts)}
          </button>
        ))}
        {!files.length && <div>No recordings for this date.</div>}
      </div>
    </div>
  )
}

function formatTimeLabel(ts){
  const d = new Date(ts*1000)
  return d.toTimeString().slice(0,5)
}
