import { useState, useEffect } from 'react'

const INDIA_SVG_VIEWBOX = "0 0 600 700"

// District positions mapped to SVG coordinates (approximate India map layout)
const DISTRICT_COORDS = {
  "Gurugram": { x: 268, y: 215, region: "NCR" },
  "Jamtara": { x: 370, y: 290, region: "East" },
  "Mewat": { x: 262, y: 228, region: "NCR" },
  "Nuh": { x: 258, y: 235, region: "NCR" },
  "Bharatpur": { x: 252, y: 243, region: "North" },
  "Mathura": { x: 265, y: 238, region: "North" },
  "Deoghar": { x: 375, y: 285, region: "East" },
  "Alwar": { x: 242, y: 235, region: "North" },
  "Hyderabad": { x: 290, y: 405, region: "South" },
  "Bengaluru": { x: 275, y: 475, region: "South" },
  "Mumbai": { x: 210, y: 385, region: "West" },
  "Delhi": { x: 265, y: 205, region: "NCR" },
  "Noida": { x: 275, y: 210, region: "NCR" },
  "Lucknow": { x: 310, y: 240, region: "North" },
  "Jaipur": { x: 235, y: 240, region: "North" },
  "Kolkata": { x: 395, y: 300, region: "East" },
  "Chennai": { x: 300, y: 490, region: "South" },
  "Pune": { x: 225, y: 400, region: "West" },
  "Ahmedabad": { x: 200, y: 300, region: "West" },
  "Chandigarh": { x: 260, y: 175, region: "North" },
}

export default function IndiaHeatmap() {
  const [heatmapData, setHeatmapData] = useState([])
  const [tooltip, setTooltip] = useState(null)
  const [selectedRegion, setSelectedRegion] = useState('all')

  useEffect(() => {
    fetchHeatmap()
  }, [])

  async function fetchHeatmap() {
    try {
      const res = await fetch('/api/statistics/heatmap')
      if (res.ok) setHeatmapData(await res.json())
      else setHeatmapData(demoData)
    } catch { setHeatmapData(demoData) }
  }

  const maxCount = Math.max(...heatmapData.map(d => d.count), 1)
  const filtered = selectedRegion === 'all' ? heatmapData :
    heatmapData.filter(d => DISTRICT_COORDS[d.district]?.region === selectedRegion)

  const totalCases = filtered.reduce((s, d) => s + d.count, 0)
  const hotspots = filtered.filter(d => d.is_hotspot)

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>🗺️ India Cybercrime Heatmap</h2>
          <p className="subtitle">District-level case distribution • {heatmapData.length} districts</p>
        </div>
        <div className="tabs" style={{ marginBottom: 0 }}>
          {['all', 'NCR', 'North', 'East', 'West', 'South'].map(r => (
            <button key={r} className={`tab ${selectedRegion === r ? 'active' : ''}`}
              onClick={() => setSelectedRegion(r)}>
              {r === 'all' ? 'All India' : r}
            </button>
          ))}
        </div>
      </div>

      {/* Stats */}
      <div className="stats-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: 24 }}>
        <div className="stat-card">
          <span className="label">Total Cases</span>
          <div className="value" style={{ color: 'var(--accent)' }}>{totalCases}</div>
        </div>
        <div className="stat-card">
          <span className="label">Active Hotspots</span>
          <div className="value" style={{ color: 'var(--critical)' }}>{hotspots.length}</div>
        </div>
        <div className="stat-card">
          <span className="label">Top District</span>
          <div className="value" style={{ fontSize: 18 }}>{heatmapData[0]?.district || '—'}</div>
        </div>
        <div className="stat-card">
          <span className="label">Avg Cases/District</span>
          <div className="value" style={{ color: 'var(--high)' }}>{heatmapData.length ? Math.round(totalCases / heatmapData.length) : 0}</div>
        </div>
      </div>

      <div className="grid-2-1">
        {/* Map */}
        <div className="heatmap-container" style={{ position: 'relative' }}>
          <svg viewBox={INDIA_SVG_VIEWBOX} style={{ width: '100%', height: 'auto' }}>
            {/* India outline (simplified polygon) */}
            <path d="M260,80 L290,75 L320,90 L340,85 L370,100 L400,130 L420,170 L430,220 L425,260 L410,280 L400,310 L395,340 L380,360 L370,380 L355,400 L340,420 L320,440 L300,470 L290,500 L285,530 L275,560 L265,570 L255,540 L248,510 L240,480 L225,450 L215,420 L200,390 L185,350 L175,310 L165,280 L160,250 L165,220 L175,190 L190,160 L210,130 L230,105 L260,80Z"
              fill="rgba(99,115,171,0.08)" stroke="rgba(99,115,171,0.3)" strokeWidth="1" />

            {/* Heatmap dots */}
            {filtered.map((d, i) => {
              const coords = DISTRICT_COORDS[d.district]
              if (!coords) return null
              const intensity = d.count / maxCount
              const radius = 6 + intensity * 18
              const color = d.is_hotspot ?
                `rgba(239, 68, 68, ${0.4 + intensity * 0.5})` :
                `rgba(59, 130, 246, ${0.3 + intensity * 0.5})`
              const glowColor = d.is_hotspot ? 'rgba(239,68,68,0.3)' : 'rgba(59,130,246,0.2)'

              return (
                <g key={i} className="heatmap-dot"
                  onMouseEnter={(e) => setTooltip({ d, x: e.clientX, y: e.clientY })}
                  onMouseLeave={() => setTooltip(null)}>
                  {/* Glow */}
                  <circle cx={coords.x} cy={coords.y} r={radius + 8}
                    fill={glowColor} opacity={0.5}>
                    <animate attributeName="r" values={`${radius + 5};${radius + 12};${radius + 5}`}
                      dur="3s" repeatCount="indefinite" />
                    <animate attributeName="opacity" values="0.5;0.2;0.5" dur="3s" repeatCount="indefinite" />
                  </circle>
                  {/* Main dot */}
                  <circle cx={coords.x} cy={coords.y} r={radius} fill={color} stroke="rgba(255,255,255,0.3)" strokeWidth="1" />
                  {/* Label */}
                  {intensity > 0.3 && (
                    <text x={coords.x} y={coords.y + radius + 14} textAnchor="middle"
                      fontSize="9" fill="var(--text-muted)" fontWeight="600" fontFamily="Inter">
                      {d.district}
                    </text>
                  )}
                  {/* Count */}
                  <text x={coords.x} y={coords.y + 4} textAnchor="middle"
                    fontSize="10" fill="white" fontWeight="800" fontFamily="Inter">
                    {d.count}
                  </text>
                </g>
              )
            })}
          </svg>

          {/* Tooltip */}
          {tooltip && (
            <div className="heatmap-tooltip" style={{ left: tooltip.x - 100, top: tooltip.y - 160 }}>
              <div style={{ fontWeight: 700, marginBottom: 4 }}>{tooltip.d.district}, {tooltip.d.state}</div>
              <div style={{ color: 'var(--text-secondary)' }}>Cases: <strong style={{ color: tooltip.d.is_hotspot ? 'var(--critical)' : 'var(--accent)' }}>{tooltip.d.count}</strong></div>
              {tooltip.d.is_hotspot && <div style={{ color: 'var(--critical)', fontWeight: 600, marginTop: 4 }}>🔥 Known Hotspot</div>}
            </div>
          )}

          {/* Legend */}
          <div style={{ display: 'flex', gap: 16, marginTop: 12, justifyContent: 'center' }}>
            <LegendItem color="var(--critical)" label="Known Hotspot" />
            <LegendItem color="var(--accent)" label="Active Cases" />
            <LegendItem color="var(--text-muted)" label="Low Activity" />
          </div>
        </div>

        {/* District table */}
        <div className="card" style={{ maxHeight: 600, overflowY: 'auto' }}>
          <div className="card-header"><h3>📊 District Ranking</h3></div>
          {filtered.map((d, i) => (
            <div key={i} style={{
              display: 'flex', justifyContent: 'space-between', alignItems: 'center',
              padding: '10px 0', borderBottom: '1px solid var(--border)',
            }}>
              <div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ fontSize: 12, fontWeight: 800, color: 'var(--text-muted)', width: 24 }}>#{i + 1}</span>
                  <span style={{ fontSize: 13, fontWeight: 600 }}>{d.district}</span>
                  {d.is_hotspot && <span style={{ fontSize: 10 }}>🔥</span>}
                </div>
                <span style={{ fontSize: 11, color: 'var(--text-muted)', marginLeft: 32 }}>{d.state}</span>
              </div>
              <div style={{ textAlign: 'right' }}>
                <span style={{
                  fontSize: 16, fontWeight: 800,
                  color: d.is_hotspot ? 'var(--critical)' : d.count > 15 ? 'var(--high)' : 'var(--text-secondary)',
                }}>{d.count}</span>
                <div style={{
                  width: 60, height: 4, background: 'var(--bg-secondary)', borderRadius: 2,
                  overflow: 'hidden', marginTop: 4,
                }}>
                  <div style={{
                    width: `${(d.count / maxCount) * 100}%`, height: '100%',
                    background: d.is_hotspot ? 'var(--critical)' : 'var(--accent)',
                    borderRadius: 2,
                  }}></div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function LegendItem({ color, label }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 10, height: 10, borderRadius: '50%', background: color }}></div>
      <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{label}</span>
    </div>
  )
}

