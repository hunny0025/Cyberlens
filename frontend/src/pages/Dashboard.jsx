import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import * as api from '../services/api'
import NetworkGraphComponent from '../components/NetworkGraph'

export default function Dashboard() {
  const navigate = useNavigate()
  const [campaigns, setCampaigns] = useState([])
  const [alerts, setAlerts] = useState([])
  const [liveEvents, setLiveEvents] = useState([])
  const [heatmapData, setHeatmapData] = useState([])
  const [trends, setTrends] = useState(null)
  const [graphData, setGraphData] = useState(null)
  const [monitorStatus, setMonitorStatus] = useState(null)
  const [muted, setMuted] = useState(false)
  const [platformFilter, setPlatformFilter] = useState('ALL')
  const wsRef = useRef(null)
  const audioRef = useRef(null)

  useEffect(() => {
    loadData()
    connectWebSocket()
    const timer = setInterval(loadData, 60000)
    return () => { clearInterval(timer); wsRef.current?.close() }
  }, [])

  // Load campaign graph for the highest-risk campaign
  useEffect(() => {
    if (campaigns.length > 0) {
      api.getNetworkGraph(campaigns[0]?.id || 'cpg-001').then(r => {
        if (r) setGraphData(r.network || r.demo_graph || null)
      })
    }
  }, [campaigns])

  async function loadData() {
    const [c, a, h, t, ms] = await Promise.all([
      api.getCampaigns(),
      api.getEarlyWarnings(),
      api.getHeatmap(),
      api.getTrends(),
      api.getMonitorStatus(),
    ])
    if (c) setCampaigns(c.campaigns || [])
    if (a) setAlerts(a.alerts || [])
    if (h) setHeatmapData(h || [])
    if (t) setTrends(t)
    if (ms) setMonitorStatus(ms)
  }

  function connectWebSocket() {
    try {
      const ws = new WebSocket(`ws://${window.location.host}/ws/scraper-feed`)
      ws.onmessage = (e) => {
        const evt = JSON.parse(e.data)
        setLiveEvents(prev => [evt, ...prev].slice(0, 100))
        if (evt.severity === 'EMERGENCY' && !muted && audioRef.current) {
          audioRef.current.play().catch(() => {})
        }
      }
      ws.onclose = () => setTimeout(connectWebSocket, 5000)
      wsRef.current = ws
    } catch { /* */ }
  }

  const liveCampaigns = campaigns.length > 0 ? campaigns : demoCampaigns
  const liveAlerts   = alerts.length > 0 ? alerts : demoAlerts
  const liveFeed     = liveEvents.length > 0 ? liveEvents : demoFeedEvents
  const liveHeatmap  = heatmapData.length > 0 ? heatmapData : demoHeatmap

  const activeCampaigns = liveCampaigns.filter(c => c.status === 'ACTIVE').length || liveCampaigns.length
  const criticalAlerts  = liveAlerts.filter(a => a.severity === 'CRITICAL' || a.severity === 'EMERGENCY').length
  const totalVictims    = liveCampaigns.reduce((s, c) => s + (c.victim_estimate || 0), 0)
  const postsToday      = monitorStatus?.total_posts_today || 148

  const filteredFeed = platformFilter === 'ALL'
    ? liveFeed
    : liveFeed.filter(e => (e.data?.source || '').toLowerCase().includes(platformFilter.toLowerCase()))

  return (
    <div className="fade-in" id="dashboard-root">
      {/* Hidden audio for EMERGENCY alerts */}
      <audio ref={audioRef} src="data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAA==" />

      {/* ── Page Header ────────────────────────────────────────────── */}
      <div className="page-header" style={{ marginBottom: 20 }}>
        <div>
          <h2>🛡️ Cyber Intelligence Command Center</h2>
          <p className="subtitle">Gurugram Police / GPCSSI India — Real-time Threat Intelligence Platform</p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span className="live-dot" />
            <span style={{ fontSize: 13, color: 'var(--text-secondary)', fontWeight: 600 }}>LIVE</span>
          </div>
          <button id="mute-btn" className="btn btn-outline btn-sm" onClick={() => setMuted(!muted)}>
            {muted ? '🔇 Muted' : '🔊 Sound On'}
          </button>
        </div>
      </div>

      {/* ── 1. THREAT OVERVIEW — 4 metric cards ─────────────────────── */}
      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4,1fr)', marginBottom: 20 }}>
        <ThreatCard
          id="card-campaigns"
          label="Active Campaigns"
          value={activeCampaigns}
          icon="🎯"
          color="var(--accent)"
          change={`+${Math.max(1, Math.floor(activeCampaigns * 0.1))} today`}
          trend="up"
        />
        <ThreatCard
          id="card-posts"
          label="Posts Monitored Today"
          value={postsToday}
          icon="📡"
          color="var(--accent-3)"
          change="↑ from yesterday"
          trend="up"
        />
        <ThreatCard
          id="card-alerts"
          label="Critical Alerts"
          value={criticalAlerts}
          icon="🚨"
          color="var(--critical)"
          pulse={criticalAlerts > 0}
        />
        <ThreatCard
          id="card-victims"
          label="Victims at Risk"
          value={totalVictims > 0 ? totalVictims.toLocaleString() : '6,620'}
          icon="⚠️"
          color="var(--high)"
          change="est. 30-day"
        />
      </div>

      {/* ── 2. EARLY WARNING PANEL (top-right) + Campaign Map ────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 400px', gap: 20, marginBottom: 20 }}>
        {/* Campaign Intelligence Network Map */}
        <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
          <div className="card-header" style={{ padding: '14px 18px' }}>
            <h3>🕸️ Campaign Intelligence Map</h3>
            <div style={{ display: 'flex', gap: 8 }}>
              <span className="badge badge-critical">{liveCampaigns.length} campaigns</span>
              <button
                className="btn btn-outline btn-sm"
                onClick={() => navigate('/network')}
              >Full Graph →</button>
            </div>
          </div>
          <div style={{ height: 340 }}>
            {graphData ? (
              <NetworkGraphComponent
                nodes={graphData.nodes || demoGraphData.nodes}
                links={graphData.links || demoGraphData.links}
                onNodeClick={() => {}}
                height={340}
              />
            ) : (
              <NetworkGraphComponent
                nodes={demoGraphData.nodes}
                links={demoGraphData.links}
                onNodeClick={() => {}}
                height={340}
              />
            )}
          </div>
        </div>

        {/* Early Warning Panel */}
        <div className="card" style={{
          borderColor: criticalAlerts > 0 ? 'rgba(239,68,68,0.5)' : 'var(--border)',
          boxShadow: criticalAlerts > 0 ? '0 0 20px rgba(239,68,68,0.15)' : 'none',
        }}>
          <div className="card-header">
            <h3>⚡ Early Warning Panel</h3>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              {criticalAlerts > 0 && <span className="live-dot" style={{ background: 'var(--critical)' }} />}
              <span className="badge badge-critical">{liveAlerts.length} ACTIVE</span>
            </div>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8, overflowY: 'auto', maxHeight: 290 }}>
            {liveAlerts.slice(0, 6).map((alert, i) => (
              <AlertRow key={i} alert={alert} />
            ))}
          </div>
          <div style={{ marginTop: 12, paddingTop: 12, borderTop: '1px solid var(--border)', textAlign: 'center' }}>
            <button className="btn btn-outline btn-sm" onClick={() => navigate('/early-warning')}>
              View All Alerts →
            </button>
          </div>
        </div>
      </div>

      {/* ── 3. INDIA HEATMAP + SCAM PEAK HOURS ──────────────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20, marginBottom: 20 }}>
        {/* India Heatmap */}
        <div className="card">
          <div className="card-header">
            <h3>🗺️ India Threat Heatmap</h3>
            <button className="btn btn-outline btn-sm" onClick={() => navigate('/heatmap')}>Full Map →</button>
          </div>
          <HeatmapPanel data={liveHeatmap} />
        </div>

        {/* Scam Peak Hours */}
        <div className="card">
          <div className="card-header"><h3>🕐 Scam Activity Pattern</h3></div>
          <HourlyChart data={trends?.hourly_distribution || demoHourly} />
          <div style={{ marginTop: 12, padding: '10px 14px', borderRadius: 'var(--radius-sm)', background: 'rgba(239,68,68,0.07)', border: '1px solid rgba(239,68,68,0.2)', fontSize: 12 }}>
            <span style={{ color: 'var(--text-muted)' }}>Peak activity windows: </span>
            <span style={{ color: 'var(--critical)', fontWeight: 700 }}>10:00–14:00</span>
            <span style={{ color: 'var(--text-muted)' }}> & </span>
            <span style={{ color: 'var(--critical)', fontWeight: 700 }}>18:00–22:00</span>
            <span style={{ color: 'var(--text-muted)' }}> IST — coordinate enforcement ops accordingly</span>
          </div>
        </div>
      </div>

      {/* ── 4. ACTIVE CAMPAIGNS + 5. LIVE MONITOR FEED ───────────────── */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 20 }}>
        {/* Active Campaigns */}
        <div className="card">
          <div className="card-header">
            <h3>🎯 Active Campaigns</h3>
            <button className="btn btn-outline btn-sm" onClick={() => navigate('/campaigns')}>View All →</button>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
            {liveCampaigns.slice(0, 5).map((c, i) => (
              <CampaignRow key={i} campaign={c} onClick={() => navigate('/campaigns')} />
            ))}
          </div>
        </div>

        {/* Live Monitor Feed */}
        <div className="card">
          <div className="card-header">
            <h3>📡 Live Monitor Feed</h3>
            <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
              <span className="live-dot" />
              <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{liveFeed.length} events</span>
            </div>
          </div>
          {/* Platform filter */}
          <div style={{ display: 'flex', gap: 6, marginBottom: 10, flexWrap: 'wrap' }}>
            {['ALL', 'Telegram', 'Instagram', 'Facebook'].map(p => (
              <button
                key={p}
                className={`btn btn-sm ${platformFilter === p ? 'btn-primary' : 'btn-outline'}`}
                style={{ padding: '3px 10px', fontSize: 11 }}
                onClick={() => setPlatformFilter(p)}
              >{p}</button>
            ))}
          </div>
          <div style={{ maxHeight: 320, overflowY: 'auto' }}>
            {filteredFeed.slice(0, 20).map((evt, i) => (
              <LiveFeedItem key={i} event={evt} />
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}

// ── Sub-components ────────────────────────────────────────────────────────

function ThreatCard({ id, label, value, icon, color, change, pulse, trend }) {
  return (
    <div id={id} className="stat-card" style={{ position: 'relative', overflow: 'hidden' }}>
      {pulse && (
        <div style={{
          position: 'absolute', inset: 0,
          background: 'rgba(239,68,68,0.06)',
          animation: 'alertPulse 2s infinite',
          borderRadius: 'var(--radius)',
        }} />
      )}
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span className="label">{label}</span>
        <span style={{ fontSize: 22 }}>{icon}</span>
      </div>
      <div className="value" style={{ color, fontSize: 32, letterSpacing: '-1px' }}>{value}</div>
      {change && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 4, fontSize: 11, color: trend === 'up' ? 'var(--accent-3)' : 'var(--text-muted)', marginTop: 4 }}>
          {trend === 'up' && <span>↑</span>}
          {change}
        </div>
      )}
    </div>
  )
}

