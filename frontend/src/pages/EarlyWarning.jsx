/**
 * CyberLens — Early Warning System Page
 * =========================================
 * Full alert management: active alerts, history, threshold config, subscriptions.
 */

import { useState, useEffect, useRef } from 'react'
import * as api from '../services/api'

const SEV_COLORS = {
  EMERGENCY: 'var(--critical)',
  CRITICAL:  'var(--high)',
  WARNING:   'var(--medium)',
  WATCH:     'var(--accent)',
  HIGH:      'var(--high)',
}
const SEV_ICONS = {
  EMERGENCY: '🔴', CRITICAL: '🟠', WARNING: '🟡', WATCH: '🔵', HIGH: '🟠',
}
const SEV_ORDER = { EMERGENCY: 0, CRITICAL: 1, HIGH: 2, WARNING: 3, WATCH: 4 }

export default function EarlyWarning() {
  const [alerts, setAlerts]         = useState([])
  const [history, setHistory]       = useState([])
  const [tab, setTab]               = useState('active')
  const [filterSev, setFilterSev]   = useState('ALL')
  const [filterType, setFilterType] = useState('ALL')
  const [muted, setMuted]           = useState(false)
  const [acknowledged, setAcknowledged] = useState(new Set())
  const [monitorStatus, setMonitorStatus] = useState(null)
  const wsRef = useRef(null)
  const audioRef = useRef(null)

  useEffect(() => {
    loadAlerts()
    connectWs()
    const timer = setInterval(loadAlerts, 30000)
    return () => { clearInterval(timer); wsRef.current?.close() }
  }, [])

  async function loadAlerts() {
    const [a, s] = await Promise.all([
      api.getEarlyWarnings(),
      api.getMonitorStatus(),
    ])
    if (a?.alerts) {
      setAlerts(a.alerts)
      // Add older ones to history
      setHistory(prev => {
        const existing = new Set(prev.map(x => x.alert_id))
        const newOnes = a.alerts.filter(x => !existing.has(x.alert_id))
        return [...prev, ...newOnes].slice(-200)
      })
    }
    if (s) setMonitorStatus(s)
  }

  function connectWs() {
    try {
      const ws = new WebSocket(`ws://${window.location.host}/ws/scraper-feed`)
      ws.onmessage = e => {
        const evt = JSON.parse(e.data)
        if (evt.type === 'HIGH_SEVERITY_ALERT') {
          const newAlert = {
            alert_id: `ws-${Date.now()}`,
            type: 'REAL_TIME',
            severity: evt.severity || 'WARNING',
            campaign_name: evt.data?.category || 'Live Detection',
            trigger_reason: evt.data?.caption_preview || evt.data?.message || '',
            recommended_action: 'Review immediately',
            estimated_victims: 0,
            timestamp: evt.timestamp || new Date().toISOString(),
          }
          setAlerts(prev => [newAlert, ...prev])
          if ((evt.severity === 'EMERGENCY' || evt.severity === 'CRITICAL') && !muted && audioRef.current) {
            audioRef.current.play().catch(() => {})
          }
        }
      }
      ws.onclose = () => setTimeout(connectWs, 5000)
      wsRef.current = ws
    } catch { /* */ }
  }

  function acknowledge(alertId) {
    setAcknowledged(prev => new Set([...prev, alertId]))
  }

  function acknowledgeAll() {
    const ids = visibleAlerts.map(a => a.alert_id)
    setAcknowledged(prev => new Set([...prev, ...ids]))
  }

  const liveAlerts = alerts.length > 0 ? alerts : demoAlerts

  const visibleAlerts = liveAlerts
    .filter(a => !acknowledged.has(a.alert_id))
    .filter(a => filterSev === 'ALL' || a.severity === filterSev)
    .filter(a => filterType === 'ALL' || a.type === filterType)
    .sort((a, b) => (SEV_ORDER[a.severity] ?? 9) - (SEV_ORDER[b.severity] ?? 9))

  const emergencyCount = liveAlerts.filter(a => a.severity === 'EMERGENCY').length
  const criticalCount  = liveAlerts.filter(a => a.severity === 'CRITICAL' || a.severity === 'HIGH').length

  const alertTypes = [...new Set(liveAlerts.map(a => a.type))]

  return (
    <div className="fade-in">
      <audio ref={audioRef} src="data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAA==" />

      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="page-header" style={{ marginBottom: 20 }}>
        <div>
          <h2>⚡ Early Warning System</h2>
          <p className="subtitle">Real-time threat monitoring — Gurugram Police / GPCSSI India</p>
        </div>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          {emergencyCount > 0 && (
            <span className="badge badge-critical" style={{ animation: 'alertPulse 1.5s infinite', fontSize: 13 }}>
              🔴 {emergencyCount} EMERGENCY
            </span>
          )}
          <button className="btn btn-outline btn-sm" onClick={() => setMuted(!muted)}>
            {muted ? '🔇 Muted' : '🔊 Sound On'}
          </button>
        </div>
      </div>

      {/* ── Stat row ─────────────────────────────────────────────── */}
      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4,1fr)', marginBottom: 20 }}>
        <StatMini label="Total Active Alerts" value={visibleAlerts.length} color="var(--accent)" />
        <StatMini label="Emergency" value={emergencyCount} color="var(--critical)" pulse={emergencyCount > 0} />
        <StatMini label="Critical / High" value={criticalCount} color="var(--high)" />
        <StatMini label="Monitor Status" value={monitorStatus?.early_warning_active ? 'ONLINE' : 'OFFLINE'} color="var(--accent-3)" />
      </div>

      {/* ── Tabs ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 16 }}>
        {[
          { key: 'active', label: `⚡ Active (${visibleAlerts.length})` },
          { key: 'history', label: `📜 History (${history.length})` },
          { key: 'thresholds', label: '⚙️ Thresholds' },
        ].map(t => (
          <button key={t.key} className={`btn btn-sm ${tab === t.key ? 'btn-primary' : 'btn-outline'}`} onClick={() => setTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Active Alerts Tab ──────────────────────────────────── */}
      {tab === 'active' && (
        <>
          {/* Filters */}
          <div className="card" style={{ marginBottom: 16, padding: '12px 16px' }}>
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap', alignItems: 'center' }}>
              <div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', marginRight: 8 }}>SEVERITY</span>
                {['ALL', 'EMERGENCY', 'CRITICAL', 'WARNING', 'WATCH'].map(s => (
                  <button
                    key={s}
                    className={`btn btn-sm ${filterSev === s ? 'btn-primary' : 'btn-outline'}`}
                    style={{ marginRight: 4, fontSize: 11, padding: '2px 8px' }}
                    onClick={() => setFilterSev(s)}
                  >{s}</button>
                ))}
              </div>
              <div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', marginRight: 8 }}>TYPE</span>
                {['ALL', ...alertTypes].map(t => (
                  <button
                    key={t}
                    className={`btn btn-sm ${filterType === t ? 'btn-primary' : 'btn-outline'}`}
                    style={{ marginRight: 4, fontSize: 10, padding: '2px 6px' }}
                    onClick={() => setFilterType(t)}
                  >{t.replace(/_/g, ' ')}</button>
                ))}
              </div>
              {visibleAlerts.length > 0 && (
                <button className="btn btn-outline btn-sm" style={{ marginLeft: 'auto' }} onClick={acknowledgeAll}>
                  ✓ Acknowledge All
                </button>
              )}
            </div>
          </div>

          {/* Alert cards */}
          {visibleAlerts.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: 48 }}>
              <div style={{ fontSize: 48, marginBottom: 12 }}>✅</div>
              <div style={{ fontSize: 16, fontWeight: 700, marginBottom: 6 }}>No Active Alerts</div>
              <div style={{ color: 'var(--text-muted)', fontSize: 13 }}>All threats within normal parameters</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {visibleAlerts.map((alert, i) => (
                <AlertCard
                  key={alert.alert_id || i}
                  alert={alert}
                  onAcknowledge={() => acknowledge(alert.alert_id)}
                />
              ))}
            </div>
          )}
        </>
      )}

      {/* ── History Tab ───────────────────────────────────────── */}
      {tab === 'history' && (
        <div className="card">
          <div className="card-header">
            <h3>📜 Alert History</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{history.length} alerts</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {(history.length > 0 ? history : demoAlerts).map((alert, i) => (
              <div key={i} style={{
                display: 'flex', gap: 12, padding: '10px 14px',
                borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)',
                border: '1px solid var(--border)', opacity: 0.7,
              }}>
                <span style={{ fontSize: 14 }}>{SEV_ICONS[alert.severity] || '⚪'}</span>
                <div style={{ flex: 1 }}>
                  <span className={`badge badge-${alert.severity === 'EMERGENCY' || alert.severity === 'CRITICAL' ? 'critical' : 'medium'}`} style={{ marginRight: 8 }}>
                    {alert.severity}
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 600 }}>{alert.campaign_name || alert.type}</span>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 3 }}>{alert.trigger_reason}</div>
                </div>
                <div style={{ fontSize: 11, color: 'var(--text-muted)', flexShrink: 0 }}>
                  {new Date(alert.timestamp).toLocaleString()}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Thresholds Tab ─────────────────────────────────────── */}
      {tab === 'thresholds' && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
          <div className="card">
            <div className="card-header"><h3>⚙️ Alert Thresholds</h3></div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
              {thresholdConfig.map((t, i) => (
                <ThresholdRow key={i} config={t} />
              ))}
            </div>
          </div>

          <div className="card">
            <div className="card-header"><h3>📡 Monitor Controls</h3></div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
              <div style={{ padding: '14px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
                <div style={{ fontWeight: 700, marginBottom: 8 }}>Telegram Monitor</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
                  Requires TELEGRAM_API_ID / TELEGRAM_API_HASH in .env
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn btn-primary btn-sm" onClick={api.startMonitor}>▶ Start</button>
                  <button className="btn btn-outline btn-sm" onClick={api.stopMonitor}>⏹ Stop</button>
                </div>
              </div>
              <div style={{ padding: '14px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)', border: '1px solid var(--border)' }}>
                <div style={{ fontWeight: 700, marginBottom: 8 }}>Instagram Monitor</div>
                <div style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 12 }}>
                  Uses Playwright — install: <code>pip install playwright</code>
                </div>
                <div style={{ display: 'flex', gap: 8 }}>
                  <button className="btn btn-primary btn-sm">▶ Start</button>
                  <button className="btn btn-outline btn-sm">⏹ Stop</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// ── Sub-components ─────────────────────────────────────────────────────────

function StatMini({ label, value, color, pulse }) {
  return (
    <div className="stat-card" style={{ position: 'relative', overflow: 'hidden' }}>
      {pulse && <div style={{ position: 'absolute', inset: 0, background: 'rgba(239,68,68,0.06)', animation: 'alertPulse 2s infinite', borderRadius: 'var(--radius)' }} />}
      <div className="label">{label}</div>
      <div className="value" style={{ color, fontSize: 28 }}>{value}</div>
    </div>
  )
}

function AlertCard({ alert, onAcknowledge }) {
  const sev = alert.severity || 'INFO'
  const color = SEV_COLORS[sev] || 'var(--text-muted)'
  const isEmergency = sev === 'EMERGENCY'

  return (
    <div style={{
      padding: '16px 18px',
      borderRadius: 'var(--radius)',
      background: 'var(--bg-card)',
      border: `1px solid ${isEmergency ? 'rgba(239,68,68,0.5)' : 'var(--border)'}`,
      borderLeft: `4px solid ${color}`,
      boxShadow: isEmergency ? '0 0 15px rgba(239,68,68,0.12)' : 'none',
      animation: isEmergency ? 'alertPulse 3s infinite' : 'none',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 12 }}>
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <span style={{ fontSize: 20 }}>{SEV_ICONS[sev] || '⚪'}</span>
          <div>
            <div style={{ fontWeight: 800, fontSize: 15, color }}>[{sev}] {alert.campaign_name || alert.type}</div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
              {new Date(alert.timestamp).toLocaleString()} · {alert.type?.replace(/_/g, ' ')}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button className="btn btn-outline btn-sm" onClick={onAcknowledge}>✓ Ack</button>
          <button className="btn btn-outline btn-sm">🔗 Escalate</button>
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 12 }}>
        <div style={{ padding: '10px 12px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)' }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>TRIGGER REASON</div>
          <div style={{ fontSize: 12, fontWeight: 600 }}>{alert.trigger_reason}</div>
        </div>
        <div style={{ padding: '10px 12px', borderRadius: 'var(--radius-sm)', background: 'var(--bg-secondary)' }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginBottom: 4 }}>RECOMMENDED ACTION</div>
          <div style={{ fontSize: 12 }}>{alert.recommended_action}</div>
        </div>
      </div>

      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        {alert.estimated_victims > 0 && (
          <span style={{ fontSize: 12, color: 'var(--high)', fontWeight: 700 }}>
            ⚠️ ~{alert.estimated_victims.toLocaleString()} victims at risk
          </span>
        )}
        {(alert.affected_districts || []).map((d, i) => (
          <span key={i} className="badge badge-medium">📍 {d}</span>
        ))}
      </div>
    </div>
  )
}

