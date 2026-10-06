export type Status = 'pass' | 'conflict' | 'unknown'
export type Health = { live_ready: boolean; missing: string[]; replay_available: boolean }
export type RunInput = { device_model: string; installed_modules_gb: number[] | null; free_slots: number | null; upgrade_action: 'add_module' | 'replace_all'; desired_capacity_gb: number; country: string; part_number: string | null; mode: 'live' | 'replay' }
export type Source = { id: string; url: string; title: string; publisher: string; source_type: string; retrieved_at: string; origin: string; fetch_status: string }
export type Fact = { id: string; source_id: string; subject: string; field: string; value: unknown; evidence_span: string; status: string; validation_reason: string }
export type Check = { id: string; offer_id: string; check_type: string; label: string; status: Status; critical: boolean; explanation: string; required: unknown; observed: unknown; source_ids: string[]; fact_ids: string[] }
export type Offer = { id: string; title: string; part_number: string | null; manufacturer: string | null; price: string | null; currency: string | null; seller: string | null; url: string | null; observed_at: string; result: string; manufacturer_listed: boolean; origin: string }
export type RunEvent = { id: number; stage: string; event_type: string; message: string; created_at: string }
export type Run = { run_id: string; input: RunInput; status: string; stage: string; sources: Source[]; facts: Fact[]; offers: Offer[]; checks: Check[]; queries_used: number; max_searches: number; events: RunEvent[]; errors: { code: string; message: string }[]; mode: 'live' | 'replay'; summary: string; updated_at: string }