function AlertRow({ alert }) {
  const sev = alert.severity || 'INFO'
  const icons    = { EMERGENCY: '🔴', CRITICAL: '🟠', WARNING: '🟡', WATCH: '🔵', HIGH: '🟠' }
  const colors   = { EMERGENCY: 'var(--critical)', CRITICAL: 'var(--high)', WARNING: 'var(--medium)', WATCH: 'var(--accent)', HIGH: 'var(--high)' }
  const badgeCls = { EMERGENCY: 'badge-critical', CRITICAL: 'badge-critical', WARNING: 'badge-medium', WATCH: 'badge-low', HIGH: 'badge-high' }

  return (
    <div style={{
      display: 'flex', gap: 10, padding: '10px 12px',
      borderRadius: 'var(--radius-sm)',
      background: 'var(--bg-secondary)',
      border: '1px solid var(--border)',
      borderLeft: `3px solid ${colors[sev] || 'var(--border)'}`,
      animation: sev === 'EMERGENCY' ? 'alertPulse 3s infinite' : 'none',
    }}>
      <span style={{ fontSize: 14, flexShrink: 0 }}>{icons[sev] || '⚪'}</span>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 700, fontSize: 12, color: colors[sev] }}>
          [{sev}] {alert.campaign_name || alert.type}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 2, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {alert.trigger_reason}
        </div>
        {alert.estimated_victims > 0 && (
          <div style={{ fontSize: 10, color: 'var(--text-muted)', marginTop: 3 }}>
            ⚠️ ~{alert.estimated_victims?.toLocaleString()} victims at risk
          </div>
        )}
      </div>
      <span className={`badge ${badgeCls[sev] || 'badge-low'}`} style={{ flexShrink: 0, alignSelf: 'flex-start' }}>
        {sev}
      </span>
    </div>
  )
}

