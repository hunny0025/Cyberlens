import { useState, useEffect } from 'react'
import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import * as api from './services/api'
import Dashboard           from './pages/Dashboard'
import Analyze             from './pages/Analyze'
import CaseQueue           from './pages/CaseQueue'
import LiveScraper         from './pages/LiveScraper'
import IndiaHeatmap        from './pages/IndiaHeatmap'
import Campaigns           from './pages/Campaigns'
import CampaignIntelligence from './pages/CampaignIntelligence'
import NetworkGraph        from './pages/NetworkGraph'
import EarlyWarning        from './pages/EarlyWarning'
import EvidenceBuilder     from './pages/EvidenceBuilder'
import ModelEvaluation     from './pages/ModelEvaluation'
import IntelligencePipeline from './pages/IntelligencePipeline'

export default function App() {
  const location = useLocation()
  const [officer, setOfficer]         = useState({
    officer_id: 'off-001',
    username: 'admin',
    full_name: 'System Administrator',
    badge_number: 'ADMIN-001',
    district: 'ALL',
    role: 'admin',
  })
  const [criticalCount, setCriticalCount] = useState(0)
  const [highFPR, setHighFPR] = useState(false)


  const navGroups = [
    {
      label: 'Intelligence',
      items: [
        { path: '/',              label: 'Command Center',     icon: '🛡️' },
        { path: '/campaigns',    label: 'Campaigns',          icon: '🎯' },
        { path: '/intelligence', label: 'Campaign Intel',     icon: '🧠' },
        { path: '/early-warning',label: 'Early Warning',      icon: '⚡', badge: criticalCount > 0 ? criticalCount : null },
        { path: '/evidence',     label: 'Evidence Builder',   icon: '📋' },
        { path: '/network',      label: 'Network Graph',      icon: '🕸️' },
        { path: '/heatmap',      label: 'India Heatmap',      icon: '🗺️' },
        { path: '/model-eval',   label: 'Model Performance',  icon: '📊', badge: highFPR ? '!' : null },
        { path: '/pipeline',     label: 'Intel Pipeline',     icon: '🧠' },
      ],
    },
    {
      label: 'Analysis',
      items: [
        { path: '/analyze', label: 'Analyze Image', icon: '🔍' },
        { path: '/cases',   label: 'Case Queue',    icon: '📋' },
      ],
    },
    {
      label: 'Monitor',
      items: [
        { path: '/scraper', label: 'Live Scraper', icon: '📡' },
      ],
    },
  ]

  return (
    <div className="app-layout">
      {/* Official Top Banner Header Bar */}
      <header className="portal-header">
        <div className="header-brand">
          <span className="crest-icon">🛡️</span>
          <div>
            <h2>CyberLens Intelligence Portal</h2>
            <div className="header-subtitle">GURUGRAM POLICE · CYBER CRIME INVESTIGATION DIVISION</div>
          </div>
        </div>
        <div className="header-stats">
          <div className="header-stat-badge">
            <span className="status-dot green"></span> SECURE CONNECT
          </div>
          <div className="header-stat-badge">
            OFFICER: <strong>{officer.badge_number}</strong>
          </div>
          <div className="header-stat-badge">
            JURISDICTION: <strong>{officer.district === 'ALL' ? 'ALL DISTRICTS' : officer.district}</strong>
          </div>
        </div>
      </header>

      <div className="portal-container">
        <aside className="sidebar">
          <div className="sidebar-logo">
            <div className="logo-icon">🛡️</div>
            <div>
              <h1>CyberLens</h1>
              <span style={{
                fontSize: 10, background: 'var(--critical)',
                border: '1px solid var(--accent)',
                color: '#fff', padding: '2px 6px', borderRadius: 4, marginTop: 4,
                display: 'inline-block', fontWeight: 700,
              }}>v6.0 -- INTEL</span>
            </div>
          </div>

          <nav className="sidebar-nav">
            {navGroups.map(group => (
              <div key={group.label} style={{ marginBottom: 8 }}>
                <div style={{
                  fontSize: 9, fontWeight: 700, letterSpacing: '0.1em',
                  color: 'var(--text-muted)', padding: '6px 12px 4px',
                  textTransform: 'uppercase',
                }}>
                  {group.label}
                </div>
                {group.items.map(item => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
                    end={item.path === '/'}
                  >
                    <span className="icon">{item.icon}</span>
                    <span style={{ flex: 1 }}>{item.label}</span>
                    {item.badge && (
                      <span style={{
                        background: 'var(--critical)', color: '#fff',
                        borderRadius: 10, fontSize: 9, fontWeight: 800,
                        padding: '1px 5px', minWidth: 16, textAlign: 'center',
                        animation: 'alertPulse 2s infinite',
                      }}>
                        {item.badge}
                      </span>
                    )}
                  </NavLink>
                ))}
              </div>
            ))}
          </nav>

          {/* Officer info */}
          <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)', marginTop: 'auto' }}>
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10,
              padding: '8px 0', borderBottom: '1px solid var(--border)', marginBottom: 8,
            }}>
              <div style={{
                width: 32, height: 32, borderRadius: '50%',
                background: 'linear-gradient(135deg, var(--critical), var(--accent))',
                display: 'flex', alignItems: 'center', justifyContent: 'center',
                fontSize: 14, fontWeight: 800, color: '#fff',
              }}>
                {(officer.full_name || officer.username || '?')[0].toUpperCase()}
              </div>
              <div>
                <div style={{ fontSize: 12, fontWeight: 700 }}>{officer.full_name || officer.username}</div>
                <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                  {officer.badge_number} · {officer.role}
                </div>
              </div>
            </div>
            <div style={{ fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.8 }}>
              <div style={{ fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 2 }}>
                {officer.district === 'ALL' ? 'All Districts' : officer.district}
              </div>
              GPCSSI India<br />
              <span style={{ color: 'var(--accent)' }}>●</span> System Online
            </div>
          </div>
        </aside>

        <main className="main-content fade-in" key={location.pathname}>
          <Routes>
            <Route path="/"               element={<Dashboard />} />
            <Route path="/campaigns"      element={<Campaigns />} />
            <Route path="/intelligence"   element={<CampaignIntelligence />} />
            <Route path="/early-warning"  element={<EarlyWarning />} />
            <Route path="/evidence"       element={<EvidenceBuilder />} />
            <Route path="/network"        element={<NetworkGraph />} />
            <Route path="/analyze"        element={<Analyze />} />
            <Route path="/cases"          element={<CaseQueue />} />
            <Route path="/scraper"        element={<LiveScraper />} />
            <Route path="/heatmap"        element={<IndiaHeatmap />} />
            <Route path="/model-eval"    element={<ModelEvaluation />} />
            <Route path="/pipeline"     element={<IntelligencePipeline />} />
          </Routes>
        </main>
      </div>
    </div>
  )
}

