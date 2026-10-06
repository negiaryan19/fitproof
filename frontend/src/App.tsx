import { useEffect, useState } from 'react'
import { ArrowUpRight, Check, FileText, GitCompareArrows, Search, ShieldCheck } from 'lucide-react'
import { api } from './lib/api'
import type { Health } from './types'
import { useInvestigation } from './hooks/useInvestigation'
import InputForm from './components/InputForm'
import Progress from './components/Progress'
import Results from './components/Results'

export default function App() {
  const [health,setHealth]=useState<Health|null>(null)
  const investigation=useInvestigation()
  useEffect(()=>{void api<Health>('/health').then(setHealth).catch(()=>{})},[])
  return <div className="app-shell">
    <header className="site-header"><button className="brand" onClick={investigation.reset} aria-label="FitProof home"><span className="brand-mark"><Check size={22} strokeWidth={3}/></span>fitproof<span className="brand-period">.</span></button><div className="header-links"><span className="scope-pill">LAPTOP RAM</span><a href="http://127.0.0.1:8017/api/docs" target="_blank" rel="noreferrer">API docs <ArrowUpRight size={14}/></a></div></header>
    <main className="main-shell">
      {investigation.error&&<div className="error-banner" role="alert">{investigation.error}</div>}
      {!investigation.run?<div className="landing-grid">
        <section className="hero"><div className="eyebrow"><span/> EVIDENCE BEFORE AN UPGRADE</div><h1>Know before<br/>you <span>buy.</span></h1><p className="hero-description">The right capacity is only the beginning.<br/>Investigate whether RAM fits your laptop,<br className="desktop-break"/> with every conclusion linked to evidence.</p>
          <div className="hero-proof"><ShieldCheck size={18}/><span>Manufacturer evidence. Clearly explained.</span></div>
          <div className="process-list">{[[SearchIcon,'Find the source','Discover manufacturer documents and exact parts.'],[GitCompareArrows,'Check the details','Compare specifications with explicit rules.'],[FileText,'Inspect the evidence','See what matches, what conflicts, and what’s unknown.']].map(([Icon,title,desc])=>{const I=Icon as typeof FileText;return <div className="process-item" key={String(title)}><I size={18}/><div><strong>{String(title)}</strong><p>{String(desc)}</p></div></div>})}</div>
          <div className="hero-footnote"><span>BUILT WITH</span><strong>SerpApi</strong><span className="separator">/</span><span>Search → evidence → decision</span></div>
        </section>
        <InputForm health={health} busy={investigation.busy} onSubmit={investigation.create}/>
      </div>:investigation.run.status==='investigating'?<Progress run={investigation.run}/>:<Results run={investigation.run} busy={investigation.busy} onReset={investigation.reset} onClarify={investigation.clarify} onOffer={investigation.addOffer}/>}
    </main>
    <footer className="site-footer"><span>KNOW THE FIT. SEE THE PROOF.</span><span>Documented checks, with uncertainty made visible.</span></footer>
  </div>
}
function SearchIcon({size=18}:{size?:number}) {return <Search size={size}/>}
