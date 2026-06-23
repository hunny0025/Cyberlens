/**
 * CyberLens v3.0 — Unified API Service Layer
 * All backend endpoint calls in one place.
 * Includes JWT auth header injection.
 */

let base_url = import.meta.env.VITE_API_URL;

if (!base_url) {
  if (typeof window !== 'undefined' && window.location.hostname.endsWith('.vercel.app')) {
    base_url = 'https://cyberlens-api.onrender.com/api';
  } else {
    base_url = '/api';
  }
}

if (base_url.startsWith('http') && !base_url.endsWith('/api') && !base_url.includes('/api/')) {
  base_url = base_url.replace(/\/$/, '') + '/api';
}
const BASE = base_url;

export function getWsUrl() {
  if (BASE.startsWith('/')) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${window.location.host}/ws/scraper-feed`;
  }
  const wsProtocol = BASE.startsWith('https:') ? 'wss:' : 'ws:';
  const cleanUrl = BASE.replace(/^https?:\/\//i, '').replace(/\/api\/?$/i, '');
  return `${wsProtocol}//${cleanUrl}/ws/scraper-feed`;
}


// ── Auth token management ─────────────────────────────────────
let _token = localStorage.getItem('cyberlens_token') || ''

export function setToken(token) {
  _token = token
  localStorage.setItem('cyberlens_token', token)
}
export function clearToken() {
  _token = ''
  localStorage.removeItem('cyberlens_token')
}
export function getToken() { return _token }
export function isAuthenticated() { return !!_token }

async function apiFetch(url, opts = {}) {
  try {
    const headers = { 'Content-Type': 'application/json', ...opts.headers }
    if (_token) headers['Authorization'] = `Bearer ${_token}`
    // Don't set Content-Type for FormData
    if (opts.body instanceof FormData) delete headers['Content-Type']

    const res = await fetch(url, { ...opts, headers })

    // Token expired → redirect to login
    if (res.status === 401) {
      clearToken()
      window.dispatchEvent(new Event('cyberlens:auth-expired'))
      return null
    }
    if (!res.ok) throw new Error(`HTTP ${res.status}`)
    return res.json()
  } catch (e) {
    console.warn(`API ${url}:`, e.message)
    return null
  }
}

// ── Auth ──────────────────────────────────────────────────────
export const login = (username, password) =>
  apiFetch(`${BASE}/auth/login`, {
    method: 'POST', body: JSON.stringify({ username, password }),
  })
export const logout = () => apiFetch(`${BASE}/auth/logout`, { method: 'POST' })
export const getMe = () => apiFetch(`${BASE}/auth/me`)
export const getAuditLog = (limit = 50) => apiFetch(`${BASE}/auth/audit-log?limit=${limit}`)
export const verifyAuditChain = () => apiFetch(`${BASE}/auth/audit-log/verify`)

// ── Statistics ────────────────────────────────────────────────
export const getHeatmap = () => apiFetch(`${BASE}/statistics/heatmap`)
export const getTrends = () => apiFetch(`${BASE}/statistics/trends`)
export const getEntityPatterns = () => apiFetch(`${BASE}/statistics/entity-patterns`)

// ── Intelligence / Campaigns ──────────────────────────────────
export const getCampaigns = () => apiFetch(`${BASE}/intelligence/campaigns`)
export const getCampaign = (id) => apiFetch(`${BASE}/intelligence/campaigns/${id}`)
export const getCampaignEvidence = (id) => apiFetch(`${BASE}/intelligence/campaigns/${id}/evidence`)
export const getScamNarrative = (id) => apiFetch(`${BASE}/intelligence/campaigns/${id}/narrative`)
export const getEarlyWarnings = () => apiFetch(`${BASE}/intelligence/early-warning`)
export const getGrowthForecast = (id) => apiFetch(`${BASE}/intelligence/growth/${id}`)
export const resolveIdentity = (entities) =>
  apiFetch(`${BASE}/intelligence/resolve-identity`, {
    method: 'POST', body: JSON.stringify({ entities }),
  })

// ── Graph ─────────────────────────────────────────────────────
export const getNetworkGraph = (campaignId) => apiFetch(`${BASE}/graph/campaign/${campaignId}`)
export const getEntityConnections = (value) => apiFetch(`${BASE}/graph/entity/${encodeURIComponent(value)}`)
export const findNetwork = (entityValue, entityType = 'AUTO') =>
  apiFetch(`${BASE}/graph/find-network`, {
    method: 'POST', body: JSON.stringify({ entity_value: entityValue, entity_type: entityType }),
  })

