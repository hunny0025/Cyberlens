/**
 * CyberLens — Campaign Intelligence Page
 * =========================================
 * Full list of all detected campaigns with network graph, evidence builder,
 * scam narrative, growth forecast, and entity breakdown.
 */

import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import * as api from '../services/api'
import NetworkGraph from '../components/NetworkGraph'

export default function CampaignIntelligence() {
  const navigate = useNavigate()
  const [campaigns, setCampaigns]     = useState([])
  const [selected, setSelected]       = useState(null)
  const [detail, setDetail]           = useState(null)
  const [narrative, setNarrative]     = useState(null)
  const [graphData, setGraphData]     = useState(null)
  const [evidence, setEvidence]       = useState(null)
  const [tab, setTab]                 = useState('overview')
  const [loading, setLoading]         = useState(false)
  const [buildingEvidence, setBuildingEvidence] = useState(false)
  const [filterRisk, setFilterRisk]   = useState('ALL')
  const [searchText, setSearchText]   = useState('')

  useEffect(() => {
    api.getCampaigns().then(r => {
      const c = r?.campaigns || demoCampaigns
      setCampaigns(c)
      if (c.length > 0) selectCampaign(c[0])
    })
  }, [])

  async function selectCampaign(campaign) {
    setSelected(campaign)
    setDetail(null); setNarrative(null); setGraphData(null); setEvidence(null)
    setLoading(true)
    const [d, n, g] = await Promise.all([
      api.getCampaign(campaign.id),
      api.getScamNarrative(campaign.id),
      api.getNetworkGraph(campaign.id),
    ])
    setDetail(d || { demo: true, ...demoCampaignDetail })
    setNarrative(n || demoNarrative)
    setGraphData(g?.network || g?.demo_graph || demoGraph)
    setLoading(false)
  }

  async function buildEvidence() {
    if (!selected) return
    setBuildingEvidence(true)
    const pkg = await api.getCampaignEvidence(selected.id)
    setEvidence(pkg || demoEvidence)
    setBuildingEvidence(false)
    setTab('evidence')
  }

  const riskColors = {
    CRITICAL: 'var(--critical)', HIGH: 'var(--high)',
    MEDIUM: 'var(--medium)', LOW: 'var(--low)',
  }

  const visibleCampaigns = (campaigns.length > 0 ? campaigns : demoCampaigns)
    .filter(c => filterRisk === 'ALL' || c.risk_level === filterRisk)
    .filter(c => !searchText || c.name.toLowerCase().includes(searchText.toLowerCase()))

  return (
    <div className="fade-in" style={{ display: 'flex', gap: 20, height: 'calc(100vh - 120px)' }}>

      {/* ── Sidebar: campaign list ──────────────────────────────── */}
      <div style={{ width: 300, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
        <div className="card" style={{ padding: '12px 14px' }}>
          <h3 style={{ fontSize: 14, marginBottom: 10 }}>🎯 All Campaigns</h3>
          <input
            className="form-input"
            type="text"
            placeholder="Search campaigns..."
            value={searchText}
            onChange={e => setSearchText(e.target.value)}
            style={{ marginBottom: 8, fontSize: 12 }}
          />
          <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
            {['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(r => (
              <button
                key={r}
                className={`btn btn-sm ${filterRisk === r ? 'btn-primary' : 'btn-outline'}`}
                style={{ fontSize: 10, padding: '2px 8px' }}
                onClick={() => setFilterRisk(r)}
              >{r}</button>
            ))}
          </div>
          <div style={{ marginTop: 8, fontSize: 11, color: 'var(--text-muted)' }}>
            {visibleCampaigns.length} campaigns
          </div>
        </div>

        <div className="card" style={{ padding: '8px 0', flex: 1, overflow: 'hidden auto' }}>
          {visibleCampaigns.map((c, i) => (
            <CampaignSidebarItem
              key={i}
              campaign={c}
              selected={selected?.id === c.id}
              onClick={() => selectCampaign(c)}
              riskColors={riskColors}
            />
          ))}
          {visibleCampaigns.length === 0 && (
            <div style={{ padding: 20, textAlign: 'center', color: 'var(--text-muted)', fontSize: 13 }}>
              No campaigns match filter
            </div>
          )}
        </div>
      </div>

      {/* ── Main detail panel ──────────────────────────────────── */}
      <div style={{ flex: 1, overflow: 'hidden auto' }}>
        {!selected ? (
          <div className="card" style={{ height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
            <div style={{ textAlign: 'center', color: 'var(--text-muted)' }}>
              <div style={{ fontSize: 52, marginBottom: 12 }}>🎯</div>
              <div style={{ fontSize: 15, fontWeight: 600 }}>Select a campaign to view intelligence</div>
            </div>
          </div>
        ) : (
          <>
            {/* Header card */}
            <div className="card" style={{ marginBottom: 16 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
                <div>
                  <h2 style={{ fontSize: 22, marginBottom: 6 }}>{selected.name}</h2>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                    <span className={`badge badge-${selected.risk_level?.toLowerCase()}`}>{selected.risk_level}</span>
                    <span className="badge badge-low">{selected.scam_category}</span>
                    <span className="badge badge-low">📅 {selected.start_date?.slice(0,10) || 'Active'}</span>
                    {selected.growth_rate > 5 && (
                      <span className="badge badge-high">📈 Growing +{selected.growth_rate}%</span>
                    )}
                  </div>
                </div>
                <div style={{ display: 'flex', gap: 8, flexShrink: 0 }}>
                  <button className="btn btn-outline btn-sm" onClick={() => setTab('graph')}>
                    🕸️ View Network
                  </button>
                  <button className="btn btn-primary btn-sm" onClick={buildEvidence}>
                    {buildingEvidence ? '⏳ Building...' : '📋 Build Evidence'}
                  </button>
                </div>
              </div>

              {/* Metric grid */}
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5,1fr)', gap: 12 }}>
                <MetricBox label="Channels" value={selected.channel_count} icon="📡" />
                <MetricBox label="Posts" value={selected.post_count || '—'} icon="📸" />
                <MetricBox label="Reach" value={(selected.estimated_reach || 0).toLocaleString()} icon="👥" />
                <MetricBox label="Victims" value={(selected.victim_estimate || 0).toLocaleString()} icon="⚠️" color="var(--high)" />
                <MetricBox label="Risk Score" value={`${selected.risk_score || '—'}/100`} icon="🎯" color={riskColors[selected.risk_level]} />
              </div>
            </div>

            {/* Tabs */}
            <div style={{ display: 'flex', gap: 6, marginBottom: 16, flexWrap: 'wrap' }}>
              {[
                { key: 'overview', label: '📊 Overview' },
                { key: 'narrative', label: '📖 Scam Story' },
                { key: 'graph', label: '🕸️ Network' },
                { key: 'entities', label: '🔎 Entities' },
                { key: 'growth', label: '📈 Growth' },
                { key: 'evidence', label: '📋 Evidence' },
              ].map(t => (
                <button
                  key={t.key}
                  className={`btn btn-sm ${tab === t.key ? 'btn-primary' : 'btn-outline'}`}
                  onClick={() => setTab(t.key)}
                >{t.label}</button>
              ))}
            </div>

            {loading && (
              <div className="card" style={{ textAlign: 'center', padding: 40 }}>
                <div className="spinner" style={{ margin: '0 auto 10px' }} />
                <div style={{ color: 'var(--text-secondary)' }}>Loading campaign intelligence...</div>
              </div>
            )}

            {/* ── Tab: Overview ──────────────────────────────── */}
            {!loading && tab === 'overview' && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div className="card">
                  <div className="card-header"><h3>🔗 Shared Entities</h3></div>
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 16 }}>
                    {(selected.shared_entities || []).map((e, i) => (
                      <EntityTag key={i} value={e} />
                    ))}
                    {(!selected.shared_entities?.length) && (
                      <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>No shared entities detected</span>
                    )}
                  </div>
                  <div>
                    <h4 style={{ fontSize: 13, color: 'var(--text-muted)', marginBottom: 8 }}>📍 Districts Affected</h4>
                    <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                      {(selected.districts_affected || ['Gurugram', 'Delhi']).map((d, i) => (
                        <span key={i} className="badge badge-medium">📍 {d}</span>
                      ))}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* ── Tab: Scam Narrative ───────────────────────── */}
            {!loading && tab === 'narrative' && (
              <div className="card">
                <div className="card-header">
                  <h3>📖 Scam Playbook Reconstruction</h3>
                  <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>by {narrative?.generated_by || 'AI'}</span>
                </div>

                {narrative && (
                  <>
                    <div style={{ marginBottom: 16, padding: '10px 14px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', fontSize: 13 }}>
                      <span style={{ color: 'var(--text-muted)' }}>Victim Profile: </span>
                      <span>{narrative.victim_profile}</span>
                    </div>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginBottom: 16 }}>
                      {(narrative.steps || []).map((step, i) => (
                        <div key={i} style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
                          <div style={{
                            width: 26, height: 26, borderRadius: '50%',
                            background: 'linear-gradient(135deg, var(--accent), var(--accent-2))',
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            fontSize: 12, fontWeight: 800, flexShrink: 0, color: '#fff',
                          }}>{i + 1}</div>
                          <div style={{ fontSize: 13, lineHeight: 1.7, paddingTop: 4 }}>{step}</div>
                        </div>
                      ))}
                    </div>

                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
                      <div style={{ padding: '10px 14px', borderRadius: 'var(--radius-sm)', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>💸 Financial Trail</div>
                        <div style={{ fontSize: 13, fontWeight: 600, marginTop: 4, color: 'var(--high)' }}>{narrative.financial_trail}</div>
                      </div>
                      <div style={{ padding: '10px 14px', borderRadius: 'var(--radius-sm)', background: 'rgba(239,68,68,0.08)', border: '1px solid rgba(239,68,68,0.2)' }}>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>💰 Estimated Loss</div>
                        <div style={{ fontSize: 16, fontWeight: 800, marginTop: 4, color: 'var(--critical)' }}>{narrative.estimated_loss}</div>
                        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
                          Confidence: {Math.round((narrative.confidence || 0.85) * 100)}%
                        </div>
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {/* ── Tab: Network Graph ───────────────────────── */}
            {!loading && tab === 'graph' && (
              <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
                <div className="card-header" style={{ padding: '14px 18px' }}>
                  <h3>🕸️ Criminal Network Graph</h3>
                  <div style={{ display: 'flex', gap: 8 }}>
                    <span className="badge badge-critical">{graphData?.nodes?.length || demoGraph.nodes.length} nodes</span>
                    <span className="badge badge-medium">{graphData?.links?.length || demoGraph.links.length} links</span>
                  </div>
                </div>
                <NetworkGraph
                  nodes={graphData?.nodes || demoGraph.nodes}
                  links={graphData?.links || demoGraph.links}
                  onNodeClick={() => {}}
                  height={450}
                />
              </div>
            )}

            {/* ── Tab: Entities ──────────────────────────────── */}
            {!loading && tab === 'entities' && (
              <div className="card">
                <div className="card-header"><h3>🔎 Extracted Entities</h3></div>
                <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
                  <EntityGroup
                    title="📞 Phone Numbers"
                    items={selected.shared_entities?.filter(e => e.startsWith('+91') || e.match(/\d{10}/)) || ['+91-9876XXXXX']}
                    color="var(--high)"
                  />
                  <EntityGroup
                    title="💳 UPI IDs"
                    items={selected.shared_entities?.filter(e => e.includes('@') && !e.includes('t.me')) || ['invest@paytm']}
                    color="var(--accent)"
                  />
                  <EntityGroup
                    title="📱 Telegram Links"
                    items={selected.shared_entities?.filter(e => e.includes('t.me')) || ['t.me/vip_invest']}
                    color="#229ED9"
                  />
                  <EntityGroup title="🌐 Suspicious URLs" items={[]} color="var(--medium)" />
                </div>
              </div>
            )}

            {/* ── Tab: Growth Forecast ───────────────────────── */}
            {!loading && tab === 'growth' && detail && (
              <div className="card">
                <div className="card-header"><h3>📈 30-Day Growth Forecast</h3></div>
                {(() => {
                  const g = detail.growth_forecast || demoCampaignDetail.growth_forecast
                  return (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4,1fr)', gap: 12 }}>
                        <MetricBox label="Current Channels" value={g.current_channels} icon="📡" />
                        <MetricBox label="New (24h)" value={g.new_channels_last_24h} icon="⬆️" color="var(--high)" />
                        <MetricBox label="Projected (30d)" value={g.projected_30day_channels} icon="📊" color="var(--critical)" />
                        <MetricBox label="Victims (30d est.)" value={(g.victim_estimate_30day || 0).toLocaleString()} icon="⚠️" color="var(--critical)" />
                      </div>

                      {/* Risk escalation bar */}
                      <div style={{ padding: '16px', borderRadius: 'var(--radius-sm)', background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.2)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 10 }}>
                          <span style={{ fontWeight: 700, fontSize: 14 }}>
                            Alert Level: <span style={{ color: 'var(--critical)' }}>{g.alert_level}</span>
                          </span>
                          <span style={{ fontSize: 13, color: 'var(--text-muted)' }}>
                            Escalation Score: <strong style={{ color: 'var(--critical)' }}>{g.risk_escalation_score}/100</strong>
                          </span>
                        </div>
                        <div style={{ height: 8, background: 'var(--bg-primary)', borderRadius: 4, overflow: 'hidden' }}>
                          <div style={{
                            width: `${g.risk_escalation_score}%`, height: '100%',
                            background: 'linear-gradient(90deg, var(--accent), var(--high), var(--critical))',
                            borderRadius: 4, transition: 'width 1s ease',
                          }} />
                        </div>
                        <div style={{ marginTop: 10, fontSize: 12, color: 'var(--text-muted)' }}>
                          {g.new_channels_last_24h >= 5
                            ? '🔴 CRITICAL: >5 new channels in 24h — initiate immediate response'
                            : '🟡 Monitor situation — growth within normal parameters'
                          }
                        </div>
                      </div>
                    </div>
                  )
                })()}
              </div>
            )}

            {/* ── Tab: Evidence Package ──────────────────────── */}
            {!loading && tab === 'evidence' && (
              <div className="card">
                <div className="card-header">
                  <h3>📋 Evidence Package</h3>
                  {evidence && (
                    <span style={{ fontSize: 12, color: 'var(--accent)' }}>
                      Confidence: {Math.round((evidence.confidence_score || 0.85) * 100)}%
                    </span>
                  )}
                </div>
                {buildingEvidence && (
                  <div style={{ textAlign: 'center', padding: 40 }}>
                    <div className="spinner" style={{ margin: '0 auto 10px' }} />
                    <div style={{ color: 'var(--text-secondary)', marginBottom: 6 }}>Building evidence package...</div>
                    <div style={{ fontSize: 12, color: 'var(--text-muted)' }}>
                      Collecting screenshots → OCR → Network analysis → Legal mapping
                    </div>
                  </div>
                )}
                {!buildingEvidence && !evidence && (
                  <div style={{ textAlign: 'center', padding: 40, color: 'var(--text-muted)' }}>
                    <div style={{ fontSize: 40, marginBottom: 12 }}>📋</div>
                    <div style={{ marginBottom: 16 }}>Click "Build Evidence" to generate a complete evidence package</div>
                    <button className="btn btn-primary" onClick={buildEvidence}>
                      📋 Build Evidence Package
                    </button>
                  </div>
                )}
                {!buildingEvidence && evidence && (
                  <EvidencePreview evidence={evidence} />
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────

function CampaignSidebarItem({ campaign, selected, onClick, riskColors }) {
  return (
    <div
      onClick={onClick}
      style={{
        padding: '12px 16px',
        cursor: 'pointer',
        borderLeft: selected ? '3px solid var(--accent)' : '3px solid transparent',
        background: selected ? 'rgba(59,130,246,0.08)' : 'transparent',
        borderBottom: '1px solid var(--border)',
        transition: 'all 0.15s',
      }}
      onMouseEnter={e => { if (!selected) e.currentTarget.style.background = 'var(--bg-secondary)' }}
      onMouseLeave={e => { if (!selected) e.currentTarget.style.background = 'transparent' }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 12, fontWeight: 700, lineHeight: 1.4, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {campaign.name}
          </div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>
            {campaign.channel_count} ch · {(campaign.victim_estimate || 0).toLocaleString()} victims
          </div>
        </div>
        <span className={`badge badge-${campaign.risk_level?.toLowerCase()}`} style={{ flexShrink: 0, marginLeft: 8 }}>
          {campaign.risk_level}
        </span>
      </div>
      {campaign.risk_score > 0 && (
        <div style={{ marginTop: 6, height: 2, background: 'var(--bg-primary)', borderRadius: 1, overflow: 'hidden' }}>
          <div style={{
            width: `${campaign.risk_score}%`, height: '100%',
            background: riskColors[campaign.risk_level],
            transition: 'width 0.5s',
          }} />
        </div>
      )}
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

function EntityTag({ value }) {
  const isPhone = value.startsWith('+91') || value.match(/^\d{10}$/)
  const isUPI = value.includes('@') && !value.includes('t.me')
  const isTG = value.includes('t.me')
  const color = isPhone ? 'var(--high)' : isUPI ? 'var(--accent)' : isTG ? '#229ED9' : 'var(--text-secondary)'
  return (
    <span style={{
      padding: '4px 10px', borderRadius: 20, fontSize: 11, fontWeight: 600,
      background: 'var(--bg-secondary)', border: '1px solid var(--border)', color,
    }}>{value}</span>
  )
}

function EntityGroup({ title, items, color }) {
  return (
    <div>
      <h4 style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 8 }}>{title}</h4>
      {items.length === 0 ? (
        <div style={{ fontSize: 12, color: 'var(--text-muted)', fontStyle: 'italic' }}>None detected</div>
      ) : items.map((item, i) => (
        <div key={i} style={{ padding: '5px 10px', marginBottom: 4, borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', border: '1px solid var(--border)', fontSize: 12, fontFamily: 'monospace', color }}>
          {item}
        </div>
      ))}
    </div>
  )
}

function EvidencePreview({ evidence }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3,1fr)', gap: 12 }}>
        <div style={{ padding: '12px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Screenshots</div>
          <div style={{ fontSize: 24, fontWeight: 800, marginTop: 4 }}>{evidence.screenshots?.length || 0}</div>
        </div>
        <div style={{ padding: '12px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Entities Found</div>
          <div style={{ fontSize: 24, fontWeight: 800, marginTop: 4 }}>{evidence.entity_list?.length || 0}</div>
        </div>
        <div style={{ padding: '12px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
          <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>Legal Sections</div>
          <div style={{ fontSize: 24, fontWeight: 800, marginTop: 4 }}>{evidence.legal_sections?.length || 0}</div>
        </div>
      </div>

      {evidence.scam_narrative && (
        <div style={{ padding: '12px 14px', borderRadius: 'var(--radius-sm)', background: 'rgba(59,130,246,0.07)', border: '1px solid rgba(59,130,246,0.2)' }}>
          <div style={{ fontSize: 11, color: 'var(--accent)', marginBottom: 6 }}>📖 SCAM NARRATIVE</div>
          <div style={{ fontSize: 12, lineHeight: 1.7 }}>{evidence.scam_narrative}</div>
        </div>
      )}

      {evidence.legal_sections?.length > 0 && (
        <div>
          <div style={{ fontSize: 11, color: 'var(--text-muted)', marginBottom: 8 }}>⚖️ Applicable Legal Sections</div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {evidence.legal_sections.map((s, i) => (
              <span key={i} className="badge badge-medium">{s}</span>
            ))}
          </div>
        </div>
      )}

      <div style={{ display: 'flex', gap: 10, paddingTop: 8, borderTop: '1px solid var(--border)' }}>
        <button className="btn btn-primary btn-sm">📄 Export PDF</button>
        <button className="btn btn-outline btn-sm">📊 Export JSON</button>
        <button className="btn btn-outline btn-sm">🖼️ Export Graph PNG</button>
        <button className="btn btn-primary btn-sm" style={{ marginLeft: 'auto', background: 'linear-gradient(135deg,#ef4444,#dc2626)' }}>
          🚨 Submit to I4C
        </button>
      </div>
    </div>
  )
}

// ── Demo data ────────────────────────────────────────────────────────────

const demoCampaigns = [
  { id: 'cpg-001', name: 'IPL Betting Ring — Gurugram', risk_level: 'CRITICAL', risk_score: 91, scam_category: 'Real Money Betting', channel_count: 23, post_count: 147, estimated_reach: 45000, victim_estimate: 4500, status: 'ACTIVE', growth_rate: 12.5, shared_entities: ['+91-98765XXXXX', 'betting@paytm', 't.me/ipl_vip_tips'], districts_affected: ['Gurugram', 'Delhi', 'Noida'] },
  { id: 'cpg-002', name: 'Digital Arrest Ring — NCR', risk_level: 'CRITICAL', risk_score: 88, scam_category: 'Digital Arrest', channel_count: 7, post_count: 42, estimated_reach: 0, victim_estimate: 320, status: 'ACTIVE', growth_rate: 8.1, shared_entities: ['+91-76543XXXXX'], districts_affected: ['Delhi', 'Gurugram', 'Ghaziabad'] },
  { id: 'cpg-003', name: 'Fake Zerodha Network', risk_level: 'HIGH', risk_score: 72, scam_category: 'Investment Scam', channel_count: 11, post_count: 83, estimated_reach: 18000, victim_estimate: 1800, status: 'ACTIVE', growth_rate: 6.2, shared_entities: ['+91-87654XXXXX', 'invest@gpay', 't.me/zerodha_official2'], districts_affected: ['Mumbai', 'Pune', 'Bengaluru'] },
  { id: 'cpg-004', name: 'Job Scam Ring — Delhi', risk_level: 'MEDIUM', risk_score: 48, scam_category: 'Job Scam', channel_count: 5, post_count: 34, estimated_reach: 8000, victim_estimate: 480, status: 'ACTIVE', growth_rate: 3.1, shared_entities: ['+91-65432XXXXX'], districts_affected: ['Delhi', 'Noida'] },
]
const demoCampaignDetail = {
  risk_score: 91,
  growth_forecast: { current_channels: 23, new_channels_last_24h: 5, projected_30day_channels: 78, victim_estimate_30day: 22000, risk_escalation_score: 84, alert_level: 'CRITICAL' },
}
const demoNarrative = {
  scam_type: 'Real Money Betting', generated_by: 'Gemini AI', confidence: 0.87,
  victim_profile: 'Sports fans, men (18–35), college students looking for quick money',
  financial_trail: 'Victim → UPI/Paytm → Hawala operator → Overseas account',
  estimated_loss: '₹11.25 Crore (estimated)',
  steps: [
    'Victim discovers betting tips channel on Telegram/Instagram',
    'Free "accurate" prediction shared to build credibility',
    'Victim invited to "premium paid group" (₹500–₹2,000 fee)',
    'Insider "fixing" tips shared — all appear to win initially',
    'Victim encouraged to bet progressively larger amounts',
    'Tips begin losing, victim asked to pay to "recover losses"',
    'Victim blocked after maximum extraction, channel deleted',
  ],
}
const demoEvidence = {
  confidence_score: 0.87,
  screenshots: new Array(14).fill(null),
  entity_list: ['+91-98765XXXXX', 'betting@paytm', 't.me/ipl_vip_tips'],
  legal_sections: ['IT Act §66D', 'IPC §420', 'IPC §406', 'PMLA 2002'],
  scam_narrative: 'Operation IPL Betting Ring: A coordinated scam network operating across 23 Telegram channels, recruiting victims via sports fan communities with false promises of insider match-fixing information.',
}
const demoGraph = {
  nodes: [
    { id: 'cpg-001', label: 'ScamCampaign', properties: { name: 'IPL Betting Ring' } },
    { id: 'ch-1', label: 'Channel', properties: { name: 't.me/ipl_vip_tips' } },
    { id: 'ch-2', label: 'Channel', properties: { name: 't.me/cricket_betting_vip' } },
    { id: 'ph-1', label: 'PhoneNumber', properties: { value: '+91-9876XXXXX' } },
    { id: 'upi-1', label: 'UPIId', properties: { value: 'betting@paytm' } },
    { id: 'usr-1', label: 'TelegramUser', properties: { username: '@bet_king_india' } },
    { id: 'usr-2', label: 'TelegramUser', properties: { username: '@cricket_insider' } },
  ],
  links: [
    { source: 'ch-1', target: 'cpg-001', type: 'BELONGS_TO' },
    { source: 'ch-2', target: 'cpg-001', type: 'BELONGS_TO' },
    { source: 'ch-1', target: 'ph-1', type: 'USES_PHONE' },
    { source: 'ch-1', target: 'upi-1', type: 'USES_UPI' },
    { source: 'usr-1', target: 'ch-1', type: 'OPERATED_BY' },
    { source: 'usr-2', target: 'ch-2', type: 'OPERATED_BY' },
    { source: 'usr-1', target: 'usr-2', type: 'SIMILAR_TO' },
  ],
}