function CampaignRow({ campaign, onClick }) {
  const riskColor = {
    CRITICAL: 'var(--critical)', HIGH: 'var(--high)',
    MEDIUM: 'var(--medium)', LOW: 'var(--low)',
  }[campaign.risk_level] || 'var(--text-muted)'

  return (
    <div
      onClick={onClick}
      style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        padding: '10px 12px', borderRadius: 'var(--radius-sm)',
        background: 'var(--bg-secondary)', border: '1px solid var(--border)',
        cursor: 'pointer', transition: 'all 0.15s',
      }}
      onMouseEnter={e => e.currentTarget.style.borderColor = 'var(--accent-dim)'}
      onMouseLeave={e => e.currentTarget.style.borderColor = 'var(--border)'}
    >
      <div style={{ minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
          {campaign.name}
        </div>
        <div style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
          {campaign.channel_count} ch · {(campaign.estimated_reach || 0).toLocaleString()} reach
          {campaign.growth_rate > 0 && <span style={{ color: 'var(--high)', marginLeft: 6 }}>↑{campaign.growth_rate}%</span>}
        </div>
      </div>
      <div style={{ textAlign: 'right', flexShrink: 0, marginLeft: 12 }}>
        <span className={`badge badge-${campaign.risk_level?.toLowerCase()}`}>{campaign.risk_level}</span>
        <div style={{ fontSize: 12, color: riskColor, marginTop: 4, fontWeight: 800 }}>
          {campaign.risk_score || '—'}/100
        </div>
      </div>
    </div>
  )
}

