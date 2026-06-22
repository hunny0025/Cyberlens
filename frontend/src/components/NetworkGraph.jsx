/**
 * CyberLens — NetworkGraph Component
 * =====================================
 * Reusable D3-style force-directed network graph for campaign intelligence.
 *
 * Props:
 *   nodes       — [{id, label, properties}]
 *   links       — [{source, target, type}]
 *   onNodeClick — (node) => void
 *   height      — number (default: 500)
 *   showMinimap — bool (default: false)
 */

import { useEffect, useRef, useCallback } from 'react'

const NODE_COLORS = {
  Channel:      '#cda869',
  PhoneNumber:  '#b91c1c',
  UPIId:        '#d97706',
  TelegramUser: '#a38256',
  ScamCampaign: '#b91c1c',
  Image:        '#adaba4',
  Domain:       '#a38256',
  QRCode:       '#75726a',
}

const NODE_RADIUS = {
  ScamCampaign: 22,
  Channel:      14,
  TelegramUser: 12,
  PhoneNumber:  10,
  UPIId:        10,
  Image:        8,
  Domain:       8,
  QRCode:       8,
}

const LINK_COLORS = {
  BELONGS_TO:    '#b91c1c',
  USES_PHONE:    '#d97706',
  USES_UPI:      '#16a34a',
  OPERATED_BY:   '#a38256',
  SHARES_CONTENT:'#adaba4',
  LINKED_TO:     '#75726a',
  HOSTS:         '#a38256',
  SIMILAR_TO:    '#75726a',
}

