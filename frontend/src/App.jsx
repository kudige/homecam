import React, { useEffect, useState } from 'react'
import API from './api'
import CameraGrid from './components/CameraGrid'
import RecordingBrowser from './components/RecordingBrowser'

export default function App(){
  const [clientCams, setClientCams] = useState([])
  const [view, setView] = useState('grid') // 'grid' | 'recordings' | 'admin'

  async function refreshClient(){
	const list = await API.getCamerasClient()
	console.log(list)
	setClientCams(Array.isArray(list) ? list : [])   // <-- ensure array
  }

  return (
    <>
      <header className="row">
        <div className="row" style={{justifyContent:'space-between', width:'100%'}}>
          <h2 style={{margin:0}}>HomeCam</h2>
          <div className="row" style={{gap:8}}>
            <button className="btn secondary" onClick={()=>setView('grid')}>Live Grid</button>
            <button className="btn secondary" onClick={()=>setView('recordings')}>Recordings</button>
            <button className="btn secondary" onClick={()=>setView('admin')}>Admin</button>
            <button className="btn" onClick={refreshClient}>Refresh</button>
          </div>
        </div>
      </header>

      <div className="container">
        {view === 'grid' && <CameraGrid cameras={clientCams} />}
        {view === 'recordings' && <RecordingBrowser cameras={clientCams} />}
        {view === 'admin' && <AdminPanel onChanged={refreshClient} />}
      </div>
    </>
  )
}

function AdminPanel({ onChanged }){
  const [list, setList] = useState([])
  const [name, setName] = useState('')
  const [rtsp, setRtsp] = useState('')
  const [days, setDays] = useState(7)

  async function refresh(){ setList(await API.getCamerasAdmin()) }
  useEffect(() => { refresh() }, [])

  async function add(){
    if (!name || !rtsp) return
    await API.addCameraAdmin({ name, rtsp_url: rtsp, retention_days: Number(days) })
    setName(''); setRtsp(''); await refresh(); onChanged && onChanged()
  }

  return (
    <div className="panel" style={{marginTop:16}}>
      <h3 style={{marginTop:0}}>Manage Cameras</h3>
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
          <input type="number" min="0" value={days} onChange={e=>setDays(e.target.value)} />
        </div>
        <button className="btn" onClick={add}>Add</button>
      </div>

      <div style={{marginTop:16}}>
        {list.map(cam => (
          <div key={cam.id} className="row" style={{gap:8, marginBottom:8}}>
            <span className="pill" style={{minWidth:80}}>{cam.name}</span>
            <input style={{flex:1}} value={cam.rtsp_url} readOnly />
            <button className="btn secondary" onClick={()=>API.startCameraAdmin(cam.id).then(refresh)}>Start</button>
            <button className="btn secondary" onClick={()=>API.stopCameraAdmin(cam.id).then(refresh)}>Stop</button>
            <button className="btn secondary" onClick={()=>API.deleteCameraAdmin(cam.id).then(()=>{refresh(); onChanged && onChanged()})}>Delete</button>
          </div>
        ))}
      </div>
    </div>
  )
}