function ThresholdRow({ config }) {
  return (
    <div style={{ display: 'flex', gap: 16, alignItems: 'center', padding: '12px 0', borderBottom: '1px solid var(--border)' }}>
      <div style={{ width: 28, height: 28, borderRadius: '50%', background: `${config.color}22`, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: 14, flexShrink: 0 }}>
        {config.icon}
      </div>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 700, fontSize: 13 }}>{config.name}</div>
        <div style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 2 }}>{config.description}</div>
      </div>
      <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
        <div style={{ textAlign: 'right' }}>
          <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>THRESHOLD</div>
          <div style={{ fontWeight: 700, fontSize: 14, color: config.color }}>{config.threshold}</div>
        </div>
        <span className={`badge badge-${config.severity === 'EMERGENCY' ? 'critical' : config.severity === 'CRITICAL' ? 'critical' : 'medium'}`}>
          {config.severity}
        </span>
        <div style={{ width: 36, height: 20, borderRadius: 10, background: 'var(--accent)', cursor: 'pointer', position: 'relative' }}>
          <div style={{ position: 'absolute', right: 3, top: 3, width: 14, height: 14, borderRadius: '50%', background: '#fff' }} />
        </div>
      </div>
    </div>
  )
}

// ── Static config ──────────────────────────────────────────────────────────

