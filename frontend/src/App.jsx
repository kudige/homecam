// Frontend shell + Admin with roles management.
// - Manage streams (add/probe)
// - Pick role sources (Auto / Manual / Disabled)
// - Grid targets (WxH) in Auto; when picking Manual grid stream we auto-apply its WxH to targets
// - Medium/High start/stop on demand

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
  const [cams, setCams] = useState([])
  const [name, setName] = useState('')
  const [rtsp, setRtsp] = useState('')
  const [days, setDays] = useState(7)
  const [expanded, setExpanded] = useState({}) // camId -> bool

  async function refresh(){ setCams(await API.getCamerasAdmin()) }
  useEffect(() => { refresh() }, [])

  async function add(){
    if (!name || !rtsp) return
    await API.addCameraAdmin({ name, rtsp_url: rtsp, retention_days: Number(days) })
    setName(''); setRtsp(''); await refresh(); onChanged && onChanged()
  }

  function toggle(id){ setExpanded(x => ({...x, [id]: !x[id]})) }

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
          <div style={{fontSize:12, opacity:.8}}>RTSP URL (master)</div>
          <input value={rtsp} onChange={e=>setRtsp(e.target.value)} placeholder="rtsp://user:pass@host:554/stream" style={{width:'100%'}} />
        </div>
        <div>
          <div style={{fontSize:12, opacity:.8}}>Retention (days, 0=off)</div>
          <input type="number" min="0" value={days} onChange={e=>setDays(e.target.value)} />
        </div>
        <button className="btn" onClick={add}>Add</button>
      </div>

      {/* Cameras list */}
      <div style={{marginTop:16}}>
        {cams.map(cam => (
          <CameraAdminRow
            key={cam.id}
            cam={cam}
            expanded={!!expanded[cam.id]}
            onToggle={()=>toggle(cam.id)}
            onRefresh={async ()=>{ await refresh(); onChanged && onChanged() }}
          />
        ))}
        {!cams.length && <div style={{opacity:.7}}>No cameras yet. Add one above.</div>}
      </div>
    </div>
  )
}