// ── Fingerprinting ────────────────────────────────────────────
export const checkTemplateMatch = async (imageFile) => {
  const form = new FormData()
  form.append('file', imageFile)
  return apiFetch(`${BASE}/fingerprint/check`, { method: 'POST', body: form })
}
export const getTemplateEvolution = (id) => apiFetch(`${BASE}/fingerprint/campaign/${id}/evolution`)
export const getViralSpread = (hash) => apiFetch(`${BASE}/fingerprint/viral/${hash}`)
export const getSimilarImages = (hash) => apiFetch(`${BASE}/fingerprint/similar/${hash}`)

// ── Monitor / Scraper ─────────────────────────────────────────
export const getScraperStatus = () => apiFetch(`${BASE}/scraper/status`)
export const startScraper = () => apiFetch(`${BASE}/scraper/start`, { method: 'POST' })
export const stopScraper = () => apiFetch(`${BASE}/scraper/stop`, { method: 'POST' })
export const getMonitorStatus = () => apiFetch(`${BASE}/monitor/status`)
export const startMonitor = () => apiFetch(`${BASE}/monitor/start`, { method: 'POST' })
export const stopMonitor = () => apiFetch(`${BASE}/monitor/stop`, { method: 'POST' })
export const getAlerts = () => apiFetch(`${BASE}/monitor/alerts`)
export const getCriticalAlerts = () => apiFetch(`${BASE}/monitor/alerts/critical`)
export const addChannel = (channel) =>
  apiFetch(`${BASE}/monitor/add-channel`, { method: 'POST', body: JSON.stringify({ channel }) })
export const addHashtag = (hashtag) =>
  apiFetch(`${BASE}/monitor/add-hashtag`, { method: 'POST', body: JSON.stringify({ hashtag }) })

// ── Cases ─────────────────────────────────────────────────────
export const getCases = () => apiFetch(`${BASE}/cases`)
export const analyzeImage = async (file) => {
  const form = new FormData()
  form.append('file', file)
  return apiFetch(`${BASE}/analyze/image`, { method: 'POST', body: form })
}

// ── Actions (FIR, NPCI, OSINT, Evidence) ──────────────────────
export const generateFIR = (data) =>
  apiFetch(`${BASE}/actions/generate-fir`, { method: 'POST', body: JSON.stringify(data) })
export const generateBulkFIRs = (data) =>
  apiFetch(`${BASE}/actions/generate-bulk-firs`, { method: 'POST', body: JSON.stringify(data) })
export const freezeUPI = (data) =>
  apiFetch(`${BASE}/actions/freeze-upi`, { method: 'POST', body: JSON.stringify(data) })
export const listFreezeRequests = (campaignId) =>
  apiFetch(`${BASE}/actions/freeze-upi${campaignId ? '?campaign_id=' + campaignId : ''}`)
export const osintEnrich = (value, entityType) =>
  apiFetch(`${BASE}/actions/osint-enrich`, {
    method: 'POST', body: JSON.stringify({ value, entity_type: entityType }),
  })
export const collectEvidence = (data) =>
  apiFetch(`${BASE}/actions/collect-evidence`, { method: 'POST', body: JSON.stringify(data) })
export const certifyEvidence = (campaignId) =>
  apiFetch(`${BASE}/actions/certify-evidence/${campaignId}`, { method: 'POST' })
export const verifyEvidence = (campaignId, evidenceId) =>
  apiFetch(`${BASE}/actions/verify-evidence/${campaignId}/${evidenceId}`)

// ── Victim Complaints ─────────────────────────────────────────
export const submitComplaint = (data) =>
  apiFetch(`${BASE}/complaints/submit`, { method: 'POST', body: JSON.stringify(data) })
export const listComplaints = (params = '') =>
  apiFetch(`${BASE}/complaints/${params}`)
export const complaintStats = () =>
  apiFetch(`${BASE}/complaints/stats/summary`)

// ── Model Evaluation ─────────────────────────────────────────
export const getEvalSummary = () => apiFetch(`${BASE}/evaluation/summary`)
export const getEvalMatrix = (model) => `${BASE}/evaluation/matrix/${model}`
export const getEvalLastRun = () => apiFetch(`${BASE}/evaluation/last_run`)

// ── Intelligence Pipeline ────────────────────────────────────
export const getPipelineRecommendations = () => apiFetch(`${BASE}/pipeline/recommendations`)
export const getPipelineAttribution = () => apiFetch(`${BASE}/pipeline/attribution`)
export const getPipelineFeedback = () => apiFetch(`${BASE}/pipeline/feedback`)
export const getPipelineDatasetStats = () => apiFetch(`${BASE}/pipeline/dataset-stats`)
export const getChannelEvidence = (id) => apiFetch(`${BASE}/pipeline/evidence/${encodeURIComponent(id)}`)
export const runPipeline = () => apiFetch(`${BASE}/pipeline/run`, { method: 'POST' })
