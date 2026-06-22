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
import Login               from './pages/Login'

export default function App() {
  const location = useLocation()
  const [officer, setOfficer]         = useState(null)
  const [authChecked, setAuthChecked] = useState(false)
  const [criticalCount, setCriticalCount] = useState(0)
  const [highFPR, setHighFPR] = useState(false)

  useEffect(() => {
    async function checkAuth() {
      // First check if backend has auth disabled (dev mode)
      try {
        const health = await fetch('/health').then(r => r.json()).catch(() => null)
        // Try /api/auth/me — if AUTH_DISABLED=true on backend, it accepts any/no token
        // In dev mode, auto-login with a synthetic token
        const authDisabled = health?.status === 'healthy'

        if (api.isAuthenticated()) {
          // Has existing token — verify it
          const r = await api.getMe()
          if (r && r.officer_id) {
            setOfficer(r)
            setAuthChecked(true)
            return
          }
          api.clearToken()
        }

        // No token — try auto-login if AUTH_DISABLED=true
        if (authDisabled) {
          // Try logging in with default admin credentials silently
          const result = await api.login('admin', 'cyberlens@2025')
          if (result?.access_token) {
            api.setToken(result.access_token)
            setOfficer({
              officer_id: result.officer_id || 'off-001',
              username: 'admin',
              full_name: result.full_name || 'System Administrator',
              badge_number: result.badge_number || 'ADMIN-001',
              district: result.district || 'ALL',
              role: 'admin',
            })
            setAuthChecked(true)
            return
          }
        }
      } catch { /* */ }

      setAuthChecked(true)
    }
    checkAuth()

    // Listen for auth expiry
    const handler = () => { setOfficer(null); api.clearToken() }
    window.addEventListener('cyberlens:auth-expired', handler)
    return () => window.removeEventListener('cyberlens:auth-expired', handler)
  }, [])

  // Poll critical alert count
  useEffect(() => {
    if (!officer) return
    const fetchCritical = () => {
      api.getEarlyWarnings().then(r => {
        const count = (r?.alerts || []).filter(a =>
          a.severity === 'CRITICAL' || a.severity === 'EMERGENCY'
        ).length
        setCriticalCount(count)
      })
    }
    fetchCritical()
    const timer = setInterval(fetchCritical, 60000)

    // Check model FPR status
    api.getEvalSummary().then(r => {
      if (r?.summary?.any_high_fpr) setHighFPR(true)
    })

    return () => clearInterval(timer)
  }, [officer])

  function handleLogin(officerInfo) { setOfficer(officerInfo) }
  function handleLogout() {
    api.logout()
    api.clearToken()
    setOfficer(null)
  }

  if (!authChecked) {
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg-primary)' }}>
        <div style={{ textAlign: 'center' }}>
          <div className="spinner" style={{ margin: '0 auto 12px' }} />
          <div style={{ fontSize: 13, color: 'var(--text-muted)' }}>Loading CyberLens...</div>
        </div>
      </div>
    )
  }

  if (!officer) {
    return <Login onLogin={handleLogin} />
  }

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
            <button
              className="btn btn-outline btn-sm"
              style={{ width: '100%', marginTop: 8, justifyContent: 'center' }}
              onClick={handleLogout}
            >
              🔓 Logout
            </button>
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

