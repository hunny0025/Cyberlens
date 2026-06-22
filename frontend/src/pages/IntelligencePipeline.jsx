import { useState, useEffect } from 'react'
import * as api from '../services/api'

const ACTION_CONFIG = {
  TAKEDOWN_REQUEST:     { color: '#ef4444', bg: 'rgba(239,68,68,0.12)', icon: '🚨', label: 'Takedown' },
  ANALYST_REVIEW:       { color: '#f59e0b', bg: 'rgba(245,158,11,0.12)', icon: '👁️', label: 'Review' },
  AUTOMATED_MONITORING: { color: '#cda869', bg: 'rgba(205,168,105,0.12)', icon: '📡', label: 'Monitor' },
  NO_ACTION:            { color: '#75726a', bg: 'rgba(117,114,106,0.12)', icon: '✓', label: 'No Action' },
  SUPPRESSED:           { color: '#a38256', bg: 'rgba(163,130,86,0.12)', icon: '🛑', label: 'Suppressed' },
}

const STRENGTH_COLORS = {
  DEFINITIVE:     '#ef4444',
  STRONG:         '#ea580c',
  MODERATE:       '#cda869',
  WEAK:           '#adaba4',
  CIRCUMSTANTIAL: '#75726a',
}

const CONFIDENCE_COLORS = {
  HIGH:         '#22c55e',
  MODERATE:     '#f59e0b',
  LOW:          '#f97316',
  INSUFFICIENT: '#75726a',
}

export default function IntelligencePipeline() {
  const [recs, setRecs] = useState(null)
  const [attrib, setAttrib] = useState(null)
  const [feedback, setFeedback] = useState(null)
  const [dsStats, setDsStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState('recommendations')
  const [selectedChannel, setSelectedChannel] = useState(null)
  const [running, setRunning] = useState(false)

  useEffect(() => { loadAll() }, [])

  async function loadAll() {
    setLoading(true)
    const [r, a, f, d] = await Promise.all([
      api.getPipelineRecommendations(),
      api.getPipelineAttribution(),
      api.getPipelineFeedback(),
      api.getPipelineDatasetStats(),
    ])
    setRecs(r)
    setAttrib(a)
    setFeedback(f)
    setDsStats(d)
    setLoading(false)
  }

  async function handleRunPipeline() {
    setRunning(true)
    await api.runPipeline()
    setTimeout(() => { loadAll(); setRunning(false) }, 5000)
  }

  if (loading) {
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        <div className="spinner" style={{ margin: '0 auto 16px' }} />
        <div style={{ color: 'var(--text-muted)', fontSize: 14 }}>Loading Intelligence Pipeline...</div>
      </div>
    )
  }

  const recommendations = recs?.recommendations || []
  const summary = recs?.summary || {}
  const pairs = attrib?.pairs || []
  const clusters = attrib?.clusters || {}
  const fbSummary = feedback?.summary || {}
  const stats = dsStats?.stats || {}

  const tabs = [
    { id: 'recommendations', label: 'Recommendations', icon: '🎯', badge: summary.takedown_count },
    { id: 'attribution', label: 'Attribution', icon: '🔗', badge: attrib?.summary?.pairs_above_threshold },
    { id: 'dataset', label: 'Dataset', icon: '📊' },
    { id: 'feedback', label: 'Feedback Loop', icon: '🔄' },
  ]

  return (
    <div style={{ padding: '24px 28px', maxWidth: 1400 }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, margin: 0, display: 'flex', alignItems: 'center', gap: 10 }}>
            <span style={{ fontSize: 28 }}>🧠</span> Intelligence Pipeline
            <span style={{
              fontSize: 10, background: 'var(--critical)', border: '1px solid var(--accent)',
              color: '#fff', padding: '3px 8px', borderRadius: 4, fontWeight: 700,
            }}>v6.0 LIVE</span>
          </h1>
          <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
            Evidence-Based 4-Layer Framework: Evidence → Confidence → Recommendation → Feedback
          </div>
        </div>
        <button
          className="btn btn-primary"
          onClick={handleRunPipeline}
          disabled={running}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
        >
          {running ? <><div className="spinner" style={{ width: 14, height: 14 }} /> Running...</> : '▶ Re-run Pipeline'}
        </button>
      </div>

      {/* Summary Cards */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 12, marginBottom: 20 }}>
        <SummaryCard label="Total Channels" value={summary.total_channels || 0} icon="📡" color="var(--accent)" />
        <SummaryCard label="Takedowns" value={summary.takedown_count || 0} icon="🚨" color="var(--critical)" />
        <SummaryCard label="Analyst Review" value={summary.review_count || 0} icon="👁️" color="#f59e0b" />
        <SummaryCard label="Operator Clusters" value={Object.keys(clusters).length} icon="🔗" color="var(--accent-2)" />
        <SummaryCard label="Total Posts" value={stats.total_posts?.toLocaleString() || '0'} icon="💬" color="#22c55e" />
      </div>

      {/* Tabs */}
      <div style={{ display: 'flex', gap: 4, marginBottom: 20, borderBottom: '1px solid var(--border)', paddingBottom: 0 }}>
        {tabs.map(t => (
          <button
            key={t.id}
            onClick={() => { setActiveTab(t.id); setSelectedChannel(null) }}
            style={{
              padding: '10px 18px', fontSize: 13, fontWeight: 700, cursor: 'pointer',
              background: activeTab === t.id ? 'var(--bg-tertiary)' : 'transparent',
              color: activeTab === t.id ? 'var(--text-primary)' : 'var(--text-muted)',
              border: 'none', borderBottom: activeTab === t.id ? '2px solid var(--accent)' : '2px solid transparent',
              borderRadius: '8px 8px 0 0', display: 'flex', alignItems: 'center', gap: 6,
              transition: 'all 0.2s',
            }}
          >
            <span>{t.icon}</span> {t.label}
            {t.badge > 0 && (
              <span style={{
                background: 'var(--critical)', color: '#fff', fontSize: 9, fontWeight: 800,
                padding: '1px 5px', borderRadius: 8, minWidth: 16, textAlign: 'center',
              }}>{t.badge}</span>
            )}
          </button>
        ))}
      </div>

      {/* Tab Content */}
      {activeTab === 'recommendations' && (
        <RecommendationsTab
          recommendations={recommendations}
          summary={summary}
          selectedChannel={selectedChannel}
          onSelect={setSelectedChannel}
        />
      )}
      {activeTab === 'attribution' && (
        <AttributionTab pairs={pairs} clusters={clusters} summary={attrib?.summary || {}} />
      )}
      {activeTab === 'dataset' && <DatasetTab stats={stats} />}
      {activeTab === 'feedback' && <FeedbackTab summary={fbSummary} recent={feedback?.recent || []} />}
    </div>
  )
}

