import { Check, LoaderCircle, Circle, FileSearch } from 'lucide-react'
import type { Run } from '../types'
const stages=[['validate','Checking your setup'],['device','Finding laptop documentation'],['discover','Discovering exact-part candidates'],['parts','Extracting RAM specifications'],['audit','Validating source evidence'],['checks','Running compatibility checks']]
export default function Progress({run}:{run:Run}) {
  const current=stages.findIndex(([key])=>key===run.stage)
  return <section className="progress-view" aria-live="polite"><div className="eyebrow">INVESTIGATION IN PROGRESS</div><h1 className="page-title">Following the evidence.</h1><p className="subheading">{run.input.device_model} · {run.input.desired_capacity_gb} GB upgrade</p>
    {run.mode==='replay'&&<div className="replay-note">Recorded evidence replay · no live provider calls</div>}
    <div className="progress-panel">{stages.map(([key,label],i)=>{const seen=run.events.some(e=>e.stage===key);const active=run.stage===key;return <div key={key} className={'progress-step '+(active?'active':'')}>{active?<LoaderCircle size={20} className="spin"/>:seen&&i<current?<Check size={20}/>:<Circle size={17}/>}<span>{label}</span>{active&&<small>Working</small>}</div>})}
      <div className="progress-metrics"><span><FileSearch size={15}/> {run.sources.filter(s=>s.fetch_status==='available').length} sources loaded</span><span>{run.queries_used} / {run.max_searches} search requests</span></div>
    </div><p className="live-message" role="status">{run.events.at(-1)?.message || 'Starting investigation…'}</p>
  </section>
}