export default function NetworkGraph({ nodes = [], links = [], onNodeClick, height = 500, showMinimap = false }) {
  const svgRef = useRef(null)
  const animFrameRef = useRef(null)

  const renderGraph = useCallback(() => {
    if (!svgRef.current || !nodes.length) return

    const svg = svgRef.current
    const ns = 'http://www.w3.org/2000/svg'
    const container = svg.parentElement
    const W = container?.offsetWidth || 800
    const H = height

    // Clear previous render
    while (svg.firstChild) svg.removeChild(svg.firstChild)
    svg.setAttribute('width', W)
    svg.setAttribute('height', H)
    svg.setAttribute('viewBox', `0 0 ${W} ${H}`)

    // ── Defs: arrowhead markers ────────────────────────────────────
    const defs = document.createElementNS(ns, 'defs')

    // Glow filter for campaign nodes
    const filter = document.createElementNS(ns, 'filter')
    filter.setAttribute('id', 'glow')
    const feBlur = document.createElementNS(ns, 'feGaussianBlur')
    feBlur.setAttribute('stdDeviation', '4')
    feBlur.setAttribute('result', 'coloredBlur')
    const feMerge = document.createElementNS(ns, 'feMerge')
    ;['coloredBlur', 'SourceGraphic'].forEach(ref => {
      const n = document.createElementNS(ns, 'feMergeNode')
      n.setAttribute('in', ref)
      feMerge.appendChild(n)
    })
    filter.appendChild(feBlur)
    filter.appendChild(feMerge)
    defs.appendChild(filter)

    Object.entries(LINK_COLORS).forEach(([type, color]) => {
      const marker = document.createElementNS(ns, 'marker')
      marker.setAttribute('id', `arr-${type}`)
      marker.setAttribute('markerWidth', '8')
      marker.setAttribute('markerHeight', '8')
      marker.setAttribute('refX', '8')
      marker.setAttribute('refY', '3')
      marker.setAttribute('orient', 'auto')
      const path = document.createElementNS(ns, 'path')
      path.setAttribute('d', 'M0,0 L0,6 L8,3 z')
      path.setAttribute('fill', color)
      path.setAttribute('opacity', '0.7')
      marker.appendChild(path)
      defs.appendChild(marker)
    })
    svg.appendChild(defs)

    // ── Main group (for zoom/pan) ─────────────────────────────────
    const g = document.createElementNS(ns, 'g')

    // Background click for zoom reset
    const bg = document.createElementNS(ns, 'rect')
    bg.setAttribute('width', W)
    bg.setAttribute('height', H)
    bg.setAttribute('fill', 'transparent')
    g.appendChild(bg)

    svg.appendChild(g)

    // ── Build node data with initial positions ────────────────────
    const nodeData = nodes.map((n, i) => ({
      ...n,
      x: W / 2 + Math.cos((2 * Math.PI * i) / nodes.length) * Math.min(W, H) * 0.32,
      y: H / 2 + Math.sin((2 * Math.PI * i) / nodes.length) * Math.min(W, H) * 0.28,
      vx: 0,
      vy: 0,
      r: NODE_RADIUS[n.label] || 10,
      color: NODE_COLORS[n.label] || '#64748b',
      fixed: false,
    }))
    const nodeById = Object.fromEntries(nodeData.map(n => [n.id, n]))

    // ── Render links ──────────────────────────────────────────────
    const linkEls = links.map(l => {
      const color = LINK_COLORS[l.type] || '#475569'
      const line = document.createElementNS(ns, 'line')
      line.setAttribute('stroke', color)
      line.setAttribute('stroke-width', '1.5')
      line.setAttribute('opacity', '0.5')
      line.setAttribute('marker-end', `url(#arr-${l.type})`)
      g.appendChild(line)

      // Link label on hover
      const lbl = document.createElementNS(ns, 'text')
      lbl.setAttribute('fill', color)
      lbl.setAttribute('font-size', '8')
      lbl.setAttribute('font-family', 'Inter, sans-serif')
      lbl.setAttribute('text-anchor', 'middle')
      lbl.setAttribute('opacity', '0')
      lbl.textContent = l.type?.replace(/_/g, ' ') || ''
      g.appendChild(lbl)

      line.addEventListener('mouseenter', () => lbl.setAttribute('opacity', '0.9'))
      line.addEventListener('mouseleave', () => lbl.setAttribute('opacity', '0'))

      return { ...l, el: line, lblEl: lbl }
    })

    // ── Render nodes ──────────────────────────────────────────────
    const nodeEls = nodeData.map(n => {
      const group = document.createElementNS(ns, 'g')
      group.setAttribute('cursor', 'pointer')
      group.setAttribute('data-id', n.id)
      group.style.transition = 'transform 0.05s'

      const circle = document.createElementNS(ns, 'circle')
      circle.setAttribute('r', n.r)
      circle.setAttribute('fill', n.color)
      circle.setAttribute('stroke', '#ffffff')
      circle.setAttribute('stroke-width', '2')
      circle.setAttribute('opacity', '0.9')

      if (n.label === 'ScamCampaign') {
        circle.setAttribute('filter', 'url(#glow)')
        circle.setAttribute('stroke', '#ff6b6b')
        circle.setAttribute('stroke-width', '2.5')
      }

      // Pulse ring for ScamCampaign
      if (n.label === 'ScamCampaign') {
        const pulse = document.createElementNS(ns, 'circle')
        pulse.setAttribute('r', n.r + 4)
        pulse.setAttribute('fill', 'none')
        pulse.setAttribute('stroke', n.color)
        pulse.setAttribute('stroke-width', '1')
        pulse.setAttribute('opacity', '0.4')
        pulse.style.animation = 'pulseRing 2s infinite'
        group.appendChild(pulse)
      }

      const label = n.properties?.name || n.properties?.value || n.properties?.username || n.id
      const shortLabel = label.length > 14 ? label.slice(0, 12) + '…' : label

      const text = document.createElementNS(ns, 'text')
      text.setAttribute('text-anchor', 'middle')
      text.setAttribute('dy', n.r + 13)
      text.setAttribute('fill', '#94a3b8')
      text.setAttribute('font-size', '9')
      text.setAttribute('font-family', 'Inter, sans-serif')
      text.setAttribute('font-weight', '500')
      text.textContent = shortLabel

      group.appendChild(circle)
      group.appendChild(text)

      // Hover effect
      group.addEventListener('mouseenter', () => {
        circle.setAttribute('opacity', '1')
        circle.setAttribute('stroke-width', '3')
        text.setAttribute('fill', '#e2e8f0')
      })
      group.addEventListener('mouseleave', () => {
        if (!n.fixed) {
          circle.setAttribute('opacity', '0.9')
          circle.setAttribute('stroke-width', n.label === 'ScamCampaign' ? '2.5' : '2')
        }
        text.setAttribute('fill', '#94a3b8')
      })

      // Click
      group.addEventListener('click', (e) => {
        e.stopPropagation()
        onNodeClick?.(n)
      })

      // Drag
      let dragging = false, ox = 0, oy = 0
      group.addEventListener('mousedown', e => {
        dragging = true
        ox = e.clientX - n.x
        oy = e.clientY - n.y
        n.fixed = true
        e.stopPropagation()
        e.preventDefault()
      })
      svg.addEventListener('mousemove', e => {
        if (!dragging) return
        const rect = svg.getBoundingClientRect()
        n.x = e.clientX - rect.left - ox + n.x
        n.y = e.clientY - rect.top - oy + n.y
        n.vx = n.vy = 0
        n.x = e.clientX - ox
        n.y = e.clientY - oy
        updatePositions()
      })
      svg.addEventListener('mouseup', () => {
        dragging = false
        setTimeout(() => { n.fixed = false }, 800)
      })

      g.appendChild(group)
      return { ...n, groupEl: group }
    })

    // ── Position updater ──────────────────────────────────────────
    function updatePositions() {
      nodeEls.forEach(n => {
        const nd = nodeById[n.id] || n
        n.groupEl.setAttribute('transform', `translate(${nd.x.toFixed(1)},${nd.y.toFixed(1)})`)
      })
      linkEls.forEach(l => {
        const srcId = typeof l.source === 'string' ? l.source : l.source?.id
        const tgtId = typeof l.target === 'string' ? l.target : l.target?.id
        const src = nodeById[srcId]
        const tgt = nodeById[tgtId]
        if (!src || !tgt) return

        const dx = tgt.x - src.x, dy = tgt.y - src.y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const tgtR = tgt.r + 5

        l.el.setAttribute('x1', src.x.toFixed(1))
        l.el.setAttribute('y1', src.y.toFixed(1))
        l.el.setAttribute('x2', (tgt.x - (dx / dist) * tgtR).toFixed(1))
        l.el.setAttribute('y2', (tgt.y - (dy / dist) * tgtR).toFixed(1))
        l.lblEl.setAttribute('x', ((src.x + tgt.x) / 2).toFixed(1))
        l.lblEl.setAttribute('y', ((src.y + tgt.y) / 2 - 5).toFixed(1))
      })
    }

    // ── Force simulation ──────────────────────────────────────────
    let frame = 0
    const MAX_FRAMES = 300

    function simulate() {
      if (frame++ > MAX_FRAMES) {
        updatePositions()
        return
      }

      nodeData.forEach(n => {
        if (n.fixed) return
        // Repulsion
        nodeData.forEach(m => {
          if (n === m) return
          const dx = n.x - m.x, dy = n.y - m.y
          const dist2 = dx * dx + dy * dy + 0.1
          const force = 3500 / dist2
          const d = Math.sqrt(dist2)
          n.vx += (dx / d) * force
          n.vy += (dy / d) * force
        })
        // Center gravity
        n.vx += (W / 2 - n.x) * 0.002
        n.vy += (H / 2 - n.y) * 0.002
      })

      // Spring links
      linkEls.forEach(l => {
        const srcId = typeof l.source === 'string' ? l.source : l.source?.id
        const tgtId = typeof l.target === 'string' ? l.target : l.target?.id
        const src = nodeById[srcId]
        const tgt = nodeById[tgtId]
        if (!src || !tgt) return
        const dx = tgt.x - src.x, dy = tgt.y - src.y
        const dist = Math.sqrt(dx * dx + dy * dy) || 1
        const ideal = 130
        const force = (dist - ideal) * 0.025
        const fx = (dx / dist) * force
        const fy = (dy / dist) * force
        if (!src.fixed) { src.vx += fx; src.vy += fy }
        if (!tgt.fixed) { tgt.vx -= fx; tgt.vy -= fy }
      })

      // Integrate
      nodeData.forEach(n => {
        if (n.fixed) return
        n.vx *= 0.82; n.vy *= 0.82
        n.x = Math.max(n.r + 8, Math.min(W - n.r - 8, n.x + n.vx))
        n.y = Math.max(n.r + 8, Math.min(H - n.r - 8, n.y + n.vy))
      })

      updatePositions()
      animFrameRef.current = requestAnimationFrame(simulate)
    }

    simulate()
  }, [nodes, links, height])

  useEffect(() => {
    renderGraph()
    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current)
    }
  }, [renderGraph])

  // Re-render on resize
  useEffect(() => {
    const observer = new ResizeObserver(() => renderGraph())
    if (svgRef.current?.parentElement) {
      observer.observe(svgRef.current.parentElement)
    }
    return () => observer.disconnect()
  }, [renderGraph])

  return (
    <div style={{ width: '100%', height, position: 'relative', overflow: 'hidden' }}>
      <svg
        ref={svgRef}
        id="network-graph-svg"
        style={{ display: 'block', width: '100%', height: '100%' }}
      />
      {/* Legend */}
      <div style={{
        position: 'absolute', bottom: 8, left: 10,
        display: 'flex', gap: 8, flexWrap: 'wrap',
        background: 'rgba(26,26,24,0.9)',
        border: '1px solid var(--border)',
        padding: '4px 8px', borderRadius: 'var(--radius-sm)',
        backdropFilter: 'blur(4px)',
      }}>
        {Object.entries(NODE_COLORS).map(([type, color]) => (
          <div key={type} style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{ width: 8, height: 8, borderRadius: '50%', background: color, flexShrink: 0 }} />
            <span style={{ fontSize: 9, color: 'var(--text-secondary)' }}>{type}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