function SummaryCard({ label, value, icon, color }) {
  return (
    <div className="card" style={{ padding: '16px 18px', textAlign: 'center' }}>
      <div style={{ fontSize: 24, marginBottom: 4 }}>{icon}</div>
      <div style={{ fontSize: 26, fontWeight: 800, color, lineHeight: 1 }}>{value}</div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 4, fontWeight: 600 }}>{label}</div>
    </div>
  )
}

/* ================================================================
   RECOMMENDATIONS TAB
   ================================================================ */
function RecommendationsTab({ recommendations, summary, selectedChannel, onSelect }) {
  const actionOrder = ['TAKEDOWN_REQUEST', 'ANALYST_REVIEW', 'AUTOMATED_MONITORING', 'SUPPRESSED', 'NO_ACTION']
  const sorted = [...recommendations].sort((a, b) => {
    return actionOrder.indexOf(a.action) - actionOrder.indexOf(b.action)
  })

  const selected = selectedChannel
    ? recommendations.find(r => r.channel_id === selectedChannel)
    : null

  return (
    <div style={{ display: 'grid', gridTemplateColumns: selected ? '1fr 420px' : '1fr', gap: 16 }}>
      <div>
        {/* Action distribution bar */}
        <div className="card" style={{ padding: 16, marginBottom: 16 }}>
          <div style={{ fontSize: 12, fontWeight: 700, marginBottom: 10, color: 'var(--text-secondary)' }}>
            Action Distribution
          </div>
          <div style={{ display: 'flex', height: 28, borderRadius: 8, overflow: 'hidden', gap: 2 }}>
            {actionOrder.map(action => {
              const count = summary.action_counts?.[action] || 0
              if (!count) return null
              const pct = (count / recommendations.length) * 100
              const cfg = ACTION_CONFIG[action] || ACTION_CONFIG.NO_ACTION
              return (
                <div key={action} style={{
                  width: `${pct}%`, background: cfg.color, display: 'flex',
                  alignItems: 'center', justifyContent: 'center',
                  color: '#fff', fontSize: 10, fontWeight: 800, minWidth: 30,
                }} title={`${action}: ${count}`}>
                  {count}
                </div>
              )
            })}
          </div>
          <div style={{ display: 'flex', gap: 16, marginTop: 8, flexWrap: 'wrap' }}>
            {actionOrder.map(action => {
              const count = summary.action_counts?.[action] || 0
              if (!count) return null
              const cfg = ACTION_CONFIG[action]
              return (
                <div key={action} style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11 }}>
                  <span style={{ width: 10, height: 10, borderRadius: 3, background: cfg.color, display: 'inline-block' }} />
                  <span style={{ fontWeight: 600 }}>{cfg.label}</span>
                  <span style={{ color: 'var(--text-muted)' }}>({count})</span>
                </div>
              )
            })}
          </div>
        </div>

        {/* Recommendations table */}
        <div className="card" style={{ overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
            <thead>
              <tr style={{ background: 'var(--bg-tertiary)', textAlign: 'left' }}>
                <th style={thStyle}>Channel</th>
                <th style={thStyle}>Action</th>
                <th style={thStyle}>Strength</th>
                <th style={thStyle}>Confidence</th>
                <th style={thStyle}>Urgency</th>
                <th style={thStyle}>Legal</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((rec, i) => {
                const cfg = ACTION_CONFIG[rec.action] || ACTION_CONFIG.NO_ACTION
                const isSelected = selectedChannel === rec.channel_id
                return (
                  <tr
                    key={rec.channel_id}
                    onClick={() => onSelect(isSelected ? null : rec.channel_id)}
                    style={{
                      cursor: 'pointer', transition: 'background 0.15s',
                      background: isSelected ? 'rgba(59,130,246,0.08)' : (i % 2 === 0 ? 'transparent' : 'var(--bg-secondary)'),
                      borderLeft: isSelected ? '3px solid var(--accent)' : '3px solid transparent',
                    }}
                    onMouseEnter={e => { if (!isSelected) e.currentTarget.style.background = 'var(--bg-tertiary)' }}
                    onMouseLeave={e => { if (!isSelected) e.currentTarget.style.background = i % 2 === 0 ? 'transparent' : 'var(--bg-secondary)' }}
                  >
                    <td style={tdStyle}>
                      <span style={{ fontWeight: 700, fontFamily: 'monospace' }}>@{rec.channel_name}</span>
                    </td>
                    <td style={tdStyle}>
                      <span style={{
                        display: 'inline-flex', alignItems: 'center', gap: 4,
                        padding: '3px 8px', borderRadius: 6, fontSize: 11, fontWeight: 700,
                        background: cfg.bg, color: cfg.color,
                      }}>
                        {cfg.icon} {cfg.label}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span style={{
                        color: STRENGTH_COLORS[rec.evidence_strength] || '#6b7280',
                        fontWeight: 700, fontSize: 11,
                      }}>
                        {rec.evidence_strength}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span style={{
                        color: CONFIDENCE_COLORS[rec.recommendation_confidence] || '#6b7280',
                        fontWeight: 700, fontSize: 11,
                      }}>
                        {rec.recommendation_confidence}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>
                        {rec.urgency?.replace('_', ' ')}
                      </span>
                    </td>
                    <td style={tdStyle}>
                      <span style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                        {(rec.applicable_sections || []).length > 0 ? `${rec.applicable_sections.length} sections` : '-'}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Detail Panel */}
      {selected && (
        <div className="card" style={{ padding: 20, position: 'sticky', top: 20, maxHeight: 'calc(100vh - 100px)', overflowY: 'auto' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 16 }}>
            <h3 style={{ margin: 0, fontSize: 16, fontWeight: 800 }}>@{selected.channel_name}</h3>
            <button onClick={() => onSelect(null)} style={{
              background: 'none', border: 'none', cursor: 'pointer', fontSize: 16, color: 'var(--text-muted)',
            }}>✕</button>
          </div>

          {/* Action Badge */}
          {(() => {
            const cfg = ACTION_CONFIG[selected.action] || ACTION_CONFIG.NO_ACTION
            return (
              <div style={{
                padding: '12px 16px', borderRadius: 10, background: cfg.bg,
                border: `1px solid ${cfg.color}30`, marginBottom: 16,
              }}>
                <div style={{ fontSize: 18, fontWeight: 800, color: cfg.color, display: 'flex', alignItems: 'center', gap: 8 }}>
                  {cfg.icon} {selected.action?.replace(/_/g, ' ')}
                </div>
                <div style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 4 }}>
                  Urgency: <strong>{selected.urgency}</strong>
                </div>
              </div>
            )
          })()}

          {/* Evidence Strength + Confidence */}
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 10, marginBottom: 16 }}>
            <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-tertiary)', textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 700, marginBottom: 4 }}>EVIDENCE STRENGTH</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: STRENGTH_COLORS[selected.evidence_strength] || '#6b7280' }}>
                {selected.evidence_strength}
              </div>
            </div>
            <div style={{ padding: 12, borderRadius: 8, background: 'var(--bg-tertiary)', textAlign: 'center' }}>
              <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 700, marginBottom: 4 }}>CONFIDENCE</div>
              <div style={{ fontSize: 16, fontWeight: 800, color: CONFIDENCE_COLORS[selected.recommendation_confidence] || '#6b7280' }}>
                {selected.recommendation_confidence}
              </div>
            </div>
          </div>

          {/* Justification */}
          <div style={{ marginBottom: 16 }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}>PRIMARY JUSTIFICATION</div>
            <div style={{ fontSize: 13, color: 'var(--text-primary)', lineHeight: 1.5, padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 8, borderLeft: '3px solid var(--accent)' }}>
              {selected.primary_justification}
            </div>
          </div>

          {/* Supporting Evidence */}
          {selected.supporting_evidence?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 6 }}>
                SUPPORTING EVIDENCE ({selected.supporting_evidence.length})
              </div>
              {selected.supporting_evidence.map((ev, i) => (
                <div key={i} style={{
                  padding: '8px 10px', fontSize: 11, borderRadius: 6,
                  background: 'var(--bg-secondary)', marginBottom: 4,
                  borderLeft: `3px solid ${STRENGTH_COLORS[ev.strength] || '#6b7280'}`,
                }}>
                  <div style={{ fontWeight: 700, color: 'var(--text-primary)' }}>{ev.evidence_type}</div>
                  <div style={{ color: 'var(--text-secondary)', marginTop: 2, fontFamily: 'monospace', fontSize: 10 }}>
                    {ev.value}
                  </div>
                  <div style={{ color: 'var(--text-muted)', marginTop: 2 }}>{ev.details}</div>
                </div>
              ))}
            </div>
          )}

          {/* Caveats */}
          {selected.caveats?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: '#f59e0b', marginBottom: 4 }}>⚠ CAVEATS</div>
              {selected.caveats.map((c, i) => (
                <div key={i} style={{ fontSize: 11, color: 'var(--text-secondary)', padding: '4px 0', lineHeight: 1.4 }}>
                  • {c}
                </div>
              ))}
            </div>
          )}

          {/* Legal Sections */}
          {selected.applicable_sections?.length > 0 && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}>APPLICABLE LEGAL SECTIONS</div>
              {selected.applicable_sections.map((s, i) => (
                <div key={i} style={{
                  fontSize: 10, padding: '4px 8px', background: 'rgba(139,92,246,0.08)',
                  borderRadius: 4, marginBottom: 3, color: '#8b5cf6', fontWeight: 600,
                }}>
                  {s}
                </div>
              ))}
            </div>
          )}

          {/* Analyst Instructions */}
          {selected.analyst_instructions && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)', marginBottom: 4 }}>ANALYST INSTRUCTIONS</div>
              <div style={{
                fontSize: 11, padding: '10px 12px', background: 'rgba(34,197,94,0.06)',
                borderRadius: 8, border: '1px solid rgba(34,197,94,0.15)',
                color: 'var(--text-secondary)', lineHeight: 1.6, whiteSpace: 'pre-line',
              }}>
                {selected.analyst_instructions}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