function LiveFeedItem({ event }) {
  const sev = event.severity || 'INFO'
  const typeIcons = { POST_FOUND: '📸', CLASSIFIED: '🏷️', HIGH_SEVERITY_ALERT: '🚨', SCRAPER_STATUS: '📡', CONNECTED: '🔌' }
  const srcColors = {
    instagram: 'linear-gradient(45deg,#f09433,#e6683c,#dc2743)',
    telegram: '#229ED9', facebook: '#1877F2', synthetic: 'var(--bg-card)',
  }
  const src = (event.data?.source || 'synthetic').toLowerCase()
  const badgeCls = { CRITICAL: 'badge-critical', HIGH: 'badge-high', MEDIUM: 'badge-medium', INFO: 'badge-low' }

  return (
    <div className="feed-item">
      <div className="source-icon" style={{ background: srcColors[src] || 'var(--bg-card)', color: '#fff', flexShrink: 0 }}>
        {typeIcons[event.type] || '📡'}
      </div>
      <div className="content" style={{ minWidth: 0, flex: 1 }}>
        <div className="text" style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: 12 }}>
          {event.data?.caption_preview || event.data?.category || event.data?.message || event.type}
        </div>
        <div className="meta">
          <span className={`badge ${badgeCls[sev] || 'badge-low'}`} style={{ fontSize: 10 }}>{sev}</span>
          <span>{event.data?.source || 'System'}</span>
          <span>{new Date(event.timestamp).toLocaleTimeString()}</span>
        </div>
      </div>
    </div>
  )
}

