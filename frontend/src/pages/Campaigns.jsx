import { useState, useEffect } from 'react'
import * as api from '../services/api'

export default function Campaigns() {
  const [campaigns, setCampaigns] = useState([])
  const [selected, setSelected] = useState(null)
  const [detail, setDetail] = useState(null)
  const [narrative, setNarrative] = useState(null)
  const [tab, setTab] = useState('overview')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    api.getCampaigns().then(r => {
      const c = r?.campaigns || demoCampaigns
      setCampaigns(c)
      if (c.length > 0) select(c[0])
    })
  }, [])

  async function select(campaign) {
    setSelected(campaign)
    setDetail(null)
    setNarrative(null)
    setLoading(true)
    const [d, n] = await Promise.all([
      api.getCampaign(campaign.id),
      api.getScamNarrative(campaign.id),
    ])
    setDetail(d || { demo: true, ...demoCampaignDetail })
    setNarrative(n || demoNarrative)
    setLoading(false)
  }

  const riskColors = {
    CRITICAL: 'var(--critical)', HIGH: 'var(--high)',
    MEDIUM: 'var(--medium)', LOW: 'var(--low)',
  }

  return (
    <div className="fade-in" style={{ display: 'flex', gap: 20, height: 'calc(100vh - 120px)' }}>
      {/* Sidebar */}
      <div style={{ width: 300, flexShrink: 0, overflow: 'hidden auto' }}>
        <div className="card" style={{ padding: '12px 0', height: '100%' }}>
          <div style={{ padding: '0 16px 12px', borderBottom: '1px solid var(--border)' }}>
            <h3 style={{ fontSize: 14 }}>🎯 All Campaigns</h3>
            <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4 }}>
              {campaigns.length} detected — sorted by risk
            </p>
          </div>
          {(campaigns.length > 0 ? campaigns : demoCampaigns).map((c, i) => (
            <div
              key={i}
              onClick={() => select(c)}
              style={{
                padding: '12px 16px',
                cursor: 'pointer',
                borderLeft: selected?.id === c.id ? '3px solid var(--accent)' : '3px solid transparent',
                background: selected?.id === c.id ? 'var(--bg-secondary)' : 'transparent',
                borderBottom: '1px solid var(--border)',
                transition: 'all 0.15s',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <div style={{ fontSize: 12, fontWeight: 700, lineHeight: 1.4 }}>{c.name}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
                    {c.channel_count} ch · {(c.victim_estimate || 0).toLocaleString()} victims
                  </div>
                </div>
                <span className={`badge badge-${c.risk_level?.toLowerCase()}`} style={{ flexShrink: 0, marginLeft: 8 }}>
                  {c.risk_level}
                </span>
              </div>
              {c.growth_rate > 0 && (
                <div style={{ marginTop: 6, height: 2, background: 'var(--bg-primary)', borderRadius: 1, overflow: 'hidden' }}>
                  <div style={{
                    width: `${Math.min(100, c.growth_rate * 3)}%`, height: '100%',
                    background: riskColors[c.risk_level],
                  }} />
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Main detail panel */}
      <div style={{ flex: 1, overflow: 'hidden auto' }}>
        {!selected ? (
          <div className="card" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>🎯</div>
              <div>Select a campaign to view intelligence</div>
            </div>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="card" style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                <div>
                  <h2 style={{ fontSize: 20, marginBottom: 4 }}>{selected.name}</h2>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <span className={`badge badge-${selected.risk_level?.toLowerCase()}`}>{selected.risk_level}</span>
                    <span className="badge badge-low">{selected.scam_category}</span>
                    <span className="badge badge-low">Status: {selected.status || 'ACTIVE'}</span>
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                  <a href={`/network?campaign=${selected.id}`} className="btn btn-outline btn-sm">
                    🕸️ View Network
                  </a>
                  <button
                    className="btn btn-primary btn-sm"
                    onClick={() => api.getCampaignEvidence(selected.id)}
                  >
                    📋 Build Evidence
                  </button>
                </div>
              </div>

              {/* Metric row */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginTop: 16 }}>
                <MetricBox label="Channels" value={selected.channel_count} icon="📡" />
                <MetricBox label="Posts" value={selected.post_count} icon="📸" />
                <MetricBox label="Reach" value={(selected.estimated_reach || 0).toLocaleString()} icon="👥" />
                <MetricBox label="Victims (est.)" value={(selected.victim_estimate || 0).toLocaleString()} icon="🎯" color="var(--high)" />
                <MetricBox label="Risk Score" value={`${detail?.risk_score || selected.risk_score || '—'}/100`} icon="⚠️" color={riskColors[selected.risk_level]} />
              </div>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 4, marginBottom: 16 }}>
              {['overview', 'narrative', 'entities', 'growth'].map(t => (
                <button
                  key={t}
                  className={`btn ${tab === t ? 'btn-primary' : 'btn-outline'} btn-sm`}
                  onClick={() => setTab(t)}
                >
                  {t.charAt(0).toUpperCase() + t.slice(1)}
                </button>
              ))}
            </div>

            {loading && <div className="card" style={{ textAlign: 'center', padding: 40 }}>
              <div className="spinner" style={{ margin: '0 auto 8px' }} />
              <div>Loading intelligence data...</div>
            </div>}

            {!loading && tab === 'overview' && (
              <div className="card">
                <div className="card-header"><h3>📊 Campaign Overview</h3></div>
                {/* Shared entities */}
                <div style={{ marginBottom: 20 }}>
                  <h4 style={{ fontSize: 13, marginBottom: 10, color: 'var(--text-secondary)' }}>🔗 Shared Entities (linking channels)</h4>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {(selected.shared_entities || []).map((e, i) => (
                      <span key={i} style={{
                        padding: '4px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600,
                        background: 'var(--bg-secondary)', border: '1px solid var(--border)',
                        color: e.startsWith('+91') ? 'var(--high)' : e.includes('@') ? 'var(--accent)' : 'var(--text-secondary)',
                      }}>{e}</span>
                    ))}
                    {(!selected.shared_entities || selected.shared_entities.length === 0) && (
                      <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>No shared entities yet — run discovery to find links</span>
                    )}
                  </div>
                </div>
                {/* Districts */}
                <div>
                  <h4 style={{ fontSize: 13, marginBottom: 10, color: 'var(--text-secondary)' }}>📍 Districts Affected</h4>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    {(selected.districts_affected || ['Gurugram', 'Delhi', 'Noida']).map((d, i) => (
                      <span key={i} className="badge badge-medium">📍 {d}</span>
                    ))}
                  </div>
                </div>
              </div>
            )}

            {!loading && tab === 'narrative' && narrative && (
              <div className="card">
                <div className="card-header">
                  <h3>📖 Scam Playbook Reconstruction</h3>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>by {narrative.generated_by}</span>
                </div>
                <div style={{ marginBottom: 16, padding: '10px 14px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', fontSize: 12 }}>
                  <span style={{ color: 'var(--text-muted)' }}>Victim Profile:</span>{' '}
                  <span style={{ color: 'var(--text-secondary)' }}>{narrative.victim_profile}</span>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginBottom: 16 }}>
                  {(narrative.steps || []).map((step, i) => (
                    <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                      <div style={{
                        width: 24, height: 24, borderRadius: '50%', background: 'var(--accent)',
                        display: 'flex', alignItems: 'center', justifyContent: 'center',
                        fontSize: 11, fontWeight: 800, flexShrink: 0, color: 'var(--bg-primary)',
                      }}>{i + 1}</div>
                      <div style={{ fontSize: 13, lineHeight: 1.6, paddingTop: 3 }}>{step}</div>
                    </div>
                  ))}
                </div>
                <div style={{ padding: '10px 14px', borderRadius: 'var(--radius-sm)', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}>
                  <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>💸 Financial Trail</div>
                  <div style={{ fontSize: 13, fontWeight: 600, marginTop: 3, color: 'var(--high)' }}>{narrative.financial_trail}</div>
                </div>
                {narrative.estimated_loss && (
                  <div style={{ marginTop: 10, padding: '8px 14px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', fontSize: 13 }}>
                    <span style={{ color: 'var(--text-muted)' }}>Estimated Loss:</span>{' '}
                    <span style={{ fontWeight: 700, color: 'var(--critical)' }}>{narrative.estimated_loss}</span>
                    {' · '}
                    <span style={{ color: 'var(--text-muted)' }}>Confidence: {Math.round((narrative.confidence || 0.8) * 100)}%</span>
                  </div>
                )}
              </div>
            )}

            {!loading && tab === 'entities' && (
              <div className="card">
                <div className="card-header"><h3>🔎 Extracted Entities</h3></div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <EntityGroup title="📞 Phone Numbers" items={selected.shared_entities?.filter(e => e.startsWith('+91')) || ['+91-9876XXXXX']} color="var(--high)" />
                  <EntityGroup title="💳 UPI IDs" items={selected.shared_entities?.filter(e => e.includes('@') && !e.includes('t.me')) || ['scam@paytm']} color="var(--accent)" />
                  <EntityGroup title="📱 Telegram Links" items={selected.shared_entities?.filter(e => e.includes('t.me')) || ['t.me/invest_vip_tips']} color="#229ED9" />
                  <EntityGroup title="🌐 Suspicious URLs" items={[]} color="var(--medium)" />
                </div>
              </div>
            )}

            {!loading && tab === 'growth' && detail && (
              <div className="card">
                <div className="card-header"><h3>📈 30-Day Growth Forecast</h3></div>
                {(() => {
                  const g = detail.growth_forecast || demoCampaignDetail.growth_forecast
                  return (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
                      <MetricBox label="Current Channels" value={g.current_channels} icon="📡" />
                      <MetricBox label="New (24h)" value={g.new_channels_last_24h} icon="⬆️" color="var(--high)" />
                      <MetricBox label="Projected 30-day Channels" value={g.projected_30day_channels} icon="📊" color="var(--critical)" />
                      <MetricBox label="Projected Victims (30-day)" value={(g.victim_estimate_30day || 0).toLocaleString()} icon="🎯" color="var(--critical)" />
                      <div style={{ gridColumn: '1/-1', padding: '12px 16px', borderRadius: 'var(--radius-sm)', background: `${g.alert_level === 'CRITICAL' ? 'rgba(239,68,68,0.1)' : 'var(--bg-secondary)'}`, border: `1px solid ${g.alert_level === 'CRITICAL' ? 'rgba(239,68,68,0.3)' : 'var(--border)'}` }}>
                        <div style={{ fontWeight: 700, fontSize: 14 }}>
                          Alert Level: <span style={{ color: g.alert_level === 'CRITICAL' ? 'var(--critical)' : g.alert_level === 'WARNING' ? 'var(--medium)' : 'var(--accent)' }}>{g.alert_level}</span>
                        </div>
                        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 6 }}>
                          Risk Escalation Score: {g.risk_escalation_score}/100
                        </div>
                      </div>
                    </div>
                  )
                })()}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function MetricBox({ label, value, icon, color }) {
  return (
    <div style={{ padding: '12px 14px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label}</span>
        <span style={{ fontSize: 16 }}>{icon}</span>
      </div>
      <div style={{ fontSize: 20, fontWeight: 800, marginTop: 4, color: color || 'var(--text-primary)' }}>{value}</div>
    </div>
  )
}

function EntityGroup({ title, items, color }) {
  return (
    <div>
      <h4 style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>{title}</h4>
      {items.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>None detected</div>
      ) : (
        items.map((item, i) => (
          <div key={i} style={{ padding: '5px 10px', marginBottom: 4, borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', border: `1px solid var(--border)`, fontSize: 12, fontFamily: 'monospace', color }}>
            {item}
          </div>
        ))
      )}
    </div>
  )
}

// Demo data
const demoCampaigns = [
  { id: 'cpg-001', name: 'IPL Betting Ring — Gurugram', risk_level: 'CRITICAL', risk_score: 91, scam_category: 'Real Money Betting', channel_count: 23, post_count: 147, estimated_reach: 45000, victim_estimate: 4500, status: 'ACTIVE', growth_rate: 12.5, shared_entities: ['+91-98765XXXXX', 'betting@paytm', 't.me/ipl_vip_tips'], districts_affected: ['Gurugram', 'Delhi', 'Noida'] },
  { id: 'cpg-002', name: 'Fake Zerodha Network', risk_level: 'HIGH', risk_score: 72, scam_category: 'Investment Scam', channel_count: 11, post_count: 83, estimated_reach: 18000, victim_estimate: 1800, status: 'ACTIVE', growth_rate: 6.2, shared_entities: ['+91-87654XXXXX', 'invest@gpay'], districts_affected: ['Mumbai', 'Pune'] },
  { id: 'cpg-003', name: 'Digital Arrest Ring — NCR', risk_level: 'CRITICAL', risk_score: 88, scam_category: 'Digital Arrest', channel_count: 7, post_count: 42, estimated_reach: 0, victim_estimate: 320, status: 'ACTIVE', growth_rate: 8.1, shared_entities: ['+91-76543XXXXX'], districts_affected: ['Delhi', 'Gurugram', 'Ghaziabad'] },
]
const demoCampaignDetail = {
  risk_score: 88,
  growth_forecast: { current_channels: 23, new_channels_last_24h: 5, projected_30day_channels: 78, victim_estimate_30day: 22000, risk_escalation_score: 82, alert_level: 'CRITICAL' },
}
const demoNarrative = {
  scam_type: 'Real Money Betting', generated_by: 'rule_engine', confidence: 0.85,
  victim_profile: 'Sports fans, young men (18-35), college students',
  financial_trail: 'Victim → UPI/Paytm → Hawala operator → Overseas',
  estimated_loss: '₹11.25 Crore (estimated)',
  steps: [
    'Victim contacts betting tips channel on Telegram/Instagram',
    'Free "accurate" prediction shared to build credibility',
    'Victim invited to "premium paid group" (₹500–₹2,000 fee)',
    'Insider "fixing" tips shared — all show as winning',
    'Victim encouraged to bet larger amounts',
    'Tips start losing, victim asked to pay to "recover losses"',
    'Victim blocked after maximum extraction',
  ],
}
