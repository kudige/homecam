// frontend/src/App.jsx
import React, { useEffect, useState } from 'react'
import API from './api'
import CameraGrid from './components/CameraGrid'
import RecordingBrowser from './components/RecordingBrowser'

export default function App(){
  const [clientCams, setClientCams] = useState([])
  const [view, setView] = useState('grid') // 'grid' | 'recordings' | 'admin'

  async function refreshClient(){
    const list = await API.getCamerasClient()
    setClientCams(Array.isArray(list) ? list : [])
  }
  useEffect(() => { refreshClient() }, [])

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

/* --------------------------- Admin Panel --------------------------- */

function AdminPanel({ onChanged }){
  const [list, setList] = useState([])
  const [name, setName] = useState('')
  const [rtsp, setRtsp] = useState('')
  const [days, setDays] = useState(7)
  const [expanded, setExpanded] = useState({})   // camId -> bool

  async function refresh(){ setList(await API.getCamerasAdmin()) }
  useEffect(() => { refresh() }, [])

  async function add(){
    if (!name || !rtsp) return
    await API.addCameraAdmin({ name, rtsp_url: rtsp, retention_days: Number(days) })
    setName(''); setRtsp(''); await refresh(); onChanged && onChanged()
  }

  function toggle(camId){
    setExpanded(prev => ({...prev, [camId]: !prev[camId]}))
  }

  return (
    <div className="panel" style={{marginTop:16}}>
      <h3 style={{marginTop:0}}>Manage Cameras</h3>

      {/* Add camera */}
      <div className="row" style={{gap:12, alignItems:'flex-end', flexWrap:'wrap'}}>
        <div>
          <div style={{fontSize:12, opacity:.8}}>Name</div>
          <input value={name} onChange={e=>setName(e.target.value)} placeholder="frontdoor" />
        </div>
        <div style={{flex:1, minWidth:340}}>
          <div style={{fontSize:12, opacity:.8}}>RTSP URL (legacy default)</div>
          <input value={rtsp} onChange={e=>setRtsp(e.target.value)} placeholder="rtsp://user:pass@host:554/stream" style={{width:'100%'}} />
        </div>
        <div>
          <div style={{fontSize:12, opacity:.8}}>Retention (days, 0=off)</div>
          <input type="number" min="0" value={days} onChange={e=>setDays(e.target.value)} />
        </div>
        <button className="btn" onClick={add}>Add</button>
      </div>

      {/* List cameras */}
      <div style={{marginTop:16}}>
        {list.map(cam => (
          <CameraAdminRow
            key={cam.id}
            cam={cam}
            expanded={!!expanded[cam.id]}
            onToggle={()=>toggle(cam.id)}
            onRefresh={async()=>{ await refresh(); onChanged && onChanged() }}
          />
        ))}
        {!list.length && <div style={{opacity:.7}}>No cameras yet. Add one above.</div>}
      </div>
    </div>
  )
}

function CameraAdminRow({ cam, expanded, onToggle, onRefresh }){
  const [streams, setStreams] = useState([])
  const [newName, setNewName] = useState('')
  const [newUrl, setNewUrl] = useState('')
  const [gridW, setGridW] = useState(cam.grid_target_w ?? 640)
  const [gridH, setGridH] = useState(cam.grid_target_h ?? 360)
  const [fullW, setFullW] = useState(cam.full_target_w ?? 1920)
  const [fullH, setFullH] = useState(cam.full_target_h ?? 1080)
  const [prefLow, setPrefLow] = useState(cam.preferred_low_stream_id ?? '')
  const [prefHigh, setPrefHigh] = useState(cam.preferred_high_stream_id ?? '')

  async function refreshStreams(){
    try{
      const list = await API.listStreamsAdmin(cam.id)
      setStreams(Array.isArray(list) ? list : [])
    }catch{ setStreams([]) }
  }

  
  useEffect(() => {
	setGridW(cam.grid_target_w ?? 640)
	setGridH(cam.grid_target_h ?? 360)
	setFullW(cam.full_target_w ?? 1920)
	setFullH(cam.full_target_h ?? 1080)
	setPrefLow(cam.preferred_low_stream_id ?? '')
	setPrefHigh(cam.preferred_high_stream_id ?? '')
  }, [cam.id, cam.grid_target_w, cam.grid_target_h, cam.full_target_w, cam.full_target_h, cam.preferred_low_stream_id, cam.preferred_high_stream_id])

  async function addStream(){
    if (!newName || !newUrl) return
    await API.addStreamAdmin(cam.id, { name: newName, rtsp_url: newUrl })
    setNewName(''); setNewUrl('')
    await refreshStreams()
    await onRefresh()
  }

  async function probe(streamId){
    await API.probeStreamAdmin(cam.id, streamId)
    await refreshStreams()
  }

  async function savePrefs(){
    await API.updateCameraAdmin(cam.id, {
      preferred_low_stream_id: prefLow === '' ? null : Number(prefLow),
      preferred_high_stream_id: prefHigh === '' ? null : Number(prefHigh),
      grid_target_w: Number(gridW), grid_target_h: Number(gridH),
      full_target_w: Number(fullW), full_target_h: Number(fullH),
    })
    await onRefresh()
  }

  const label = `${cam.name} (id ${cam.id})`

  return (
    <div className="panel" style={{marginTop:12}}>
      <div className="row" style={{gap:8, alignItems:'center', justifyContent:'space-between', flexWrap:'wrap'}}>
        <div className="row" style={{gap:8, alignItems:'center'}}>
          <button className="btn secondary" onClick={onToggle} title="Expand / Collapse">{expanded ? '▾' : '▸'}</button>
          <span className="pill" style={{minWidth:160}}>{label}</span>
          <input style={{flex:1, minWidth:320}} value={cam.rtsp_url} readOnly />
        </div>
        <div className="row" style={{gap:8}}>
          <button className="btn secondary" onClick={()=>API.startCameraAdmin(cam.id).then(onRefresh)}>Start</button>
          <button className="btn secondary" onClick={()=>API.stopCameraAdmin(cam.id).then(onRefresh)}>Stop</button>
          <button className="btn secondary" onClick={()=>API.deleteCameraAdmin(cam.id).then(onRefresh)}>Delete</button>
        </div>
      </div>

      {expanded && (
        <div style={{marginTop:12, borderTop:'1px solid #1f2630', paddingTop:12}}>
          {/* Targets & Preferred Streams */}
          <div className="row" style={{gap:16, flexWrap:'wrap', alignItems:'flex-end'}}>
            <div>
              <div style={{fontSize:12, opacity:.8}}>Grid target (WxH)</div>
              <div className="row" style={{gap:8}}>
                <input type="number" style={{width:96}} value={gridW} onChange={e=>setGridW(e.target.value)} />
                <input type="number" style={{width:96}} value={gridH} onChange={e=>setGridH(e.target.value)} />
              </div>
            </div>
            <div>
              <div style={{fontSize:12, opacity:.8}}>Full target (WxH)</div>
              <div className="row" style={{gap:8}}>
                <input type="number" style={{width:96}} value={fullW} onChange={e=>setFullW(e.target.value)} />
                <input type="number" style={{width:96}} value={fullH} onChange={e=>setFullH(e.target.value)} />
              </div>
            </div>
            <div>
              <div style={{fontSize:12, opacity:.8}}>Preferred Low Stream</div>
              <select value={prefLow} onChange={e=>setPrefLow(e.target.value)} style={{minWidth:160}}>
                <option value="">(auto)</option>
                {streams.map(s => <option key={s.id} value={s.id}>{streamLabel(s)}</option>)}
              </select>
            </div>
            <div>
              <div style={{fontSize:12, opacity:.8}}>Preferred High Stream</div>
              <select value={prefHigh} onChange={e=>setPrefHigh(e.target.value)} style={{minWidth:160}}>
                <option value="">(auto)</option>
                {streams.map(s => <option key={s.id} value={s.id}>{streamLabel(s)}</option>)}
              </select>
            </div>
            <button className="btn" onClick={savePrefs}>Save Preferences</button>
          </div>

          {/* Streams list */}
          <div style={{marginTop:16}}>
            <div style={{fontWeight:600, marginBottom:8}}>Streams</div>
            <div style={{display:'grid', gridTemplateColumns:'1fr 1fr auto auto', gap:8, alignItems:'center'}}>
              <div style={{opacity:.8, fontSize:12}}>Name</div>
              <div style={{opacity:.8, fontSize:12}}>RTSP URL (read-only)</div>
              <div style={{opacity:.8, fontSize:12}}>Meta</div>
              <div style={{opacity:.8, fontSize:12}}>Actions</div>

              {streams.map(s => (
                <React.Fragment key={s.id}>
                  <div className="pill">{s.name}</div>
                  <input value={s.rtsp_url} readOnly style={{width:'100%'}} />
                  <div style={{fontSize:12, opacity:.9}}>
                    {s.width && s.height ? `${s.width}×${s.height}` : '—'}{s.fps ? ` @ ${s.fps}fps` : ''}{s.bitrate_kbps ? ` • ${s.bitrate_kbps}kbps` : ''}
                  </div>
                  <div className="row" style={{gap:8}}>
                    <button className="btn secondary" onClick={()=>probe(s.id)}>Probe</button>
                  </div>
                </React.Fragment>
              ))}
            </div>

            {/* Add stream */}
            <div className="row" style={{gap:12, alignItems:'flex-end', marginTop:12, flexWrap:'wrap'}}>
              <div>
                <div style={{fontSize:12, opacity:.8}}>New Stream Name</div>
                <input value={newName} onChange={e=>setNewName(e.target.value)} placeholder="sub/main/720p" />
              </div>
              <div style={{flex:1, minWidth:360}}>
                <div style={{fontSize:12, opacity:.8}}>New Stream RTSP URL</div>
                <input value={newUrl} onChange={e=>setNewUrl(e.target.value)} placeholder="rtsp://user:pass@host:554/sub" style={{width:'100%'}} />
              </div>
              <button className="btn" onClick={addStream}>Add & Probe</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

function streamLabel(s){
  const wh = (s.width && s.height) ? `${s.width}×${s.height}` : 'unknown'
  return `${s.name} (${wh}${s.fps ? ` @ ${s.fps}fps` : ''})`
}
