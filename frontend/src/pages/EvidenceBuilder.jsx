/**
 * CyberLens — Evidence Builder Page
 * =====================================
 * Select a campaign → generate full evidence package →
 * preview: narrative, entities, legal sections, network graph →
 * export: PDF / JSON / PNG / I4C submission
 */

import { useState, useEffect } from 'react'
import * as api from '../services/api'
import NetworkGraph from '../components/NetworkGraph'

const BUILD_STEPS = [
  { id: 'screenshots',  label: 'Collecting screenshots',      icon: '📸', duration: 1200 },
  { id: 'ocr',          label: 'Running OCR extraction',      icon: '🔍', duration: 1400 },
  { id: 'entities',     label: 'Extracting entities',         icon: '🔗', duration: 800  },
  { id: 'network',      label: 'Mapping network graph',       icon: '🕸️', duration: 1000 },
  { id: 'narrative',    label: 'Generating scam narrative',   icon: '📖', duration: 1600 },
  { id: 'legal',        label: 'Applying legal sections',     icon: '⚖️', duration: 600  },
  { id: 'compile',      label: 'Compiling evidence package',  icon: '📋', duration: 800  },
]

export default function EvidenceBuilder() {
  const [campaigns, setCampaigns]   = useState([])
  const [selected, setSelected]     = useState(null)
  const [building, setBuilding]     = useState(false)
  const [stepsDone, setStepsDone]   = useState([])
  const [evidence, setEvidence]     = useState(null)
  const [graphData, setGraphData]   = useState(null)
  const [submitted, setSubmitted]   = useState(false)

  useEffect(() => {
    api.getCampaigns().then(r => {
      const c = r?.campaigns || demoCampaigns
      setCampaigns(c)
      setSelected(c[0])
    })
  }, [])

  async function buildEvidence() {
    if (!selected || building) return
    setBuilding(true)
    setStepsDone([])
    setEvidence(null)
    setSubmitted(false)

    // Simulate step-by-step building
    for (const step of BUILD_STEPS) {
      await new Promise(r => setTimeout(r, step.duration))
      setStepsDone(prev => [...prev, step.id])
    }

    // Fetch real data
    const [pkg, g] = await Promise.all([
      api.getCampaignEvidence(selected.id),
      api.getNetworkGraph(selected.id),
    ])
    setEvidence(pkg || demoEvidence(selected))
    setGraphData(g?.network || g?.demo_graph || null)
    setBuilding(false)
  }

  async function submitToI4C() {
    setSubmitted(true)
    // In production: POST to /api/i4c/submit with evidence package
  }

  const progress = building
    ? Math.round((stepsDone.length / BUILD_STEPS.length) * 100)
    : evidence ? 100 : 0

  return (
    <div className="fade-in">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="page-header" style={{ marginBottom: 20 }}>
        <div>
          <h2>📋 Evidence Builder</h2>
          <p className="subtitle">AI-powered evidence package generation for cyber crime investigations</p>
        </div>
        {evidence && (
          <span className="badge badge-critical" style={{ fontSize: 13 }}>
            Confidence: {Math.round((evidence.confidence_score || 0.85) * 100)}%
          </span>
        )}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: evidence ? '340px 1fr' : '1fr', gap: 20 }}>
        {/* ── Left panel: campaign select + build ────────────────── */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          {/* Campaign selector */}
          <div className="card">
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>1️⃣ Select Campaign</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {(campaigns.length > 0 ? campaigns : demoCampaigns).map((c, i) => (
                <div
                  key={i}
                  onClick={() => { setSelected(c); setEvidence(null); setStepsDone([]) }}
                  style={{
                    padding: '10px 12px', borderRadius: 'var(--radius-sm)',
                    background: selected?.id === c.id ? 'rgba(59,130,246,0.1)' : 'var(--bg-secondary)',
                    border: `1px solid ${selected?.id === c.id ? 'var(--accent)' : 'var(--border)'}`,
                    cursor: 'pointer', transition: 'all 0.15s',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div>
                      <div style={{ fontSize: 12, fontWeight: 700 }}>{c.name}</div>
                      <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 2 }}>
                        {c.channel_count} channels · {(c.victim_estimate || 0).toLocaleString()} victims
                      </div>
                    </div>
                    <span className={`badge badge-${c.risk_level?.toLowerCase()}`}>{c.risk_level}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Build button + progress */}
          <div className="card">
            <h3 style={{ fontSize: 14, marginBottom: 12 }}>2️⃣ Generate Package</h3>

            {!building && !evidence && (
              <button
                className="btn btn-primary"
                style={{ width: '100%', justifyContent: 'center', padding: '12px', fontSize: 14 }}
                onClick={buildEvidence}
                disabled={!selected}
              >
                📋 Build Evidence Package
              </button>
            )}

            {(building || evidence) && (
              <div>
                {/* Progress bar */}
                <div style={{ marginBottom: 12 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                    <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      {building ? 'Building...' : '✅ Complete'}
                    </span>
                    <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--accent)' }}>{progress}%</span>
                  </div>
                  <div style={{ height: 6, background: 'var(--bg-primary)', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{
                      width: `${progress}%`, height: '100%',
                      background: 'linear-gradient(90deg, var(--accent), var(--accent-2))',
                      borderRadius: 3, transition: 'width 0.4s ease',
                    }} />
                  </div>
                </div>

                {/* Step list */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {BUILD_STEPS.map(step => {
                    const done = stepsDone.includes(step.id)
                    const current = building && stepsDone.length < BUILD_STEPS.length &&
                      BUILD_STEPS[stepsDone.length]?.id === step.id
                    return (
                      <div key={step.id} style={{ display: 'flex', gap: 10, alignItems: 'center', opacity: done || current ? 1 : 0.35 }}>
                        <span style={{ fontSize: 12 }}>
                          {done ? '✅' : current ? <span style={{ display: 'inline-block', animation: 'spin 1s linear infinite' }}>⏳</span> : '⬜'}
                        </span>
                        <span style={{ fontSize: 11 }}>{step.icon} {step.label}</span>
                      </div>
                    )
                  })}
                </div>

                {evidence && !building && (
                  <button
                    className="btn btn-outline btn-sm"
                    style={{ width: '100%', marginTop: 12, justifyContent: 'center' }}
                    onClick={buildEvidence}
                  >🔄 Rebuild</button>
                )}
              </div>
            )}
          </div>

          {/* Export & Submit */}
          {evidence && !building && (
            <div className="card">
              <h3 style={{ fontSize: 14, marginBottom: 12 }}>3️⃣ Export & Submit</h3>
              <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                <button className="btn btn-outline btn-sm" style={{ justifyContent: 'flex-start' }}>📄 Download PDF Report</button>
                <button className="btn btn-outline btn-sm" style={{ justifyContent: 'flex-start' }}>📊 Export JSON Data</button>
                <button className="btn btn-outline btn-sm" style={{ justifyContent: 'flex-start' }}>🖼️ Export Network Graph (PNG)</button>
                <div style={{ height: 1, background: 'var(--border)', margin: '4px 0' }} />
                {submitted ? (
                  <div style={{ padding: '10px', borderRadius: 'var(--radius-sm)', background: 'rgba(16,185,129,0.1)', border: '1px solid rgba(16,185,129,0.3)', textAlign: 'center', fontSize: 13, color: 'var(--accent-3)' }}>
                    ✅ Submitted to I4C Portal
                  </div>
                ) : (
                  <button
                    className="btn btn-primary"
                    style={{ background: 'linear-gradient(135deg,#ef4444,#dc2626)', justifyContent: 'center' }}
                    onClick={submitToI4C}
                  >
                    🚨 One-Click I4C Submission
                  </button>
                )}
              </div>
            </div>
          )}
        </div>

        {/* ── Right panel: evidence preview ─────────────────────── */}
        {evidence && !building && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
            {/* Summary stats */}
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
              <EvidenceStat label="Screenshots" value={evidence.screenshots?.length || 0} icon="📸" />
              <EvidenceStat label="OCR Extractions" value={evidence.ocr_extractions?.length || 0} icon="🔍" />
              <EvidenceStat label="Entities" value={evidence.entity_list?.length || 0} icon="🔗" />
              <EvidenceStat label="Legal Sections" value={evidence.legal_sections?.length || 0} icon="⚖️" />
            </div>

            {/* Scam narrative */}
            <div className="card">
              <div className="card-header"><h3>📖 Scam Narrative</h3></div>
              <div style={{ fontSize: 13, lineHeight: 1.8, color: 'var(--text-secondary)' }}>
                {evidence.scam_narrative}
              </div>
            </div>

            {/* Entity list */}
            <div className="card">
              <div className="card-header"><h3>🔗 Extracted Entities</h3></div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {(evidence.entity_list || []).map((e, i) => (
                  <span key={i} style={{
                    padding: '4px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600,
                    background: 'var(--bg-secondary)', border: '1px solid var(--border)',
                    color: e.startsWith('+91') ? 'var(--high)' : e.includes('@') ? 'var(--accent)' : 'var(--text-secondary)',
                    fontFamily: 'monospace',
                  }}>{e}</span>
                ))}
              </div>
            </div>

            {/* Network graph */}
            <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <div className="card-header" style={{ padding: '14px 18px' }}><h3>🕸️ Network Graph</h3></div>
              <NetworkGraph
                nodes={graphData?.nodes || demoGraphFallback.nodes}
                links={graphData?.links || demoGraphFallback.links}
                onNodeClick={() => {}}
                height={360}
              />
            </div>

            {/* Legal sections */}
            <div className="card">
              <div className="card-header">
                <h3>⚖️ Applicable Legal Sections</h3>
                <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Auto-mapped by AI</span>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
                {(evidence.legal_sections || []).map((s, i) => (
                  <span key={i} className="badge badge-medium">{s}</span>
                ))}
              </div>
              {evidence.related_complaints?.length > 0 && (
                <div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>📁 Related FIRs/Complaints</div>
                  {evidence.related_complaints.map((c, i) => (
                    <div key={i} style={{ fontSize: 12, color: 'var(--text-secondary)', marginBottom: 4 }}>
                      · {c}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Role attribution */}
            {evidence.role_attribution && (
              <div className="card">
                <div className="card-header"><h3>👤 Role Attribution</h3></div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
                  {Object.entries(evidence.role_attribution).map(([role, actor], i) => (
                    <div key={i} style={{ display: 'flex', gap: 12, padding: '8px 12px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
                      <span className="badge badge-medium">{role}</span>
                      <span style={{ fontSize: 12, fontFamily: 'monospace' }}>{actor}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <div style={{ padding: '10px 14px', borderRadius: 'var(--radius-sm)', background: 'rgba(59,130,246,0.07)', border: '1px solid rgba(59,130,246,0.2)', fontSize: 11, color: 'var(--text-muted)' }}>
              Generated at: {new Date(evidence.generated_at || Date.now()).toLocaleString()} ·
              Confidence: {Math.round((evidence.confidence_score || 0.85) * 100)}%
            </div>
          </div>
        )}

        {/* Empty state when no evidence built yet */}
        {!evidence && !building && (
          <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 16, color: 'var(--text-muted)', padding: 60 }}>
            <div style={{ fontSize: 64 }}>📋</div>
            <div style={{ fontSize: 16, fontWeight: 700 }}>Evidence Package Not Built Yet</div>
            <div style={{ fontSize: 13, textAlign: 'center' }}>
              Select a campaign on the left and click<br />"Build Evidence Package" to begin
            </div>
          </div>
        )}

        {building && (
          <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 16, padding: 60 }}>
            <div className="spinner" style={{ width: 48, height: 48 }} />
            <div style={{ fontSize: 15, fontWeight: 700 }}>Building Evidence Package</div>
            <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>
              {BUILD_STEPS[stepsDone.length]?.icon} {BUILD_STEPS[stepsDone.length]?.label}...
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function EvidenceStat({ label, value, icon }) {
  return (
    <div style={{ padding: '14px', borderRadius: 'var(--radius)', background: 'var(--bg-card)', border: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label}</span>
        <span style={{ fontSize: 18 }}>{icon}</span>
      </div>
      <div style={{ fontSize: 28, fontWeight: 800 }}>{value}</div>
    </div>
  )
}

// ── Demo data ──────────────────────────────────────────────────────────────

const demoCampaigns = [
  { id: 'cpg-001', name: 'IPL Betting Ring — Gurugram', risk_level: 'CRITICAL', risk_score: 91, channel_count: 23, victim_estimate: 4500 },
  { id: 'cpg-002', name: 'Digital Arrest Ring — NCR', risk_level: 'CRITICAL', risk_score: 88, channel_count: 7, victim_estimate: 320 },
  { id: 'cpg-003', name: 'Fake Zerodha Network', risk_level: 'HIGH', risk_score: 72, channel_count: 11, victim_estimate: 1800 },
]

function demoEvidence(campaign) {
  return {
    confidence_score: 0.87,
    generated_at: new Date().toISOString(),
    screenshots: new Array(14).fill(null),
    ocr_extractions: new Array(28).fill(null),
    entity_list: ['+91-98765XXXXX', '+91-87654XXXXX', 'betting@paytm', 'invest@gpay', 't.me/ipl_vip_tips', 't.me/cricket_tips_vip'],
    legal_sections: ['IT Act §66D (Cheating by Personation)', 'IPC §420 (Cheating)', 'IPC §406 (Criminal Breach of Trust)', 'PMLA 2002 (Money Laundering)'],
    role_attribution: {
      'KINGPIN':    '@bet_king_india',
      'RECRUITER':  '@cricket_insider',
      'MONEY_MULE': 'betting@paytm',
    },
    scam_narrative: `Operation ${campaign?.name || 'IPL Betting Ring'}: A sophisticated multi-platform scam network recruiting sports fans via Telegram and Instagram with false promises of IPL match-fixing insider information. The operation uses 23 channels in a pyramid structure, with victims progressively charged higher "membership fees" before being blocked after maximum extraction. Financial flows through UPI IDs suggest Hawala connections to overseas accounts.`,
    related_complaints: [
      'FIR No. 2024/GGN/0412 — Sector 29 PS, ₹45,000 loss',
      'FIR No. 2024/GGN/0398 — Cyber Cell, ₹1,20,000 loss',
      'FIR No. 2024/GGN/0441 — DLF PS, ₹80,000 loss',
    ],
  }
}

const demoGraphFallback = {
  nodes: [
    { id: 'cpg-001', label: 'ScamCampaign', properties: { name: 'IPL Betting Ring' } },
    { id: 'ch-1', label: 'Channel', properties: { name: 't.me/ipl_vip_tips' } },
    { id: 'ph-1', label: 'PhoneNumber', properties: { value: '+91-9876XXXXX' } },
    { id: 'upi-1', label: 'UPIId', properties: { value: 'betting@paytm' } },
    { id: 'usr-1', label: 'TelegramUser', properties: { username: '@bet_operator' } },
  ],
  links: [
    { source: 'ch-1', target: 'cpg-001', type: 'BELONGS_TO' },
    { source: 'ch-1', target: 'ph-1', type: 'USES_PHONE' },
    { source: 'ch-1', target: 'upi-1', type: 'USES_UPI' },
    { source: 'usr-1', target: 'ch-1', type: 'OPERATED_BY' },
  ],
}
