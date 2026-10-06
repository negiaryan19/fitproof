import { useState } from 'react'
import { ArrowRight, Laptop, MemoryStick, Search, Info } from 'lucide-react'
import type { Health, RunInput } from '../types'

export default function InputForm({health, busy, onSubmit}:{health:Health|null;busy:boolean;onSubmit:(input:RunInput)=>void}) {
  const [device,setDevice]=useState('')
  const [modules,setModules]=useState('8')
  const [slots,setSlots]=useState('1')
  const [unknown,setUnknown]=useState(false)
  const [capacity,setCapacity]=useState('16')
  const [part,setPart]=useState('')
  const [action,setAction]=useState<'add_module'|'replace_all'>('add_module')
  const [intent,setIntent]=useState<'discover'|'exact'>('discover')
  const [country,setCountry]=useState('IN')
  const [error,setError]=useState('')
  const submit=(mode:'live'|'replay')=>{
    setError('')
    const installed=unknown ? null : modules.split(',').map(n=>Number(n.trim()))
    if (installed?.some(n=>!Number.isInteger(n)||n<1||n>256)) {setError('Enter module capacities such as 8 or 8, 8.');return}
    if(mode==='live' && device.trim().length<3){setError('Enter your exact laptop model.');return}
    if(mode==='live' && intent==='exact' && !part.trim()){setError('Enter the manufacturer part number.');return}
    onSubmit({device_model:mode==='replay'?'Lenovo ThinkPad T480':device.trim(),installed_modules_gb:installed,
      free_slots:unknown?null:Number(slots),upgrade_action:action,desired_capacity_gb:Number(capacity),country,
      part_number:mode==='replay'?null:intent==='exact'?part.trim():null,mode})
  }
  return <section className="intake">
    <div className="section-caption"><span>START AN INVESTIGATION</span><span>01 — YOUR SETUP</span></div>
    <form onSubmit={e=>{e.preventDefault();submit('live')}} className="input-card">
      <div className="form-heading"><span className="icon-box"><Laptop size={22}/></span><div><h2>What are you upgrading?</h2><p>Start with the exact model. We’ll find the evidence.</p></div></div>
      <label className="field full">Laptop model<input value={device} onChange={e=>setDevice(e.target.value)} placeholder="e.g. Lenovo ThinkPad T480" maxLength={120}/><small>Include the model suffix. T480 and T480s are different laptops.</small></label>
      <div className="form-divider"/>
      <div className="row-between"><h3>Your current memory</h3><label className="checkbox"><input type="checkbox" checked={unknown} onChange={e=>setUnknown(e.target.checked)}/> I’m not sure</label></div>
      <div className="fields-two">
        <label className="field">Installed modules <span className="unit">(GB each)</span><input value={modules} onChange={e=>setModules(e.target.value)} disabled={unknown} placeholder="8 or 8, 8"/><small>Separate modules with a comma.</small></label>
        <label className="field">Free memory slots<select value={slots} onChange={e=>setSlots(e.target.value)} disabled={unknown}>{[0,1,2,3,4].map(n=><option key={n}>{n}</option>)}</select><small>Confirmed by you, not guessed from the model.</small></label>
      </div>
      <div className="fields-two">
        <label className="field">Upgrade action<select value={action} onChange={e=>setAction(e.target.value as typeof action)}><option value="add_module">Add one module</option><option value="replace_all">Replace all modules with one</option></select></label>
        <label className="field">New module capacity<select value={capacity} onChange={e=>setCapacity(e.target.value)}>{[4,8,16,32,48,64].map(n=><option value={n} key={n}>{n} GB</option>)}</select></label>
      </div>
      <div className="form-divider"/>
      <div className="mode-switch" aria-label="RAM investigation type"><button type="button" className={intent==='discover'?'active':''} aria-pressed={intent==='discover'} onClick={()=>setIntent('discover')}><Search size={16}/> Discover RAM</button><button type="button" className={intent==='exact'?'active':''} aria-pressed={intent==='exact'} onClick={()=>setIntent('exact')}><MemoryStick size={16}/> Check an exact part</button></div>
      {intent==='exact'&&<label className="field full">Manufacturer part number<input value={part} onChange={e=>setPart(e.target.value)} placeholder="e.g. KCP432SD8/16" maxLength={100}/><small>Use the manufacturer’s SKU, not the marketplace product ID.</small></label>}
      <label className="field market">Shopping market<select value={country} onChange={e=>setCountry(e.target.value)}><option value="IN">India</option><option value="US">United States</option><option value="GB">United Kingdom</option></select></label>
      {!health?.live_ready&&<div className="setup-note"><Info size={17}/><span>Live investigation needs backend provider setup. The recorded example below works without API keys.</span></div>}
      {error&&<p className="error" role="alert">{error}</p>}
      <button className="primary full-width" disabled={busy||!health?.live_ready} type="submit">Investigate compatibility <ArrowRight size={18}/></button>
      <p className="privacy-line">Only your model and part details are used for research.</p>
    </form>
    {health?.replay_available&&<button className="example-card" disabled={busy} onClick={()=>submit('replay')}><span className="example-icon"><MemoryStick size={22}/></span><span><strong>Try the ThinkPad T480 example</strong><small>Recorded evidence · no live search or AI call</small></span><ArrowRight size={19}/></button>}
  </section>
}

