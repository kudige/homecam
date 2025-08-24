import React, { useEffect, useState } from 'react'
import API from './api'
import CameraGrid from './components/CameraGrid'
import RecordingBrowser from './components/RecordingBrowser'

export default function App(){
  const [cameras, setCameras] = useState([])
  const [selected, setSelected] = useState(null)
  const [view, setView] = useState('grid') // 'grid' | 'recordings'

  async function refresh(){ setCameras(await API.getCameras()) }
  useEffect(() => { refresh() }, [])

  return (
    <>
      <header className="row">
        <div className="row" style={{justifyContent:'space-between', width:'100%'}}>
          <h2 style={{margin:0}}>HomeCam</h2>
          <div className="row" style={{gap:8}}>
            <button className="btn secondary" onClick={()=>setView('grid')}>Live Grid</button>
            <button className="btn secondary" onClick={()=>setView('recordings')}>Recordings</button>
            <button className="btn" onClick={refresh}>Refresh</button>
          </div>
        </div>
      </header>
      <div className="container">
        {view === 'grid' && (
          <CameraGrid cameras={cameras} onSelect={setSelected} />
        )}
        {view === 'recordings' && (
          <RecordingBrowser cameras={cameras} />
        )}
        <AddCameraPanel onAdded={refresh} />
      </div>
    </>
  )
}

function AddCameraPanel({ onAdded }){
  const [name, setName] = useState('')
  const [rtsp, setRtsp] = useState('')
  const [days, setDays] = useState(7)

  async function add(){
    if (!name || !rtsp) return
    await API.addCamera({ name, rtsp_url: rtsp, retention_days: Number(days) })
    setName(''); setRtsp(''); onAdded && onAdded()
  }

  return (
    <div className="panel" style={{marginTop:16}}>
      <div className="row" style={{gap:12, alignItems:'flex-end', flexWrap:'wrap'}}>
        <div>
          <div style={{fontSize:12, opacity:.8}}>Name</div>
          <input value={name} onChange={e=>setName(e.target.value)} placeholder="frontdoor" />
        </div>
        <div style={{flex:1, minWidth:340}}>
          <div style={{fontSize:12, opacity:.8}}>RTSP URL</div>
          <input value={rtsp} onChange={e=>setRtsp(e.target.value)} placeholder="rtsp://user:pass@host:554/stream" style={{width:'100%'}} />
        </div>
        <div>
          <div style={{fontSize:12, opacity:.8}}>Retention (days)</div>
          <input type="number" min="1" value={days} onChange={e=>setDays(e.target.value)} />
        </div>
        <button className="btn" onClick={add}>Add Camera</button>
      </div>
      <div style={{fontSize:12, opacity:.7, marginTop:8}}>After adding, click into the card to start streams the first time.</div>
    </div>
  )
}