function HeatmapPanel({ data }) {
  const sorted = [...data].sort((a, b) => b.count - a.count)
  const maxCount = Math.max(...data.map(d => d.count), 1)

  return (
    <div>
      {sorted.slice(0, 8).map((d, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 9 }}>
          <span style={{ fontSize: 10, color: 'var(--text-muted)', width: 18, textAlign: 'right' }}>#{i+1}</span>
          <div style={{ display: 'flex', alignItems: 'center', gap: 4, width: 110 }}>
            <span style={{ fontSize: 12, fontWeight: 600 }}>{d.district}</span>
            {d.is_hotspot && <span style={{ fontSize: 12 }}>🔥</span>}
          </div>
          <div style={{ flex: 1, height: 7, background: 'var(--bg-secondary)', borderRadius: 4, overflow: 'hidden' }}>
            <div style={{
              width: `${(d.count / maxCount) * 100}%`, height: '100%',
              background: d.is_hotspot
                ? 'linear-gradient(90deg,var(--critical),#ff6b6b)'
                : 'linear-gradient(90deg,var(--accent),var(--accent-2))',
              borderRadius: 4,
              transition: 'width 0.8s ease',
            }} />
          </div>
          <span style={{ fontSize: 12, fontWeight: 700, color: d.is_hotspot ? 'var(--critical)' : 'var(--text-secondary)', width: 28, textAlign: 'right' }}>
            {d.count}
          </span>
        </div>
      ))}
    </div>
  )
}

function HourlyChart({ data }) {
  const maxCount = Math.max(...data.map(h => h.count), 1)
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', gap: 2, height: 90 }}>
      {data.map((h, i) => {
        const isPeak = (i >= 10 && i <= 14) || (i >= 18 && i <= 22)
        const height = Math.max(3, (h.count / maxCount) * 80)
        return (
          <div key={i} style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
            <div
              title={`${String(i).padStart(2,'0')}:00 — ${Math.round(h.count)} posts`}
              style={{
                width: '100%', maxWidth: 18,
                height,
                background: isPeak
                  ? 'linear-gradient(180deg,var(--critical),rgba(239,68,68,0.5))'
                  : 'var(--bg-secondary)',
                borderRadius: '2px 2px 0 0',
                transition: 'height 0.5s ease',
                cursor: 'default',
              }}
            />
            {i % 6 === 0 && (
              <span style={{ fontSize: 8, color: 'var(--text-muted)', marginTop: 3 }}>
                {String(i).padStart(2,'0')}h
              </span>
            )}
          </div>
        )
      })}
    </div>
  )
}

// ── Demo data ────────────────────────────────────────────────────────────

const demoAlerts = [
  { severity: 'EMERGENCY', campaign_name: 'IPL Betting Ring — Gurugram',
    type: 'RAPID_GROWTH', trigger_reason: '8 new channels detected in 24h — fastest growth ever recorded',
    recommended_action: 'Immediately brief district SP. Block all entities with NPCI/CERT-In.',
    estimated_victims: 4500 },
  { severity: 'CRITICAL', campaign_name: 'Deepfake Investment Ads',
    type: 'TEMPLATE_REUSE', trigger_reason: 'Mukesh Ambani deepfake detected on 5 platforms simultaneously',
    recommended_action: 'Submit NCMEC/DMCA takedowns. Issue public advisory via DGP office.',
    estimated_victims: 12000 },
  { severity: 'WARNING', campaign_name: 'Fake Zerodha Network',
    type: 'ENTITY_REPEAT', trigger_reason: 'UPI invest@gpay linked to 6 separate campaigns over 2 months',
    recommended_action: 'Initiate UPI freeze with NPCI. Cross-link all 6 campaigns.',
    estimated_victims: 1800 },
]

const demoCampaigns = [
  { id: 'cpg-001', name: 'IPL Betting Ring — Gurugram', risk_level: 'CRITICAL', risk_score: 91, channel_count: 23, estimated_reach: 45000, victim_estimate: 4500, status: 'ACTIVE', growth_rate: 12.5 },
  { id: 'cpg-002', name: 'Digital Arrest Ring — NCR', risk_level: 'CRITICAL', risk_score: 88, channel_count: 7, estimated_reach: 0, victim_estimate: 320, status: 'ACTIVE', growth_rate: 8.1 },
  { id: 'cpg-003', name: 'Fake Zerodha Network', risk_level: 'HIGH', risk_score: 72, channel_count: 11, estimated_reach: 18000, victim_estimate: 1800, status: 'ACTIVE', growth_rate: 6.2 },
  { id: 'cpg-004', name: 'Job Scam Ring — Delhi', risk_level: 'MEDIUM', risk_score: 48, channel_count: 5, estimated_reach: 8000, victim_estimate: 480, status: 'ACTIVE', growth_rate: 3.1 },
]