const thresholdConfig = [
  { name: 'Rapid Growth', description: 'Campaign gains too many new channels in 24 hours', threshold: '>5 channels/24h', severity: 'CRITICAL', color: 'var(--critical)', icon: '📈' },
  { name: 'Cross-Platform Spread', description: 'Same scam template detected on multiple platforms', threshold: '3+ platforms', severity: 'EMERGENCY', color: 'var(--critical)', icon: '🌐' },
  { name: 'High Victim Risk', description: 'Campaign reaches a critical mass of potential victims', threshold: '>10,000 reach', severity: 'CRITICAL', color: 'var(--high)', icon: '⚠️' },
  { name: 'Entity Repeat', description: 'Same phone/UPI seen across multiple campaigns', threshold: '5+ campaigns', severity: 'WARNING', color: 'var(--medium)', icon: '🔗' },
  { name: 'Emerging Hotspot', description: 'District shows abnormal spike in scam activity', threshold: '3× baseline', severity: 'WARNING', color: 'var(--medium)', icon: '🔥' },
  { name: 'Template Reuse', description: 'Known scam creative template reappears', threshold: '>0.90 similarity', severity: 'CRITICAL', color: 'var(--high)', icon: '🖼️' },
  { name: 'New Campaign', description: 'First detection of a new campaign', threshold: 'Always', severity: 'WATCH', color: 'var(--accent)', icon: '🆕' },
]

