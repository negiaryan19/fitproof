import { useState } from 'react'
import { ArrowLeft,ArrowRight,ArrowUpRight,Check as CheckIcon,AlertTriangle,HelpCircle,FileDown,Plus,ShieldCheck,SlidersHorizontal } from 'lucide-react'
import type { Run,Check,Offer } from '../types'
import { pretty,safeUrl } from '../lib/api'
import EvidenceDrawer from './EvidenceDrawer'

const label=(result:string)=>result==='CONFLICT_FOUND'?'Conflict found':result==='MATCHES_CHECKED_SPECIFICATIONS'?'Matches checked specifications':'Needs information'
const tone=(result:string)=>result==='CONFLICT_FOUND'?'conflict':result==='MATCHES_CHECKED_SPECIFICATIONS'?'pass':'unknown'
function StatusIcon({status,size=18}:{status:string;size?:number}){return status==='pass'?<CheckIcon size={size}/>:status==='conflict'?<AlertTriangle size={size}/>:<HelpCircle size={size}/>}

export default function Results({run,busy,onReset,onClarify,onOffer}:{run:Run;busy:boolean;onReset:()=>void;onClarify:(body:unknown)=>void;onOffer:(part:string)=>void}){
 const [selected,setSelected]=useState(run.offers[0]?.id)
 const [evidence,setEvidence]=useState<Check|null>(null)
 const [part,setPart]=useState('')
 const [modules,setModules]=useState(run.input.installed_modules_gb?.join(', ')||'')
 const [slots,setSlots]=useState(run.input.free_slots?.toString()||'0')
 const [unknown,setUnknown]=useState(run.input.installed_modules_gb===null)
 const [formError,setFormError]=useState('')
 const offer=run.offers.find(o=>o.id===selected)||run.offers[0]
 const checks=run.checks.filter(c=>c.offer_id===offer?.id)
 const core=checks.filter(c=>c.critical)
 const additional=checks.filter(c=>!c.critical)
 const recheck=()=>{
   const capacities=unknown?null:modules.split(',').map(x=>Number(x.trim()))
   if(capacities?.some(n=>!Number.isInteger(n)||n<1||n>256)){setFormError('Enter positive module capacities, separated by commas.');return}
   setFormError('');onClarify({installed_modules_gb:capacities,free_slots:unknown?null:Number(slots)})
 }
 const card=(check:Check)=><button className={'check-card '+check.status} key={check.id} onClick={()=>setEvidence(check)} aria-label={check.label+' evidence'}><div className="row-between"><span className="check-label">{check.label}</span><span className={'check-symbol '+check.status}><StatusIcon status={check.status}/></span></div><p className="check-values">{pretty(check.required)} <span>→</span> {pretty(check.observed)}</p><p className="check-description">{check.explanation}</p><span className="inspect-link">{check.status==='conflict'?'Why rejected?':'See evidence'} <ArrowUpRight size={13}/></span></button>
 return <section className="results">
  <div className="result-topline"><button className="text-button" onClick={onReset}><ArrowLeft size={15}/> New investigation</button><a className="secondary" href={'/api/runs/'+run.run_id+'/report'}><FileDown size={15}/> Export report</a></div>
  <div className="eyebrow">INVESTIGATION {run.status==='completed'?'COMPLETE':run.status.replaceAll('_',' ').toUpperCase()}</div>
  <h1 className="page-title">The evidence is in.</h1>
  <p className="subheading">{run.input.device_model}<span> / </span>{run.input.upgrade_action==='add_module'?'Add':'Replace all with'} {run.input.desired_capacity_gb} GB<span> / </span>{run.sources.filter(s=>s.fetch_status==='available').length} sources</p>
  {run.mode==='replay'&&<div className="replay-note"><ShieldCheck size={16}/><span><strong>Recorded evidence replay.</strong> Manufacturer excerpts and reviewed extraction fixtures. No live search, AI call or current prices.</span></div>}
  {run.errors.length>0&&<div className="notice-stack">{run.errors.map(e=><p key={e.code+e.message}>{e.message}</p>)}</div>}
  {run.status==='awaiting_clarification'&&<p className="notice-stack">Enter an exact laptop model in a new investigation, including its model suffix.</p>}
  <div className="results-layout">
   <aside className="candidates"><div className="section-caption"><span>RAM CANDIDATES</span><span>{run.offers.length} INVESTIGATED</span></div>
    {run.offers.map((o:Offer)=><button key={o.id} onClick={()=>setSelected(o.id)} aria-pressed={offer?.id===o.id} className={'offer-card '+(offer?.id===o.id?'selected':'')}><div className={'offer-status '+tone(o.result)}><StatusIcon size={14} status={tone(o.result)}/><span>{label(o.result)}</span></div><strong>{o.part_number||'Exact part unresolved'}</strong><p>{o.title}</p><div className="offer-bottom"><span>{o.price||'Price unavailable'}</span><ArrowRight size={15}/></div></button>)}
    {!run.offers.length&&<p className="empty-evidence">No candidates found. Add a manufacturer part number below.</p>}
    <form className="add-part" onSubmit={e=>{e.preventDefault();if(part.trim().length>=3){onOffer(part.trim());setPart('')}}}><label className="field">Investigate another exact part<input value={part} onChange={e=>setPart(e.target.value)} placeholder="Manufacturer part number" required minLength={3} maxLength={100}/></label><button className="secondary full-width" disabled={busy||run.offers.length>=5}><Plus size={15}/> Check this part</button></form>
    <div className="request-note">{run.queries_used} / {run.max_searches} search requests used</div>
   </aside>
   <div className="result-detail">
    {offer&&<><div className={'verdict '+tone(offer.result)}><div className="verdict-symbol"><StatusIcon status={tone(offer.result)} size={25}/></div><div><p className="tiny-label">CURRENT CONCLUSION</p><h2>{label(offer.result)}</h2><p>{offer.result==='CONFLICT_FOUND'?'A documented requirement conflicts with this part. Inspect the reason below.':offer.result==='NEEDS_INFORMATION'?'One or more critical checks need evidence or configuration details.':'The documented critical checks match your supplied configuration.'}</p></div></div>
    {offer.manufacturer_listed&&<div className="listed-note"><ShieldCheck size={16}/><span>Manufacturer-listed for this laptop. Configuration checks still apply.</span></div>}
    <div className="scorecard-heading"><h3>Compatibility checks</h3><span>Every conclusion has a reason.</span></div>
    <div className="checks-grid">{core.map(card)}</div>
    {additional.length>0&&<details className="additional"><summary>Additional checks · {additional.length} not established as critical requirements</summary><div className="checks-grid">{additional.map(card)}</div></details>}
    {safeUrl(offer.url)&&<a className="text-button offer-external" href={safeUrl(offer.url)} target="_blank" rel="noreferrer">Open observed listing <ArrowUpRight size={14}/><span>{new Date(offer.observed_at).toLocaleDateString('en-IN')}</span></a>}
    </>}
    <details className="configuration"><summary><SlidersHorizontal size={16}/> Update your installed configuration</summary><p>Recheck the existing evidence. These details are supplied by you.</p><label className="checkbox"><input type="checkbox" checked={unknown} onChange={e=>setUnknown(e.target.checked)}/> Configuration is unknown</label><div className="fields-two"><label className="field">Installed modules (GB each)<input value={modules} onChange={e=>setModules(e.target.value)} disabled={unknown}/></label><label className="field">Free slots<select value={slots} disabled={unknown} onChange={e=>setSlots(e.target.value)}>{[0,1,2,3,4].map(n=><option key={n}>{n}</option>)}</select></label></div>{formError&&<p className="error">{formError}</p>}<button className="secondary" onClick={recheck} disabled={busy}>Recheck configuration <ArrowRight size={14}/></button></details>
   </div>
  </div>
  {evidence&&<EvidenceDrawer check={evidence} run={run} onClose={()=>setEvidence(null)}/>}
 </section>
}