const demoFeedEvents = [
  { type: 'HIGH_SEVERITY_ALERT', severity: 'CRITICAL', timestamp: new Date().toISOString(), data: { source: 'Telegram', caption_preview: '🔴 Investment Scam — 94% confidence — t.me/invest_vip_tips' } },
  { type: 'POST_FOUND', severity: 'INFO', timestamp: new Date(Date.now()-60000).toISOString(), data: { source: 'Instagram', caption_preview: '🔥 Invest ₹5000 → Get ₹20,000 in 24h! Guaranteed 300% return' } },
  { type: 'CLASSIFIED', severity: 'HIGH', timestamp: new Date(Date.now()-120000).toISOString(), data: { source: 'Facebook', caption_preview: 'CBI Officer impersonation — Digital Arrest scam (91% confidence)' } },
  { type: 'POST_FOUND', severity: 'INFO', timestamp: new Date(Date.now()-180000).toISOString(), data: { source: 'Telegram', caption_preview: 'IPL match fixing tips — Join VIP group ₹999/month' } },
  { type: 'CLASSIFIED', severity: 'MEDIUM', timestamp: new Date(Date.now()-300000).toISOString(), data: { source: 'Instagram', caption_preview: 'Work from home ₹3000/day — 75% scam confidence' } },
  { type: 'POST_FOUND', severity: 'HIGH', timestamp: new Date(Date.now()-420000).toISOString(), data: { source: 'Telegram', caption_preview: 'Fake Zerodha VIP trading group — UPI invest@gpay' } },
]

const demoHeatmap = [
  { district: 'Jamtara', count: 48, is_hotspot: true },
  { district: 'Mewat', count: 42, is_hotspot: true },
  { district: 'Gurugram', count: 35, is_hotspot: true },
  { district: 'Delhi', count: 22, is_hotspot: false },
  { district: 'Noida', count: 18, is_hotspot: false },
  { district: 'Mumbai', count: 15, is_hotspot: false },
  { district: 'Hyderabad', count: 11, is_hotspot: false },
  { district: 'Bengaluru', count: 9, is_hotspot: false },
]

const demoHourly = Array.from({ length: 24 }, (_, i) => ({
  hour: i,
  count: (i >= 10 && i <= 14) ? 16 + Math.random() * 7 : (i >= 18 && i <= 22) ? 18 + Math.random() * 8 : 2 + Math.random() * 5,
}))

const demoGraphData = {
  nodes: [
    { id: 'cpg-001', label: 'ScamCampaign', properties: { name: 'IPL Betting Ring' } },
    { id: 'ch-tg-1', label: 'Channel', properties: { name: 't.me/ipl_vip' } },
    { id: 'ch-tg-2', label: 'Channel', properties: { name: 't.me/cricket_tips' } },
    { id: 'ph-1', label: 'PhoneNumber', properties: { value: '+91-9876XXXXX' } },
    { id: 'upi-1', label: 'UPIId', properties: { value: 'betting@paytm' } },
    { id: 'usr-1', label: 'TelegramUser', properties: { username: '@bet_operator' } },
  ],
  links: [
    { source: 'ch-tg-1', target: 'cpg-001', type: 'BELONGS_TO' },
    { source: 'ch-tg-2', target: 'cpg-001', type: 'BELONGS_TO' },
    { source: 'ch-tg-1', target: 'ph-1', type: 'USES_PHONE' },
    { source: 'ch-tg-1', target: 'upi-1', type: 'USES_UPI' },
    { source: 'usr-1', target: 'ch-tg-1', type: 'OPERATED_BY' },
    { source: 'usr-1', target: 'ch-tg-2', type: 'OPERATED_BY' },
  ],
}
