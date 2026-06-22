import { useState, useEffect, useRef } from 'react'
import * as api from '../services/api'

export default function LiveScraper() {
  const [feed, setFeed] = useState([])
  const [status, setStatus] = useState({ running: false, total_runs: 0, total_posts_scraped: 0 })
  const [logLines, setLogLines] = useState(demoLogs)
  const wsRef = useRef(null)

  useEffect(() => {
    fetchStatus()
    connectWS()
    return () => wsRef.current?.close()
  }, [])

  async function fetchStatus() {
    try {
      const data = await api.getScraperStatus()
      if (data) {
        setStatus(data.worker || { running: false })
      }
    } catch { /* */ }
  }

  function connectWS() {
    try {
      const ws = new WebSocket(api.getWsUrl())
      ws.onmessage = (e) => {
        const evt = JSON.parse(e.data)
        setFeed(prev => [evt, ...prev].slice(0, 100))
        addLog(evt)
        if (evt.type === 'SCRAPER_STATUS') {
          setStatus(prev => ({ ...prev, ...evt.data }))
        }
      }
      ws.onclose = () => setTimeout(connectWS, 5000)
      wsRef.current = ws
    } catch { /* */ }
  }

  function addLog(evt) {
    const time = new Date(evt.timestamp).toLocaleTimeString()
    const level = evt.severity === 'CRITICAL' ? 'error' : evt.severity === 'HIGH' ? 'warn' : 'info'
    const msg = evt.data?.caption_preview || evt.data?.category || evt.data?.status || evt.type
    setLogLines(prev => [{ time, level, msg }, ...prev].slice(0, 200))
  }

  async function toggleScraper() {
    try {
      const data = status.running ? await api.stopScraper() : await api.startScraper()
      if (data) {
        setStatus(prev => ({ ...prev, running: data.status === 'started' }))
      }
    } catch { /* */ }
  }

  const sourceIcons = { Instagram: '📸', Facebook: '📘', Telegram: '✈️', Synthetic: '🔧' }

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>🌐 Live Scraper</h2>
          <p className="subtitle">Real-time social media monitoring and analysis</p>
        </div>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span className="live-dot" style={status.running ? {} : { background: 'var(--critical)', animationName: 'none' }}></span>
          <span style={{ fontSize: 13, fontWeight: 600, color: status.running ? 'var(--low)' : 'var(--critical)' }}>
            {status.running ? 'ACTIVE' : 'STOPPED'}
          </span>
          <button className={`btn ${status.running ? 'btn-danger' : 'btn-primary'} btn-sm`} onClick={toggleScraper}>
            {status.running ? '⏹ Stop' : '▶ Start'}
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
        <StatMini label="Total Runs" value={status.total_runs || 0} icon="🔄" />
        <StatMini label="Posts Scraped" value={status.total_posts_scraped || 0} icon="📸" />
        <StatMini label="Cases Created" value={status.total_cases_created || 0} icon="📁" />
        <StatMini label="Last Run" value={status.last_run_at ? new Date(status.last_run_at).toLocaleTimeString() : 'Never'} icon="🕐" />
      </div>

      <div className="grid-2">
        {/* Live feed */}
        <div className="card">
          <div className="card-header">
            <h3>📡 Incoming Posts</h3>
            <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>{feed.length} events</span>
          </div>
          <div style={{ maxHeight: 500, overflowY: 'auto' }}>
            {(feed.length > 0 ? feed : demoFeed).map((evt, i) => (
              <div key={i} className="feed-item">
                <div className={`source-icon ${(evt.data?.source || 'synthetic').toLowerCase()}`}>
                  {sourceIcons[evt.data?.source] || '📡'}
                </div>
                <div className="content">
                  <div style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-primary)', marginBottom: 4 }}>
                    {evt.data?.username || evt.type}
                  </div>
                  <div className="text">{evt.data?.caption_preview || evt.data?.category || evt.data?.message || ''}</div>
                  <div className="meta">
                    <span className={`badge ${evt.severity === 'CRITICAL' ? 'badge-critical' : evt.severity === 'HIGH' ? 'badge-high' : 'badge-low'}`}>
                      {evt.severity || 'INFO'}
                    </span>
                    <span>{evt.data?.source || 'System'}</span>
                    <span>{new Date(evt.timestamp).toLocaleTimeString()}</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Log console */}
        <div className="card">
          <div className="card-header">
            <h3>🖥️ Worker Console</h3>
            <button className="btn btn-outline btn-sm" onClick={() => setLogLines([])}>Clear</button>
          </div>
          <div className="log-feed">
            {logLines.map((line, i) => (
              <div key={i} className="log-line">
                <span className="time">{line.time}</span>
                <span className={`level-${line.level}`}>[{line.level.toUpperCase()}]</span>
                <span className="msg">{line.msg}</span>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Hashtags being monitored */}
      <div className="card" style={{ marginTop: 24 }}>
        <div className="card-header"><h3>🏷️ Monitored Hashtags & Keywords</h3></div>
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
          {['#investment', '#doublemoney', '#stocktips', '#cricketbetting', '#earnmoney', '#workfromhome',
            '#investmenttips', '#stockmarket', '#ipl', '#betting', '#customersupport', '#helpline'].map(tag => (
            <span key={tag} style={{
              padding: '6px 14px', borderRadius: 20, fontSize: 12, fontWeight: 600,
              background: 'var(--bg-secondary)', border: '1px solid var(--border)', color: 'var(--accent)',
            }}>{tag}</span>
          ))}
        </div>
      </div>
    </div>
  )
}

function StatMini({ label, value, icon }) {
  return (
    <div className="stat-card">
      <div style={{ display: 'flex', justifyContent: 'space-between' }}>
        <span className="label">{label}</span>
        <span>{icon}</span>
      </div>
      <div className="value" style={{ fontSize: 24 }}>{value}</div>
    </div>
  )
}

const demoFeed = [
  { type: 'POST_FOUND', severity: 'INFO', timestamp: new Date().toISOString(),
    data: { source: 'Instagram', username: '@quick_money_tips', caption_preview: '🔥 Invest ₹5000 → Get ₹20000 in 24 hours! 100% guaranteed. DM now!' }},
  { type: 'CLASSIFIED', severity: 'HIGH', timestamp: new Date(Date.now()-60000).toISOString(),
    data: { source: 'Telegram', category: 'Investment Scam — 92% confidence' }},
  { type: 'HIGH_SEVERITY_ALERT', severity: 'CRITICAL', timestamp: new Date(Date.now()-120000).toISOString(),
    data: { source: 'Facebook', caption_preview: 'CBI Officer calling — Your Aadhaar linked to money laundering. Digital arrest...' }},
  { type: 'POST_FOUND', severity: 'INFO', timestamp: new Date(Date.now()-180000).toISOString(),
    data: { source: 'Instagram', username: '@ipl_betting_vip', caption_preview: 'IPL prediction 100% accurate. Toss winner guaranteed. Join WhatsApp group!' }},
  { type: 'CLASSIFIED', severity: 'MEDIUM', timestamp: new Date(Date.now()-300000).toISOString(),
    data: { source: 'Synthetic', category: 'Real Money Betting — 78% confidence' }},
]

const demoLogs = [
  { time: new Date().toLocaleTimeString(), level: 'info', msg: 'ScraperWorker initialized (interval=1800s)' },
  { time: new Date(Date.now()-5000).toLocaleTimeString(), level: 'info', msg: 'Instagram: scanning #investment, #doublemoney...' },
  { time: new Date(Date.now()-8000).toLocaleTimeString(), level: 'warn', msg: 'Rate limit hit — backing off 3s' },
  { time: new Date(Date.now()-12000).toLocaleTimeString(), level: 'info', msg: 'Found 4 new posts from Instagram' },
  { time: new Date(Date.now()-15000).toLocaleTimeString(), level: 'error', msg: 'HIGH SEVERITY: Investment scam detected (confidence=0.94)' },
  { time: new Date(Date.now()-20000).toLocaleTimeString(), level: 'info', msg: 'OCR processing: DESIGNED_GRAPHIC detected' },
  { time: new Date(Date.now()-25000).toLocaleTimeString(), level: 'info', msg: 'Entity extraction: 2 phones, 1 UPI, 1 Telegram link' },
  { time: new Date(Date.now()-30000).toLocaleTimeString(), level: 'info', msg: 'Case #1042 created — queued for review' },
]
