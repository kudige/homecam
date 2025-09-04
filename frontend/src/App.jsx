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

  // Combined role selectors: value is 'auto', 'disabled', or 'stream:<id>'
  const [gridSel,   setGridSel]   = useState(selFrom(cam.grid_mode, cam.grid_stream_id, false))
  const [mediumSel, setMediumSel] = useState(selFrom(cam.medium_mode, cam.medium_stream_id, true))
  const [highSel,   setHighSel]   = useState(selFrom(cam.high_mode, cam.high_stream_id, true))
  const [recSel,    setRecSel]    = useState(selFrom(cam.recording_mode, cam.recording_stream_id, true))

  const [gridW, setGridW] = useState(cam.grid_target_w ?? 640)
  const [gridH, setGridH] = useState(cam.grid_target_h ?? 360)
  
  const [pending, setPending] = useState({ medium:false, high:false })
  
  // Role running flags for Medium/High (polled)
  const [running, setRunning] = useState({ medium:false, high:false })
  useEffect(() => {
	if (!expanded) return
	const poll = async () => {
      try {
		const st = await API.getCameraStatusAdmin(cam.id)
		const roles = st?.roles || {}
		setRunning({
          medium: !!roles.medium,
          high:   !!roles.high,
		})
      } catch {
		// if status call fails, don't flip UI unexpectedly
      }
	}
	poll()
	const t = setInterval(poll, 5000)
	return () => clearInterval(t)
  }, [expanded, cam.id])
  
  // Resync from cam
  useEffect(() => {
    setStreams(Array.isArray(cam.streams) ? cam.streams : [])
    setGridSel(selFrom(cam.grid_mode, cam.grid_stream_id, false))
    setMediumSel(selFrom(cam.medium_mode, cam.medium_stream_id, true))
    setHighSel(selFrom(cam.high_mode, cam.high_stream_id, true))
    setRecSel(selFrom(cam.recording_mode, cam.recording_stream_id, true))
    setGridW(cam.grid_target_w ?? 640)
    setGridH(cam.grid_target_h ?? 360)
  }, [cam])

  // Load/refresh streams on expand (seed first then fetch)
  useEffect(() => {
    if (!expanded) return
    if (Array.isArray(cam.streams) && cam.streams.length && !streams.length) setStreams(cam.streams)
    ;(async () => { try { setStreams(await API.listStreamsAdmin(cam.id)) } catch {} })()
  }, [expanded, cam.id]) // eslint-disable-line

  // unified dropdown change handlers
  async function onChangeGrid(val){
    setGridSel(val)
    if (val.startsWith('stream:')){
      const id = val.split(':')[1]
      const s = await ensureProbed(cam.id, streams, id, setStreams)
      if (s && s.width && s.height){ setGridW(s.width); setGridH(s.height) }
    }
  }
  async function onChangeRole(setter, val){
    setter(val)
    if (val.startsWith('stream:')){
      const id = val.split(':')[1]
      await ensureProbed(cam.id, streams, id, setStreams)
    }
  }

  async function saveAll(){
    const body = {
      // grid
      ...bodyFor('grid', gridSel, gridW, gridH),
      // medium / high / recording
      ...bodyFor('medium', mediumSel),
      ...bodyFor('high',   highSel),
      ...bodyFor('recording', recSel),
    }
    await API.updateRolesAdmin(cam.id, body)
    await onRefresh()
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
          <button className="btn secondary" onClick={()=>API.deleteCameraAdmin(cam.id).then(onRefresh)}>Delete</button>
        </div>
      </div>

      {expanded && (
        <div style={{marginTop:12, borderTop:'1px solid #1f2630', paddingTop:12}}>
          {/* Roles grid */}
          <div style={{display:'grid', gridTemplateColumns:'160px 1fr auto', gap:12, alignItems:'end'}}>
            <RoleLine
              title="Grid (always on)"
              value={gridSel}
              onChange={onChangeGrid}
              streams={streams}
              allowDisabled={false}
            >
              <div className="row" style={{gap:8}}>
                <input type="number" style={{width:96}} value={gridW} onChange={e=>setGridW(e.target.value)} />
                <input type="number" style={{width:96}} value={gridH} onChange={e=>setGridH(e.target.value)} />
                <span className="pill">Target WxH</span>
              </div>
            </RoleLine>

            <RoleLine
              title="Medium"
              value={mediumSel}
              onChange={(v)=>onChangeRole(setMediumSel, v)}
              streams={streams}
              allowDisabled={true}
            >
			  {running.medium
			   ? <button className="btn secondary" disabled={pending.medium}
						 onClick={async ()=>{
						   setPending(p=>({...p, medium:true}))
						   await API.stopMedium(cam.id)
						   const st = await API.getCameraStatusAdmin(cam.id)
						   setRunning(r => ({...r, medium: !!(st?.roles?.medium)}))
						   setPending(p=>({...p, medium:false}))
						 }}>
				   Stop
				 </button>
			   : <button className="btn" disabled={pending.medium}
						 onClick={async ()=>{
						   setPending(p=>({...p, medium:true}))
						   await API.startMedium(cam.id)
						   const st = await API.getCameraStatusAdmin(cam.id)
						   setRunning(r => ({...r, medium: !!(st?.roles?.medium)}))
						   setPending(p=>({...p, medium:false}))
						 }}>
				   Start
				 </button>}
            </RoleLine>

            <RoleLine
              title="High"
              value={highSel}
              onChange={(v)=>onChangeRole(setHighSel, v)}
              streams={streams}
              allowDisabled={true}
            >
			  {running.high
			   ? <button className="btn secondary" disabled={pending.high}
						 onClick={async ()=>{
						   setPending(p=>({...p, high:true}))
						   await API.stopHigh(cam.id)
						   const st = await API.getCameraStatusAdmin(cam.id)
						   setRunning(r => ({...r, high: !!(st?.roles?.high)}))
						   setPending(p=>({...p, high:false}))
						 }}>
				   Stop
				 </button>
			   : <button className="btn" disabled={pending.high}
						 onClick={async ()=>{
						   setPending(p=>({...p, high:true}))
						   await API.startHigh(cam.id)
						   const st = await API.getCameraStatusAdmin(cam.id)
						   setRunning(r => ({...r, high: !!(st?.roles?.high)}))
						   setPending(p=>({...p, high:false}))
						 }}>
				   Start
				 </button>}
            </RoleLine>

            <RoleLine
              title="Recording (via retention)"
              value={recSel}
              onChange={(v)=>onChangeRole(setRecSel, v)}
              streams={streams}
              allowDisabled={true}
            >
              <span className="pill">Toggle via retention</span>
            </RoleLine>
          </div>

          <div className="row" style={{gap:8, marginTop:12}}>
            <button className="btn" onClick={saveAll}>Save</button>
            <button className="btn secondary" onClick={async ()=>setStreams(await API.listStreamsAdmin(cam.id))}>Refresh Streams</button>
          </div>

          {/* Streams table + add */}
          <StreamsEditor cam={cam} streams={streams} setStreams={setStreams} />
        </div>
      )}
    </div>
  )
}

