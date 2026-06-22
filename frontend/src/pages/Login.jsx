import { useState } from 'react'
import * as api from '../services/api'

export default function Login({ onLogin }) {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleLogin(e) {
    e.preventDefault()
    setError('')
    setLoading(true)

    const result = await api.login(username, password)
    setLoading(false)

    if (result && result.access_token) {
      api.setToken(result.access_token)
      onLogin({
        officer_id: result.officer_id,
        username: username,
        full_name: result.full_name,
        badge_number: result.badge_number,
        role: result.role,
        district: result.district,
      })
    } else {
      setError('Invalid credentials. Contact your system administrator.')
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg-primary)',
      backgroundImage: 'radial-gradient(circle at 30% 50%, rgba(59,130,246,0.08) 0%, transparent 50%), radial-gradient(circle at 70% 80%, rgba(139,92,246,0.06) 0%, transparent 50%)',
    }}>
      <div className="card fade-in" style={{ width: 420, padding: 40 }}>
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{ fontSize: 48, marginBottom: 8 }}>🛡️</div>
          <h1 style={{
            fontSize: 28, fontWeight: 800, letterSpacing: -1,
            background: 'linear-gradient(135deg, var(--accent), var(--accent-2))',
            WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent',
          }}>CyberLens</h1>
          <p style={{ fontSize: 12, color: 'var(--text-muted)', marginTop: 4 }}>
            Criminal Intelligence Platform v3.0
          </p>
          <p style={{ fontSize: 11, color: 'var(--text-muted)', marginTop: 2 }}>
            Gurugram Police / GPCSSI India
          </p>
        </div>

        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: 16 }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, display: 'block' }}>
              Officer Username
            </label>
            <input
              className="form-input" type="text"
              placeholder="Enter badge username"
              value={username} onChange={e => setUsername(e.target.value)}
              required autoFocus
            />
          </div>

          <div style={{ marginBottom: 20 }}>
            <label style={{ fontSize: 12, color: 'var(--text-muted)', marginBottom: 6, display: 'block' }}>
              Password
            </label>
            <input
              className="form-input" type="password"
              placeholder="Enter password"
              value={password} onChange={e => setPassword(e.target.value)}
              required
            />
          </div>

          {error && (
            <div style={{
              background: 'var(--critical-bg)', border: '1px solid rgba(239,68,68,0.3)',
              borderRadius: 'var(--radius-sm)', padding: '10px 14px', marginBottom: 16,
              fontSize: 12, color: 'var(--critical)',
            }}>
              🚫 {error}
            </div>
          )}

          <button className="btn btn-primary" type="submit"
            style={{ width: '100%', justifyContent: 'center', padding: '12px 20px' }}
            disabled={loading}
          >
            {loading ? (
              <><div className="spinner" style={{ width: 16, height: 16, borderWidth: 2 }} /> Authenticating...</>
            ) : (
              '🔐 Login'
            )}
          </button>
        </form>

        <div style={{
          marginTop: 24, padding: '12px 14px',
          background: 'var(--bg-secondary)', borderRadius: 'var(--radius-sm)',
          fontSize: 11, color: 'var(--text-muted)', lineHeight: 1.8,
        }}>
          <div style={{ fontWeight: 700, marginBottom: 4 }}>Demo Credentials:</div>
          <div><code>admin</code> / <code>cyberlens@2025</code> — Full access</div>
          <div><code>inspector_gurugram</code> / <code>gurugram@123</code> — Investigator</div>
          <div><code>sp_ncr</code> / <code>sp@secure99</code> — Superintendent</div>
        </div>
      </div>
    </div>
  )
}