const demoData = [
  { district: "Jamtara", state: "Jharkhand", count: 48, is_hotspot: true },
  { district: "Mewat", state: "Haryana", count: 42, is_hotspot: true },
  { district: "Nuh", state: "Haryana", count: 38, is_hotspot: true },
  { district: "Gurugram", state: "Haryana", count: 35, is_hotspot: true },
  { district: "Deoghar", state: "Jharkhand", count: 28, is_hotspot: true },
  { district: "Delhi", state: "Delhi", count: 22, is_hotspot: false },
  { district: "Noida", state: "Uttar Pradesh", count: 18, is_hotspot: false },
  { district: "Bharatpur", state: "Rajasthan", count: 16, is_hotspot: false },
  { district: "Alwar", state: "Rajasthan", count: 14, is_hotspot: false },
  { district: "Mathura", state: "Uttar Pradesh", count: 12, is_hotspot: false },
  { district: "Hyderabad", state: "Telangana", count: 11, is_hotspot: false },
  { district: "Mumbai", state: "Maharashtra", count: 10, is_hotspot: false },
  { district: "Bengaluru", state: "Karnataka", count: 9, is_hotspot: false },
  { district: "Lucknow", state: "Uttar Pradesh", count: 8, is_hotspot: false },
  { district: "Jaipur", state: "Rajasthan", count: 8, is_hotspot: false },
  { district: "Kolkata", state: "West Bengal", count: 7, is_hotspot: false },
  { district: "Chennai", state: "Tamil Nadu", count: 6, is_hotspot: false },
  { district: "Pune", state: "Maharashtra", count: 5, is_hotspot: false },
  { district: "Ahmedabad", state: "Gujarat", count: 5, is_hotspot: false },
  { district: "Chandigarh", state: "Chandigarh", count: 4, is_hotspot: false },
]