function CameraAdminRow({ cam, expanded, onToggle, onRefresh }){
  const [streams, setStreams] = useState(Array.isArray(cam.streams) ? cam.streams : [])
  const [newName, setNewName] = useState('')
  const [newUrl, setNewUrl] = useState('')

  // Role states (sync from cam)
  const [gridMode, setGridMode] = useState(cam.grid_mode || 'auto')
  const [gridStreamId, setGridStreamId] = useState(cam.grid_stream_id ?? '')
  const [gridW, setGridW] = useState(cam.grid_target_w ?? 640)
  const [gridH, setGridH] = useState(cam.grid_target_h ?? 360)

  const [mediumMode, setMediumMode] = useState(cam.medium_mode || 'auto')
  const [mediumStreamId, setMediumStreamId] = useState(cam.medium_stream_id ?? '')

  const [highMode, setHighMode] = useState(cam.high_mode || 'auto')
  const [highStreamId, setHighStreamId] = useState(cam.high_stream_id ?? '')

  const [recMode, setRecMode] = useState(cam.recording_mode || 'auto')
  const [recStreamId, setRecStreamId] = useState(cam.recording_stream_id ?? '')

  useEffect(() => {
    // resync when cam prop updates
    setStreams(Array.isArray(cam.streams) ? cam.streams : [])
    setGridMode(cam.grid_mode || 'auto')
    setGridStreamId(cam.grid_stream_id ?? '')
    setGridW(cam.grid_target_w ?? 640)
    setGridH(cam.grid_target_h ?? 360)
    setMediumMode(cam.medium_mode || 'auto')
    setMediumStreamId(cam.medium_stream_id ?? '')
    setHighMode(cam.high_mode || 'auto')
    setHighStreamId(cam.high_stream_id ?? '')
    setRecMode(cam.recording_mode || 'auto')
    setRecStreamId(cam.recording_stream_id ?? '')
  }, [cam])

  // Load/refresh streams when expanded
  useEffect(() => {
    if (!expanded) return
    // seed from cam.streams, then fetch fresh
    if (Array.isArray(cam.streams) && cam.streams.length && !streams.length) {
      setStreams(cam.streams)
    }
    (async () => { try { setStreams(await API.listStreamsAdmin(cam.id)) } catch {} })()
  }, [expanded, cam.id]) // eslint-disable-line

  async function addStream(){
    if (!newName || !newUrl) return
    await API.addStreamAdmin(cam.id, { name: newName, rtsp_url: newUrl })
    setNewName(''); setNewUrl('')
    setStreams(await API.listStreamsAdmin(cam.id))
    await onRefresh()
  }
  async function probeStream(id){
    await API.probeStreamAdmin(cam.id, id)
    setStreams(await API.listStreamsAdmin(cam.id))
  }

  // Save roles to backend
  async function saveRoles(update){
    const body = {
      grid_mode: gridMode, grid_stream_id: gridStreamId === '' ? null : Number(gridStreamId),
      grid_target_w: Number(gridW), grid_target_h: Number(gridH),
      medium_mode: mediumMode, medium_stream_id: mediumStreamId === '' ? null : Number(mediumStreamId),
      high_mode: highMode, high_stream_id: highStreamId === '' ? null : Number(highStreamId),
      recording_mode: recMode, recording_stream_id: recStreamId === '' ? null : Number(recStreamId),
      ...update
    }
    await API.updateRolesAdmin(cam.id, body)
    await onRefresh()
  }

  async function onPickGridStream(id){
	setGridStreamId(id)
	setGridMode('manual')
	const s = streams.find(x => String(x.id) === String(id))
	if (!s) return
	// If not probed yet, probe then refresh streams
	if (!s.width || !s.height) {
      await API.probeStreamAdmin(cam.id, s.id)
      const list = await API.listStreamsAdmin(cam.id)
      setStreams(list)
      const s2 = list.find(x => String(x.id) === String(id))
      if (s2 && s2.width && s2.height) { setGridW(s2.width); setGridH(s2.height) }
	} else {
      setGridW(s.width); setGridH(s.height)
	}
  }

  async function onPickManual(setId, id){
	setId(id)
	const s = streams.find(x => String(x.id) === String(id))
	if (s && (!s.width || !s.height)) {
      await API.probeStreamAdmin(cam.id, s.id)
      setStreams(await API.listStreamsAdmin(cam.id))
	}
  }

  const label = `${cam.name} (id ${cam.id})`
  return (
    <div className="panel" style={{marginTop:12}}>
      <div className="row" style={{gap:8, alignItems:'center', justifyContent:'space-between', flexWrap:'wrap'}}>
        <div className="row" style={{gap:8, alignItems:'center'}}>
          <button className="btn secondary" onClick={onToggle} title="Expand / Collapse">{expanded ? '▾' : '▸'}</button>
          <span className="pill" style={{minWidth:160}}>{label}</span>
        </div>
        <div className="row" style={{gap:8}}>
          <button className="btn secondary" onClick={()=>API.startMedium(cam.id)}>Start Medium</button>
          <button className="btn secondary" onClick={()=>API.stopMedium(cam.id)}>Stop Medium</button>
          <button className="btn secondary" onClick={()=>API.startHigh(cam.id)}>Start High</button>
          <button className="btn secondary" onClick={()=>API.stopHigh(cam.id)}>Stop High</button>
          <button className="btn secondary" onClick={()=>API.deleteCameraAdmin(cam.id).then(onRefresh)}>Delete</button>
        </div>
      </div>

      {expanded && (
        <div style={{marginTop:12, borderTop:'1px solid #1f2630', paddingTop:12}}>
          {/* Roles */}
          <div style={{display:'grid', gridTemplateColumns:'180px 1fr 1fr', gap:12, alignItems:'end'}}>
            {/* GRID */}
            <RoleRow
              title="Grid (always on)"
              mode={gridMode}
              setMode={setGridMode}
              streamId={gridStreamId}
              setStreamId={onPickGridStream}
              allowDisabled={false}
              streams={streams}
            >
              <div className="row" style={{gap:8}}>
                <div>
                  <div style={{fontSize:12, opacity:.8}}>Target W</div>
                  <input type="number" style={{width:96}} value={gridW} onChange={e=>setGridW(e.target.value)} />
                </div>
                <div>
                  <div style={{fontSize:12, opacity:.8}}>Target H</div>
                  <input type="number" style={{width:96}} value={gridH} onChange={e=>setGridH(e.target.value)} />
                </div>
                <button className="btn" onClick={()=>saveRoles({})}>Save Grid</button>
              </div>
            </RoleRow>

            {/* MEDIUM */}
            <RoleRow
              title="Medium (expanded default)"
              mode={mediumMode}
              setMode={setMediumMode}
              streamId={mediumStreamId}
			  setStreamId={(id)=>onPickManual(setMediumStreamId, id)}
              allowDisabled={true}
              streams={streams}
            >
              <button className="btn" onClick={()=>saveRoles({})}>Save Medium</button>
            </RoleRow>

            {/* HIGH */}
            <RoleRow
              title="High (expanded high-res)"
              mode={highMode}
              setMode={setHighMode}
              streamId={highStreamId}
			  setStreamId={(id)=>onPickManual(setHighStreamId, id)}
              allowDisabled={true}
              streams={streams}
            >
              <button className="btn" onClick={()=>saveRoles({})}>Save High</button>
            </RoleRow>

            {/* RECORDING */}
            <RoleRow
              title="Recording (if retention > 0)"
              mode={recMode}
              setMode={setRecMode}
              streamId={recStreamId}
			  setStreamId={(id)=>onPickManual(setRecStreamId, id)}
              allowDisabled={true}
              streams={streams}
            >
              <button className="btn" onClick={()=>saveRoles({})}>Save Recording</button>
            </RoleRow>
          </div>

          {/* Streams list + Add/Probe */}
          <div style={{marginTop:16}}>
            <div style={{display:'flex', alignItems:'center', justifyContent:'space-between', marginBottom:8}}>
              <div style={{fontWeight:600}}>Streams</div>
              <button className="btn secondary" onClick={async ()=>setStreams(await API.listStreamsAdmin(cam.id))}>Refresh</button>
            </div>
            <div style={{display:'grid', gridTemplateColumns:'1fr 1fr auto auto', gap:8, alignItems:'center'}}>
              <div style={{opacity:.8, fontSize:12}}>Name</div>
              <div style={{opacity:.8, fontSize:12}}>RTSP URL</div>
              <div style={{opacity:.8, fontSize:12}}>Meta</div>
              <div style={{opacity:.8, fontSize:12}}>Actions</div>

              {streams.map(s => (
                <React.Fragment key={s.id}>
                  <div className="pill">{s.name}{s.is_master ? ' • master' : ''}</div>
                  <input value={s.rtsp_url} readOnly style={{width:'100%'}} />
                  <div style={{fontSize:12, opacity:.9}}>
                    {s.width && s.height ? `${s.width}×${s.height}` : '—'}
                    {s.fps ? ` @ ${s.fps}fps` : ''}{s.bitrate_kbps ? ` • ${s.bitrate_kbps}kbps` : ''}
                  </div>
                  <div className="row" style={{gap:8}}>
                    <button className="btn secondary" onClick={()=>probeStream(s.id)}>Probe</button>
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

function RoleRow({ title, mode, setMode, streamId, setStreamId, allowDisabled, streams, children }){
  return (
    <>
      <div style={{fontWeight:600}}>{title}</div>
      <div className="row" style={{gap:8, alignItems:'center'}}>
        <select value={mode} onChange={e=>setMode(e.target.value)} style={{minWidth:140}}>
          <option value="auto">Auto</option>
          {allowDisabled && <option value="disabled">Disabled</option>}
          <option value="manual">Manual</option>
        </select>
        <select
          value={streamId}
          onChange={e=>setStreamId(e.target.value)}
          style={{minWidth:200}}
          disabled={mode !== 'manual'}
        >
          <option value="">(pick stream)</option>
          {streams.map(s => (
            <option key={s.id} value={s.id}>
              {s.name}{s.width && s.height ? ` — ${s.width}×${s.height}` : ''}
            </option>
          ))}
        </select>
      </div>
      <div className="row" style={{gap:8}}>
        {children}
      </div>
    </>
  )
}