/* ================================================================
   ATTRIBUTION TAB
   ================================================================ */
function AttributionTab({ pairs, clusters, summary }) {
  return (
    <div>
      {/* Cluster visualization */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14, marginBottom: 20 }}>
        {Object.entries(clusters).map(([cid, members]) => (
          <div key={cid} className="card" style={{ padding: 16 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <span style={{
                width: 32, height: 32, borderRadius: '50%',
                background: 'linear-gradient(135deg, var(--critical), var(--accent))',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 14, color: '#fff', fontWeight: 800,
              }}>
                {members.length}
              </span>
              <div>
                <div style={{ fontSize: 13, fontWeight: 700 }}>Operator {cid.replace('cluster_', '#')}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{members.length} channels linked</div>
              </div>
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {members.map(m => (
                <span key={m} style={{
                  padding: '3px 8px', fontSize: 10, fontWeight: 700,
                  background: 'rgba(205,168,105,0.1)', color: 'var(--accent)',
                  borderRadius: 'var(--radius-sm)', fontFamily: 'monospace',
                }}>
                  @{m}
                </span>
              ))}
            </div>
          </div>
        ))}
        {Object.keys(clusters).length === 0 && (
          <div className="card" style={{ padding: 24, textAlign: 'center', color: 'var(--text-muted)' }}>
            No operator clusters detected above threshold
          </div>
        )}
      </div>

      {/* Pairs table */}
      <div className="card" style={{ overflow: 'hidden' }}>
        <div style={{ padding: '14px 16px', borderBottom: '1px solid var(--border)' }}>
          <h3 style={{ margin: 0, fontSize: 14, fontWeight: 700 }}>
            Attribution Pairs ({summary.pairs_above_threshold || 0} of {summary.total_pairs_evaluated || 0} above threshold)
          </h3>
        </div>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ background: 'var(--bg-tertiary)', textAlign: 'left' }}>
              <th style={thStyle}>Channel A</th>
              <th style={thStyle}>Channel B</th>
              <th style={thStyle}>P(same_op)</th>
              <th style={thStyle}>Strength</th>
              <th style={thStyle}>Infra</th>
              <th style={thStyle}>Behavioral</th>
              <th style={thStyle}>Content</th>
            </tr>
          </thead>
          <tbody>
            {pairs.map((p, i) => (
              <tr key={i} style={{ background: i % 2 === 0 ? 'transparent' : 'var(--bg-secondary)' }}>
                <td style={tdStyle}><span style={{ fontFamily: 'monospace', fontWeight: 600 }}>@{p.channel_a}</span></td>
                <td style={tdStyle}><span style={{ fontFamily: 'monospace', fontWeight: 600 }}>@{p.channel_b}</span></td>
                <td style={tdStyle}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <div style={{
                      width: 50, height: 6, borderRadius: 3, background: 'var(--bg-tertiary)', overflow: 'hidden',
                    }}>
                      <div style={{
                        width: `${(p.probability_same_operator || 0) * 100}%`, height: '100%',
                        background: p.probability_same_operator > 0.5 ? 'var(--critical)' : p.probability_same_operator > 0.3 ? '#f59e0b' : 'var(--accent)',
                        borderRadius: 3,
                      }} />
                    </div>
                    <span style={{ fontWeight: 800, fontSize: 12 }}>{(p.probability_same_operator || 0).toFixed(3)}</span>
                  </div>
                </td>
                <td style={tdStyle}>
                  <span style={{
                    padding: '2px 6px', borderRadius: 4, fontSize: 10, fontWeight: 700,
                    background: p.attribution_strength === 'PROBABLE' ? 'var(--critical-bg)' :
                               p.attribution_strength === 'POSSIBLE' ? 'rgba(245,158,11,0.12)' : 'var(--border)',
                    color: p.attribution_strength === 'PROBABLE' ? 'var(--critical)' :
                           p.attribution_strength === 'POSSIBLE' ? '#f59e0b' : 'var(--text-muted)',
                  }}>
                    {p.attribution_strength}
                  </span>
                </td>
                <td style={tdStyle}><span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{(p.evidence_breakdown?.infrastructure_overlap || 0).toFixed(2)}</span></td>
                <td style={tdStyle}><span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{(p.evidence_breakdown?.behavioral_similarity || 0).toFixed(2)}</span></td>
                <td style={tdStyle}><span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{(p.evidence_breakdown?.content_similarity || 0).toFixed(2)}</span></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

/* ================================================================
   DATASET TAB
   ================================================================ */
function DatasetTab({ stats }) {
  const categories = stats.categories || {}
  const blocked = stats.blocked_entities || {}
  const entities = stats.total_entities || {}

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      {/* Overview */}
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 700 }}>Dataset Overview</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <StatRow label="Version" value={stats.version} />
          <StatRow label="Total Channels" value={stats.total_channels} />
          <StatRow label="Scam Channels" value={stats.scam_channels} color="#ef4444" />
          <StatRow label="Legitimate" value={stats.legitimate_channels} color="#22c55e" />
          <StatRow label="Total Posts" value={stats.total_posts?.toLocaleString()} />
          <StatRow label="UPIs Extracted" value={entities.upis} />
          <StatRow label="Phones Extracted" value={entities.phones} />
          <StatRow label="URLs Extracted" value={entities.urls} />
        </div>
      </div>

      {/* Blocklist */}
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 700 }}>I4C / CERT-In Blocklist</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <StatRow label="Blocked Domains" value={blocked.domains} color="#ef4444" />
          <StatRow label="Blocked UPIs" value={blocked.upis} color="#f59e0b" />
          <StatRow label="Blocked Phones" value={blocked.phones} color="#f97316" />
          <StatRow label="Blocked Channels" value={blocked.channels} color="#8b5cf6" />
        </div>
        <div style={{ marginTop: 16, padding: 12, background: 'rgba(34,197,94,0.06)', borderRadius: 8, fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          Blocklist matches produce <strong style={{ color: '#ef4444' }}>DEFINITIVE</strong> evidence --
          the strongest category. Channels with blocklist hits automatically receive TAKEDOWN_REQUEST recommendations.
        </div>
      </div>

      {/* Categories */}
      <div className="card" style={{ padding: 20, gridColumn: '1 / -1' }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 700 }}>Channel Categories</h3>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {Object.entries(categories).sort((a, b) => b[1] - a[1]).map(([cat, count]) => (
            <div key={cat} style={{
              padding: '8px 14px', borderRadius: 8, background: 'var(--bg-tertiary)',
              display: 'flex', alignItems: 'center', gap: 8,
            }}>
              <span style={{ fontSize: 18, fontWeight: 800, color: 'var(--accent)' }}>{count}</span>
              <span style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-secondary)' }}>
                {cat.replace(/_/g, ' ')}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function StatRow({ label, value, color }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
      <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{label}</span>
      <span style={{ fontSize: 14, fontWeight: 800, color: color || 'var(--text-primary)' }}>{value ?? '-'}</span>
    </div>
  )
}

/* ================================================================
   FEEDBACK TAB
   ================================================================ */
function FeedbackTab({ summary, recent }) {
  const phaseReady = summary.feedback_ready_for_phase2 ? '✓ READY' : `${summary.analyst_reviewed || 0}/200`
  const phase3Ready = summary.feedback_ready_for_phase3 ? '✓ READY' : `${(summary.confirmed_threats || 0) + (summary.false_positives || 0)}/100`

  return (
    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
      {/* Phase progression */}
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 700 }}>Learning Progression</h3>

        {/* Phase 1 */}
        <PhaseCard
          phase={1} title="Rule-Based (Current)"
          status="ACTIVE" statusColor="#22c55e"
          desc="Evidence-conditional rules with categorical strength. No ML training required."
        />
        {/* Phase 2 */}
        <PhaseCard
          phase={2} title="Learned Coefficients"
          status={phaseReady} statusColor={summary.feedback_ready_for_phase2 ? '#22c55e' : '#f59e0b'}
          desc="Attribution coefficients learned from analyst decisions. Requires 200+ reviewed recommendations."
        />
        {/* Phase 3 */}
        <PhaseCard
          phase={3} title="Full Decision Model"
          status={phase3Ready} statusColor={summary.feedback_ready_for_phase3 ? '#22c55e' : '#6b7280'}
          desc="End-to-end trained model replacing rules. Requires 100+ enforcement outcomes."
        />
      </div>

      {/* Accuracy Metrics */}
      <div className="card" style={{ padding: 20 }}>
        <h3 style={{ margin: '0 0 16px', fontSize: 14, fontWeight: 700 }}>Accuracy Metrics</h3>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 16 }}>
          <MetricCard label="Total Recommendations" value={summary.total_recommendations || 0} />
          <MetricCard label="Analyst Reviewed" value={summary.analyst_reviewed || 0} />
          <MetricCard label="Approved" value={summary.analyst_approved || 0} color="#22c55e" />
          <MetricCard label="Rejected" value={summary.analyst_rejected || 0} color="#ef4444" />
          <MetricCard label="Confirmed Threats" value={summary.confirmed_threats || 0} color="#f59e0b" />
          <MetricCard label="False Positives" value={summary.false_positives || 0} color="#ef4444" />
        </div>
        <div style={{ padding: 12, background: 'var(--bg-tertiary)', borderRadius: 8 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)' }}>Approval Rate</span>
            <span style={{ fontSize: 14, fontWeight: 800, color: '#22c55e' }}>{((summary.approval_rate || 0) * 100).toFixed(1)}%</span>
          </div>
          <div style={{ display: 'flex', justifyContent: 'space-between' }}>
            <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--text-muted)' }}>False Positive Rate</span>
            <span style={{ fontSize: 14, fontWeight: 800, color: (summary.false_positive_rate || 0) > 0.1 ? '#ef4444' : '#22c55e' }}>
              {((summary.false_positive_rate || 0) * 100).toFixed(1)}%
            </span>
          </div>
        </div>
      </div>

      {/* Recent feedback */}
      <div className="card" style={{ padding: 20, gridColumn: '1 / -1' }}>
        <h3 style={{ margin: '0 0 12px', fontSize: 14, fontWeight: 700 }}>
          Recent Feedback Records ({recent.length})
        </h3>
        {recent.length === 0 ? (
          <div style={{ textAlign: 'center', padding: 20, color: 'var(--text-muted)', fontSize: 13 }}>
            No analyst decisions recorded yet. Analyst reviews will appear here as the feedback loop collects data.
          </div>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 11 }}>
            <thead>
              <tr style={{ background: 'var(--bg-tertiary)', textAlign: 'left' }}>
                <th style={thStyle}>Channel</th>
                <th style={thStyle}>Action</th>
                <th style={thStyle}>Analyst Decision</th>
                <th style={thStyle}>Outcome</th>
                <th style={thStyle}>Created</th>
              </tr>
            </thead>
            <tbody>
              {recent.slice(0, 15).map((fb, i) => (
                <tr key={fb.feedback_id} style={{ background: i % 2 === 0 ? 'transparent' : 'var(--bg-secondary)' }}>
                  <td style={tdStyle}><span style={{ fontFamily: 'monospace' }}>@{fb.channel_name || fb.channel_id}</span></td>
                  <td style={tdStyle}>{fb.recommended_action}</td>
                  <td style={tdStyle}>
                    <span style={{
                      padding: '2px 6px', borderRadius: 4, fontSize: 10, fontWeight: 700,
                      background: fb.analyst_decision === 'APPROVED' ? 'rgba(34,197,94,0.12)' :
                                 fb.analyst_decision === 'REJECTED' ? 'rgba(239,68,68,0.12)' : 'rgba(107,114,128,0.12)',
                      color: fb.analyst_decision === 'APPROVED' ? '#22c55e' :
                             fb.analyst_decision === 'REJECTED' ? '#ef4444' : '#6b7280',
                    }}>
                      {fb.analyst_decision}
                    </span>
                  </td>
                  <td style={tdStyle}><span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{fb.enforcement_outcome}</span></td>
                  <td style={tdStyle}><span style={{ fontSize: 10, color: 'var(--text-muted)' }}>{fb.created_at?.slice(0, 16)}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}

function PhaseCard({ phase, title, status, statusColor, desc }) {
  return (
    <div style={{
      padding: '12px 14px', marginBottom: 10, borderRadius: 8, background: 'var(--bg-secondary)',
      borderLeft: `3px solid ${statusColor}`,
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 4 }}>
        <span style={{ fontSize: 13, fontWeight: 700 }}>Phase {phase}: {title}</span>
        <span style={{ fontSize: 10, fontWeight: 800, color: statusColor, padding: '2px 6px', borderRadius: 4, background: `${statusColor}15` }}>
          {status}
        </span>
      </div>
      <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.4 }}>{desc}</div>
    </div>
  )
}

function MetricCard({ label, value, color }) {
  return (
    <div style={{ padding: '8px 12px', background: 'var(--bg-secondary)', borderRadius: 8, textAlign: 'center' }}>
      <div style={{ fontSize: 20, fontWeight: 800, color: color || 'var(--text-primary)' }}>{value}</div>
      <div style={{ fontSize: 10, color: 'var(--text-muted)', fontWeight: 600, marginTop: 2 }}>{label}</div>
    </div>
  )
}

const thStyle = { padding: '10px 12px', fontSize: 10, fontWeight: 700, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }
const tdStyle = { padding: '8px 12px', borderBottom: '1px solid var(--border)' }
