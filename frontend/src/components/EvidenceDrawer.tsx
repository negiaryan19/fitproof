import { useEffect,useRef } from 'react'
import { X, ArrowUpRight, Quote, ShieldCheck } from 'lucide-react'
import type { Check,Run } from '../types'
import { pretty,safeUrl } from '../lib/api'
export default function EvidenceDrawer({check,run,onClose}:{check:Check;run:Run;onClose:()=>void}) {
 const dialog=useRef<HTMLDialogElement>(null)
 useEffect(()=>{const element=dialog.current;if(element&&!element.open)element.showModal()},[])
 const facts=run.facts.filter(f=>check.fact_ids.includes(f.id))
 return <dialog ref={dialog} className="evidence-dialog" onClose={onClose} onClick={e=>{if(e.target===e.currentTarget)onClose()}} aria-labelledby="evidence-heading">
   <div className="drawer-inner"><div className="row-between"><div className="eyebrow">THE EVIDENCE</div><button className="icon-button" onClick={onClose} aria-label="Close evidence"><X size={21}/></button></div>
   <h2 id="evidence-heading">{check.status==='conflict'?'Why this part was rejected':check.label}</h2><p className={'status-text '+check.status}>{check.status==='pass'?'Matches this check':check.status==='conflict'?'Documented conflict':'Information needed'}</p>
   <div className="comparison"><div><span>REQUIREMENT</span><strong>{pretty(check.required)}</strong></div><div><span>OBSERVED</span><strong>{pretty(check.observed)}</strong></div></div>
   <p className="evidence-reason">{check.explanation}</p>
   <div className="drawer-divider"/><h3>Supporting sources</h3>
   {facts.length?facts.map(f=>{const source=run.sources.find(s=>s.id===f.source_id);if(!source)return null;return <article className="source-card" key={f.id}>
     <div className="row-between"><span className="source-type"><ShieldCheck size={13}/>{source.publisher}</span><span className="tiny-label">{source.source_type}</span></div>
     <p className="source-subject">{f.subject}</p><Quote size={17}/><blockquote>{f.evidence_span}</blockquote>
     <div className="source-meta"><span>{source.origin==='replay'?'Recorded':'Retrieved'} {new Date(source.retrieved_at).toLocaleDateString('en-IN',{day:'numeric',month:'short',year:'numeric'})}</span><a href={safeUrl(source.url)} target="_blank" rel="noreferrer">Open original <ArrowUpRight size={13}/></a></div>
   </article>}):<p className="empty-evidence">No verified source supports this check yet. User-provided configuration may be needed.</p>}
   <p className="drawer-note">A supported excerpt establishes what the source says. Results cover the displayed checks and do not guarantee installation success.</p>
   </div>
 </dialog>
}