const demoAlerts = [
  { alert_id: 'alr-001', type: 'RAPID_GROWTH', severity: 'EMERGENCY', campaign_name: 'IPL Betting Ring — Gurugram',
    trigger_reason: '8 new channels detected in last 24 hours — fastest growth since monitoring began',
    recommended_action: 'Immediately brief district SP. Block all listed phone numbers and UPI IDs via NPCI/CERT-In.',
    affected_districts: ['Gurugram', 'Delhi'], estimated_victims: 4500, timestamp: new Date().toISOString() },
  { alert_id: 'alr-002', type: 'TEMPLATE_REUSE', severity: 'CRITICAL', campaign_name: 'Deepfake Investment Ad',
    trigger_reason: 'Mukesh Ambani deepfake video detected simultaneously on Telegram, Instagram, Facebook, WhatsApp and YouTube',
    recommended_action: 'Submit NCMEC/DMCA takedowns to all platforms. Issue public advisory via DGP office.',
    affected_districts: ['Delhi', 'Mumbai', 'Bengaluru'], estimated_victims: 12000, timestamp: new Date(Date.now()-300000).toISOString() },
  { alert_id: 'alr-003', type: 'ENTITY_REPEAT', severity: 'WARNING', campaign_name: 'Fake Zerodha Network',
    trigger_reason: 'UPI ID invest@gpay linked to 6 different scam campaigns across a 2-month period',
    recommended_action: 'Initiate UPI freeze with NPCI. Cross-link all 6 campaigns into unified evidence package.',
    affected_districts: ['Mumbai', 'Pune'], estimated_victims: 1800, timestamp: new Date(Date.now()-900000).toISOString() },
  { alert_id: 'alr-004', type: 'EMERGING_HOTSPOT', severity: 'WARNING', campaign_name: 'Mewat District Spike',
    trigger_reason: 'Mewat district showing 3.2× normal scam activity — 48 reports in last 7 days',
    recommended_action: 'Alert Mewat district SP. Deploy cyber cell for local investigation.',
    affected_districts: ['Mewat', 'Nuh'], estimated_victims: 320, timestamp: new Date(Date.now()-1800000).toISOString() },
]