/* ---- Helpers for Admin ---- */

// Convert current selector value to role body fields
function bodyFor(role, sel, gridW, gridH){
  const isGrid = role === 'grid'
  if (sel === 'auto') {
    return isGrid
      ? { grid_mode:'auto', grid_stream_id:null, grid_target_w:Number(gridW), grid_target_h:Number(gridH) }
      : { [`${role}_mode`]:'auto', [`${role}_stream_id`]:null }
  }
  if (sel === 'disabled') {
    return isGrid
      ? { grid_mode:'auto', grid_stream_id:null } // grid can't be disabled; fallback to auto
      : { [`${role}_mode`]:'disabled', [`${role}_stream_id`]:null }
  }
  const id = Number(sel.split(':')[1])
  return isGrid
    ? { grid_mode:'manual', grid_stream_id:id, grid_target_w:Number(gridW), grid_target_h:Number(gridH) }
    : { [`${role}_mode`]:'manual', [`${role}_stream_id`]:id }
}

// Build select value from mode + stream_id
function selFrom(mode, streamId, allowDisabled){
  if (mode === 'manual' && streamId) return `stream:${streamId}`
  if (mode === 'disabled' && allowDisabled) return 'disabled'
  return 'auto'
}

// Ensure a stream is probed; refresh list if needed and return the stream
async function ensureProbed(camId, streams, id, setStreams){
  let s = streams.find(x => String(x.id) === String(id))
  if (s && s.width && s.height) return s
  await API.probeStreamAdmin(camId, id)
  const list = await API.listStreamsAdmin(camId)
  setStreams(list)
  return list.find(x => String(x.id) === String(id))
}

/* ---- Small presentational components ---- */

function RoleLine({ title, value, onChange, streams, allowDisabled, children }){
  return (
    <>
      <div style={{fontWeight:600}}>{title}</div>
      <div className="row" style={{gap:8, alignItems:'center'}}>
        <select value={value} onChange={e=>onChange(e.target.value)} style={{minWidth:240}}>
          <option value="auto">Auto</option>
          {allowDisabled && <option value="disabled">Disabled</option>}
          {streams.map(s => (
            <option key={s.id} value={`stream:${s.id}`}>
              {s.name}{s.width && s.height ? ` — ${s.width}×${s.height}` : ''}
            </option>
          ))}
        </select>
      </div>
      <div className="row" style={{gap:8}}>{children}</div>
    </>
  )
}

function StreamsEditor({ cam, streams, setStreams }){
  const [newName, setNewName] = useState('')
  const [newUrl, setNewUrl]   = useState('')

  async function addStream(){
    if (!newName || !newUrl) return
    await API.addStreamAdmin(cam.id, { name:newName, rtsp_url:newUrl })
    setNewName(''); setNewUrl('')
    setStreams(await API.listStreamsAdmin(cam.id))
  }
  async function probe(id){
    await API.probeStreamAdmin(cam.id, id)
    setStreams(await API.listStreamsAdmin(cam.id))
  }

  return (
    <>
      <div style={{marginTop:16}}>
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
                <button className="btn secondary" onClick={()=>probe(s.id)}>Probe</button>
              </div>
            </React.Fragment>
          ))}
        </div>
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
    </>
  )
}
