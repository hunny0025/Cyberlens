import { useState, useEffect, useRef } from 'react'
import * as api from '../services/api'

export default function NetworkGraph() {
  const [campaigns, setCampaigns] = useState([])
  const [selected, setSelected] = useState(null)
  const [graphData, setGraphData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedNode, setSelectedNode] = useState(null)
  const svgRef = useRef(null)
  const simulationRef = useRef(null)

  useEffect(() => {
    api.getCampaigns().then(r => {
      if (r) { setCampaigns(r.campaigns || []); setSelected((r.campaigns || [])[0]?.id) }
    })
  }, [])

  useEffect(() => {
    if (selected) loadGraph(selected)
  }, [selected])

  useEffect(() => {
    if (graphData && svgRef.current) renderD3Graph(graphData)
  }, [graphData])

  async function loadGraph(campaignId) {
    setLoading(true)
    const data = await api.getNetworkGraph(campaignId)
    const graph = data?.network || data?.demo_graph || null
    setGraphData(graph)
    setLoading(false)
  }

  async function searchEntity() {
    if (!query.trim()) return
    setLoading(true)
    const data = await api.getEntityConnections(query.trim())
    if (data?.network) setGraphData(data.network)
    setLoading(false)
  }

  function renderD3Graph(data) {
    if (!data || !svgRef.current) return
    const nodes = data.nodes || []
    const links = data.links || []
    if (!nodes.length) return

    const container = svgRef.current.parentElement
    const W = container.offsetWidth || 800
    const H = 500

    // Clear previous
    while (svgRef.current.firstChild) svgRef.current.removeChild(svgRef.current.firstChild)
    svgRef.current.setAttribute('width', W)
    svgRef.current.setAttribute('height', H)
    svgRef.current.setAttribute('viewBox', `0 0 ${W} ${H}`)

    const nodeColors = {
      Channel: '#cda869', PhoneNumber: '#b91c1c', UPIId: '#d97706',
      TelegramUser: '#a38256', ScamCampaign: '#b91c1c', Image: '#adaba4',
      Domain: '#a38256', QRCode: '#75726a',
    }
    const nodeRadius = {
      ScamCampaign: 22, Channel: 14, TelegramUser: 12,
      PhoneNumber: 10, UPIId: 10, Image: 8, Domain: 8, QRCode: 8,
    }
    const relColors = {
      BELONGS_TO: '#b91c1c', USES_PHONE: '#d97706', USES_UPI: '#16a34a',
      OPERATED_BY: '#a38256', SHARES_CONTENT: '#adaba4', LINKED_TO: '#75726a',
      HOSTS: '#a38256', SIMILAR_TO: '#75726a',
    }

    const svg = svgRef.current
    const ns = 'http://www.w3.org/2000/svg'

    // Defs: arrowhead markers
    const defs = document.createElementNS(ns, 'defs')
    Object.entries(relColors).forEach(([type, color]) => {
      const marker = document.createElementNS(ns, 'marker')
      marker.setAttribute('id', `arrow-${type}`)
      marker.setAttribute('markerWidth', '8')
      marker.setAttribute('markerHeight', '8')
      marker.setAttribute('refX', '8')
      marker.setAttribute('refY', '3')
      marker.setAttribute('orient', 'auto')
      const path = document.createElementNS(ns, 'path')
      path.setAttribute('d', 'M0,0 L0,6 L8,3 z')
      path.setAttribute('fill', color)
      path.setAttribute('opacity', '0.8')
      marker.appendChild(path)
      defs.appendChild(marker)
    })
    svg.appendChild(defs)

    // Group for zoom pan
    const g = document.createElementNS(ns, 'g')
    svg.appendChild(g)

    // Simple physics simulation (no D3 dep needed)
    const nodeData = nodes.map((n, i) => ({
      ...n,
      x: W / 2 + Math.cos(2 * Math.PI * i / nodes.length) * 200,
      y: H / 2 + Math.sin(2 * Math.PI * i / nodes.length) * 180,
      vx: 0, vy: 0,
      r: nodeRadius[n.label] || 10,
      color: nodeColors[n.label] || '#64748b',
    }))
    const nodeById = Object.fromEntries(nodeData.map(n => [n.id, n]))

    // Render links
    const linkEls = links.map(l => {
      const line = document.createElementNS(ns, 'line')
      const color = relColors[l.type] || '#475569'
      line.setAttribute('stroke', color)
      line.setAttribute('stroke-width', '2')
      line.setAttribute('opacity', '0.6')
      line.setAttribute('marker-end', `url(#arrow-${l.type})`)
      g.appendChild(line)
      return { ...l, el: line }
    })

    // Render nodes
    const nodeEls = nodeData.map(n => {
      const group = document.createElementNS(ns, 'g')
      group.setAttribute('cursor', 'pointer')
      group.setAttribute('data-id', n.id)

      const circle = document.createElementNS(ns, 'circle')
      circle.setAttribute('r', n.r)
      circle.setAttribute('fill', n.color)
      circle.setAttribute('stroke', '#fff')
      circle.setAttribute('stroke-width', '2')
      circle.setAttribute('opacity', '0.9')

      // Glow for ScamCampaign
      if (n.label === 'ScamCampaign') {
        circle.setAttribute('filter', 'drop-shadow(0 0 6px rgba(239,68,68,0.7))')
      }

      const text = document.createElementNS(ns, 'text')
      text.setAttribute('text-anchor', 'middle')
      text.setAttribute('dy', n.r + 12)
      text.setAttribute('fill', '#94a3b8')
      text.setAttribute('font-size', '9')
      text.setAttribute('font-family', 'Inter, sans-serif')
      const label = n.properties?.name || n.properties?.value || n.properties?.username || n.id
      text.textContent = label.length > 15 ? label.slice(0, 12) + '…' : label

      group.appendChild(circle)
      group.appendChild(text)
      group.addEventListener('click', () => setSelectedNode(n))

      // Hover
      group.addEventListener('mouseenter', () => {
        circle.setAttribute('opacity', '1')
        circle.setAttribute('stroke-width', '3')
      })
      group.addEventListener('mouseleave', () => {
        circle.setAttribute('opacity', '0.9')
        circle.setAttribute('stroke-width', '2')
      })

      // Drag
      let dragging = false, ox, oy
      group.addEventListener('mousedown', e => {
        dragging = true
        ox = e.clientX - n.x
        oy = e.clientY - n.y
        e.stopPropagation()
      })
      svg.addEventListener('mousemove', e => {
        if (!dragging) return
        n.x = e.clientX - ox
        n.y = e.clientY - oy
        n.vx = n.vy = 0
        updatePositions()
      })
      svg.addEventListener('mouseup', () => { dragging = false })

      g.appendChild(group)
      return { ...n, groupEl: group }
    })

    function updatePositions() {
      nodeEls.forEach(n => {
        const nd = nodeById[n.id] || n
        n.groupEl.setAttribute('transform', `translate(${nd.x},${nd.y})`)
      })
      linkEls.forEach(l => {
        const src = nodeById[l.source] || nodeById[l.source?.id]
        const tgt = nodeById[l.target] || nodeById[l.target?.id]
        if (!src || !tgt) return
        const dx = tgt.x - src.x, dy = tgt.y - src.y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const tgtR = tgt.r + 4
        l.el.setAttribute('x1', src.x)
        l.el.setAttribute('y1', src.y)
        l.el.setAttribute('x2', tgt.x - (dx / dist) * tgtR)
        l.el.setAttribute('y2', tgt.y - (dy / dist) * tgtR)
      })
    }

    // Simple force simulation
    let frame = 0
    function simulate() {
      if (frame++ > 200) return
      nodeData.forEach(n => {
        // Repulsion between nodes
        nodeData.forEach(m => {
          if (n === m) return
          const dx = n.x - m.x, dy = n.y - m.y
          const dist2 = dx * dx + dy * dy + 0.001
          const force = 4000 / dist2
          n.vx += dx * force / Math.sqrt(dist2)
          n.vy += dy * force / Math.sqrt(dist2)
        })
        // Centering force
        n.vx += (W / 2 - n.x) * 0.001
        n.vy += (H / 2 - n.y) * 0.001
      })

      // Link spring force
      linkEls.forEach(l => {
        const src = nodeById[typeof l.source === 'string' ? l.source : l.source?.id]
        const tgt = nodeById[typeof l.target === 'string' ? l.target : l.target?.id]
        if (!src || !tgt) return
        const dx = tgt.x - src.x, dy = tgt.y - src.y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const ideal = 120
        const force = (dist - ideal) * 0.03
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        src.vx += fx; src.vy += fy
        tgt.vx -= fx; tgt.vy -= fy
      })

      nodeData.forEach(n => {
        n.vx *= 0.85; n.vy *= 0.85
        n.x += n.vx; n.y += n.vy
        n.x = Math.max(n.r + 5, Math.min(W - n.r - 5, n.x))
        n.y = Math.max(n.r + 5, Math.min(H - n.r - 5, n.y))
      })

      updatePositions()
      requestAnimationFrame(simulate)
    }

    simulate()
  }

  const c = campaigns.length > 0 ? campaigns : demoCampaigns
  const nodeTypeColors = {
    Channel: '#cda869', PhoneNumber: '#b91c1c', UPIId: '#d97706',
    TelegramUser: '#a38256', ScamCampaign: '#b91c1c', Image: '#adaba4',
    Domain: '#a38256', QRCode: '#75726a',
  }

  return (
    <div className="fade-in">
      <div className="page-header">
        <div>
          <h2>🕸️ Criminal Network Graph</h2>
          <p className="subtitle">Visualize scam operator networks, shared entities, and campaign connections</p>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <span className="badge badge-critical">{graphData?.node_count || 0} nodes</span>
          <span className="badge badge-medium">{graphData?.link_count || 0} links</span>
        </div>
      </div>

      {/* Campaign selector + entity search */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20, flexWrap: 'wrap' }}>
        <select
          value={selected || ''}
          onChange={e => setSelected(e.target.value)}
          className="form-input"
          style={{ maxWidth: 300 }}
        >
          <option value="">— Select Campaign —</option>
          {c.map(camp => (
            <option key={camp.id} value={camp.id}>
              {camp.name} [{camp.risk_level}]
            </option>
          ))}
        </select>

        <div style={{ display: 'flex', gap: 8, flex: 1 }}>
          <input
            className="form-input" type="text"
            placeholder="Search: phone / UPI / username / URL..."
            value={query} onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && searchEntity()}
            style={{ flex: 1, maxWidth: 400 }}
          />
          <button className="btn btn-primary" onClick={searchEntity}>Search Network</button>
        </div>
      </div>

      {/* Main graph canvas */}
      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <div style={{
          background: 'var(--bg-primary)', position: 'relative',
          borderRadius: 'var(--radius)', overflow: 'hidden',
        }}>
          {loading && (
            <div style={{
              position: 'absolute', inset: 0, display: 'flex', alignItems: 'center',
              justifyContent: 'center', background: 'rgba(2,6,23,0.7)', zIndex: 10,
            }}>
              <div style={{ textAlign: 'center' }}>
                <div className="spinner" style={{ margin: '0 auto 8px' }} />
                <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>Building network graph...</div>
              </div>
            </div>
          )}

          {!graphData && !loading ? (
            <div style={{ height: 400, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 12, color: 'var(--text-muted)' }}>
              <div style={{ fontSize: 48 }}>🕸️</div>
              <div>Select a campaign or search for an entity to visualize its network</div>
              <button className="btn btn-primary" onClick={() => setSelected(c[0]?.id)}>
                Load Demo Network
              </button>
            </div>
          ) : (
            <svg ref={svgRef} style={{ display: 'block', width: '100%' }} />
          )}
        </div>

        {/* Legend */}
        <div style={{ padding: '12px 20px', borderTop: '1px solid var(--border)', display: 'flex', gap: 16, flexWrap: 'wrap' }}>
          {Object.entries(nodeTypeColors).map(([type, color]) => (
            <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
              <div style={{ width: 10, height: 10, borderRadius: '50%', background: color }} />
              <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>{type}</span>
            </div>
          ))}
        </div>
      </div>

      {/* Node detail panel */}
      {selectedNode && (
        <div className="card" style={{ marginTop: 16, borderColor: 'var(--accent-dim)' }}>
          <div className="card-header">
            <h3>
              <span style={{ color: nodeTypeColors[selectedNode.label] || 'var(--accent)' }}>
                ● {selectedNode.label}
              </span>
              {' '}— {selectedNode.id}
            </h3>
            <button className="btn btn-outline btn-sm" onClick={() => setSelectedNode(null)}>✕</button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 8 }}>
            {Object.entries(selectedNode.properties || {}).map(([key, val]) => (
              <div key={key} style={{ padding: '6px 0', borderBottom: '1px solid var(--border)' }}>
                <div style={{ fontSize: 10, color: 'var(--text-muted)', textTransform: 'uppercase' }}>{key}</div>
                <div style={{ fontSize: 13, fontWeight: 600, marginTop: 2 }}>{String(val)}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

const demoCampaigns = [
  { id: 'cpg-001', name: 'IPL Betting Ring — Gurugram', risk_level: 'CRITICAL' },
  { id: 'cpg-002', name: 'Fake Zerodha Network', risk_level: 'HIGH' },
  { id: 'cpg-003', name: 'Digital Arrest Ring — NCR', risk_level: 'CRITICAL' },
]
