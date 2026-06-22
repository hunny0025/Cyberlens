import { useState, useEffect } from 'react'

export default function CaseQueue() {
  const [cases, setCases] = useState(demoCases)
  const [filter, setFilter] = useState('all')
  const [sort, setSort] = useState('severity')

  useEffect(() => {
    fetch('/api/cases').then(r => r.ok ? r.json() : demoCases).then(setCases).catch(() => {})
  }, [])

  const filtered = cases
    .filter(c => filter === 'all' || c.severity === filter)
    .sort((a, b) => {
      if (sort === 'severity') {
        const order = { CRITICAL: 0, HIGH: 1, MEDIUM: 2, LOW: 3 }
        return (order[a.severity] ?? 4) - (order[b.severity] ?? 4)
      }
      return new Date(b.created_at) - new Date(a.created_at)
    })

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>📋 Case Queue</h2>
          <p className="subtitle">{filtered.length} cases • {cases.filter(c => c.severity === 'CRITICAL').length} critical</p>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-primary btn-sm" onClick={() => setSort(sort === 'severity' ? 'date' : 'severity')}>
            Sort: {sort === 'severity' ? '🔴 Severity' : '🕐 Date'}
          </button>
        </div>
      </div>

      {/* Filter tabs */}
      <div className="tabs" style={{ marginBottom: 20 }}>
        {['all', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].map(f => (
          <button key={f} className={`tab ${filter === f ? 'active' : ''}`} onClick={() => setFilter(f)}>
            {f === 'all' ? `All (${cases.length})` : `${f} (${cases.filter(c => c.severity === f).length})`}
          </button>
        ))}
      </div>

      {/* Entity pattern alert */}
      <div className="pattern-alert">
        <span className="alert-icon">🔗</span>
        <span className="alert-text">
          Phone +91-98765XXXXX detected in 8 cases — Possible organized scam ring. <strong>Investigate.</strong>
        </span>
      </div>

      {/* Case table */}
      <div className="table-container">
        <table>
          <thead>
            <tr>
              <th>ID</th>
              <th>Category</th>
              <th>Severity</th>
              <th>Confidence</th>
              <th>Source</th>
              <th>Key Entity</th>
              <th>IT Act</th>
              <th>Time</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map(c => (
              <tr key={c.id}>
                <td style={{ fontWeight: 700, color: 'var(--text-primary)' }}>#{c.id}</td>
                <td>
                  <span className={`badge badge-${c.category_class}`}>{c.category}</span>
                </td>
                <td>
                  <span className={`badge badge-${c.severity.toLowerCase()}`}>{c.severity}</span>
                </td>
                <td>
                  <ConfBar value={c.confidence} />
                </td>
                <td style={{ fontSize: 12 }}>{c.source}</td>
                <td>
                  {c.key_entity && (
                    <span className={`entity-box entity-${c.entity_type}`} style={{ fontSize: 11, padding: '4px 8px' }}>
                      {c.key_entity}
                    </span>
                  )}
                </td>
                <td style={{ fontSize: 11, maxWidth: 150, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                  {c.it_act}
                </td>
                <td style={{ fontSize: 12, color: 'var(--text-muted)' }}>{c.time_ago}</td>
                <td>
                  <div style={{ display: 'flex', gap: 4 }}>
                    <button className="btn btn-outline btn-sm">View</button>
                    <button className="btn btn-danger btn-sm">I4C</button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function ConfBar({ value }) {
  const pct = Math.round(value * 100)
  const color = pct > 80 ? 'var(--critical)' : pct > 60 ? 'var(--high)' : 'var(--medium)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
      <div style={{ width: 60, height: 4, background: 'var(--bg-secondary)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%', background: color, borderRadius: 2 }}></div>
      </div>
      <span style={{ fontSize: 12, fontWeight: 700, color }}>{pct}%</span>
    </div>
  )
}

const demoCases = [
  { id: 1042, category: 'Investment Scam', category_class: 'investment', severity: 'CRITICAL', confidence: 0.94,
    source: 'Instagram', key_entity: '+91-98765XXXXX', entity_type: 'phone', it_act: 'IT Act §66D + IPC §420', time_ago: '2m ago', created_at: '2026-06-08T12:00:00Z' },
  { id: 1041, category: 'Digital Arrest', category_class: 'critical', severity: 'CRITICAL', confidence: 0.91,
    source: 'Telegram', key_entity: 't.me/cbi_officer', entity_type: 'telegram', it_act: 'IPC §170 + BNS §204', time_ago: '8m ago', created_at: '2026-06-08T11:55:00Z' },
  { id: 1040, category: 'Sextortion', category_class: 'critical', severity: 'CRITICAL', confidence: 0.88,
    source: 'Facebook', key_entity: '+91-87654XXXXX', entity_type: 'phone', it_act: 'IT Act §66E + BNS §77', time_ago: '15m ago', created_at: '2026-06-08T11:48:00Z' },
  { id: 1039, category: 'Betting', category_class: 'betting', severity: 'HIGH', confidence: 0.86,
    source: 'Instagram', key_entity: 'scam@paytm', entity_type: 'upi', it_act: 'IT Act §66D + Gambling Act', time_ago: '22m ago', created_at: '2026-06-08T11:40:00Z' },
  { id: 1038, category: 'Fake Customer Care', category_class: 'customer-care', severity: 'HIGH', confidence: 0.82,
    source: 'Synthetic', key_entity: '+91-76543XXXXX', entity_type: 'phone', it_act: 'IT Act §66C + §66D', time_ago: '30m ago', created_at: '2026-06-08T11:32:00Z' },
  { id: 1037, category: 'Job Scam', category_class: 'medium', severity: 'MEDIUM', confidence: 0.75,
    source: 'Instagram', key_entity: null, entity_type: '', it_act: 'IT Act §66D', time_ago: '45m ago', created_at: '2026-06-08T11:18:00Z' },
  { id: 1036, category: 'Lottery Scam', category_class: 'medium', severity: 'MEDIUM', confidence: 0.71,
    source: 'Telegram', key_entity: '+91-65432XXXXX', entity_type: 'phone', it_act: 'IT Act §66D + IPC §420', time_ago: '1h ago', created_at: '2026-06-08T11:00:00Z' },
  { id: 1035, category: 'Fake Followers', category_class: 'low', severity: 'LOW', confidence: 0.65,
    source: 'Instagram', key_entity: null, entity_type: '', it_act: 'IT Act §66', time_ago: '2h ago', created_at: '2026-06-08T10:00:00Z' },
]
