import { useMemo } from 'react'

const NODE_COLORS = {
  Compound: '#D97659',
  Disease: '#5BA4CF',
  Gene: '#4CAF81',
  Anatomy: '#CF9A5B',
  Pathway: '#A78CF0',
  SideEffect: '#EF6B6B',
  Symptom: '#F0C06B',
  default: '#A09890',
}

function extractField(raw, field) {
  const m = raw.match(new RegExp(`^${field}:\\s*(.+)`, 'm'))
  return m ? m[1].trim() : ''
}

function parseGraphData(raw) {
  if (!raw) return { nodes: [], links: [] }

  const answer = extractField(raw, 'ANSWER') || raw
  const reasoning = extractField(raw, 'REASONING')
  const sources = extractField(raw, 'SOURCES')
  const text = answer + ' ' + reasoning

  const nodes = new Map()
  const links = []
  let idx = 0

  // Genes: 2-6 uppercase letters/digits (TP53, TNF, BRCA1, PTGS2)
  const geneRe = /\b([A-Z][A-Z0-9]{1,5})\b/g
  const geneStop = new Set(['AND', 'OR', 'NOT', 'FOR', 'THE', 'WITH', 'FROM', 'INTO', 'THAN', 'THAT', 'USES', 'USES', 'SSE', 'API', 'URL'])
  let m
  while ((m = geneRe.exec(text)) !== null) {
    const name = m[1]
    if (!geneStop.has(name) && !nodes.has(name)) {
      nodes.set(name, { id: `n${idx++}`, label: 'Gene', name })
    }
  }

  // Compounds: title-case words ending in common pharmaceutical suffixes
  const compoundRe = /\b([A-Z][a-z]{3,}(?:in|ol|ine|ide|ate|one|an|en|ab|mab|nib|ib))\b/g
  while ((m = compoundRe.exec(text)) !== null) {
    const name = m[1]
    if (!nodes.has(name)) {
      nodes.set(name, { id: `n${idx++}`, label: 'Compound', name })
    }
  }

  // Diseases: lowercase multi-word phrases near disease keywords
  const diseaseRe = /\b((?:[a-z]+ ){0,3}(?:disease|cancer|disorder|syndrome|arthritis|diabetes|sclerosis|fibrosis|infection|carcinoma))\b/gi
  while ((m = diseaseRe.exec(text)) !== null) {
    const name = m[1].toLowerCase().trim()
    if (name.length > 5 && !nodes.has(name)) {
      nodes.set(name, { id: `n${idx++}`, label: 'Disease', name })
    }
  }

  // Source-type nodes when no entities extracted
  if (nodes.size === 0 && sources) {
    sources.split(',').forEach(s => {
      const src = s.trim()
      if (src) nodes.set(src, { id: `n${idx++}`, label: 'default', name: src })
    })
  }

  const nodeList = Array.from(nodes.values()).slice(0, 10)

  // Link consecutive entities (simple chain) to suggest relationships
  nodeList.slice(1).forEach((n, i) => {
    links.push({ source: nodeList[i].id, target: n.id, rel: '' })
  })

  return { nodes: nodeList, links }
}

function circleLayout(nodes, cx, cy, r) {
  return nodes.map((n, i) => {
    const angle = (2 * Math.PI * i) / nodes.length - Math.PI / 2
    return { ...n, x: cx + r * Math.cos(angle), y: cy + r * Math.sin(angle) }
  })
}

export default function GraphVisualization({ raw }) {
  const graph = useMemo(() => parseGraphData(raw), [raw])

  if (!graph.nodes.length) return null

  const W = 480, H = 260
  const cx = W / 2, cy = H / 2
  const r = Math.min(80, (Math.min(W, H) / 2) - 40)
  const positioned = circleLayout(graph.nodes, cx, cy, graph.nodes.length === 1 ? 0 : r)
  const posMap = Object.fromEntries(positioned.map(n => [n.id, n]))

  return (
    <div style={styles.wrap}>
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none">
            <circle cx="6.5" cy="6.5" r="3" stroke="#A09890" strokeWidth="1.2" />
            <circle cx="1.5" cy="1.5" r="1.2" fill="#A09890" opacity="0.6" />
            <circle cx="11.5" cy="1.5" r="1.2" fill="#A09890" opacity="0.6" />
            <circle cx="1.5" cy="11.5" r="1.2" fill="#A09890" opacity="0.6" />
            <circle cx="11.5" cy="11.5" r="1.2" fill="#A09890" opacity="0.6" />
            <line x1="3.5" y1="3.5" x2="5" y2="5" stroke="#A09890" strokeWidth="1" opacity="0.5" />
            <line x1="8" y1="5" x2="10.5" y2="2.5" stroke="#A09890" strokeWidth="1" opacity="0.5" />
          </svg>
          <span style={styles.label}>Graph View</span>
        </div>
        <span style={styles.count}>{graph.nodes.length} nodes · {graph.links.length} edges</span>
      </div>

      <svg width={W} height={H} style={styles.svg}>
        <defs>
          <marker id="arrow" markerWidth="6" markerHeight="6" refX="5" refY="3" orient="auto">
            <path d="M0,0 L0,6 L6,3 z" fill="#3D3A38" />
          </marker>
        </defs>

        {graph.links.map((link, i) => {
          const s = posMap[link.source], t = posMap[link.target]
          if (!s || !t) return null
          const mx = (s.x + t.x) / 2, my = (s.y + t.y) / 2
          return (
            <g key={i}>
              <line
                x1={s.x} y1={s.y} x2={t.x} y2={t.y}
                stroke="#3D3A38" strokeWidth="1.5"
                markerEnd="url(#arrow)"
              />
              {link.rel && (
                <text x={mx} y={my - 5} textAnchor="middle" style={styles.relLabel}>
                  {link.rel}
                </text>
              )}
            </g>
          )
        })}

        {positioned.map(node => {
          const color = NODE_COLORS[node.label] || NODE_COLORS.default
          return (
            <g key={node.id}>
              <circle cx={node.x} cy={node.y} r={14} fill={color} opacity="0.15" />
              <circle cx={node.x} cy={node.y} r={8} fill={color} />
              <text x={node.x} y={node.y + 24} textAnchor="middle" style={{ ...styles.nodeLabel, fill: color }}>
                {node.name.length > 14 ? node.name.slice(0, 13) + '…' : node.name}
              </text>
            </g>
          )
        })}
      </svg>

      <div style={styles.legend}>
        {[...new Set(graph.nodes.map(n => n.label))].slice(0, 4).map(label => (
          <div key={label} style={styles.legendItem}>
            <span style={{ ...styles.legendDot, background: NODE_COLORS[label] || NODE_COLORS.default }} />
            <span style={styles.legendText}>{label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

const styles = {
  wrap: {
    background: '#252220',
    borderRadius: 10,
    border: '1px solid #3D3A38',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '14px 16px 10px',
  },
  headerLeft: { display: 'flex', alignItems: 'center', gap: 7 },
  label: { fontSize: 11, fontWeight: 600, color: '#A09890', textTransform: 'uppercase', letterSpacing: '0.08em' },
  count: { fontSize: 11, color: '#6B6560' },
  svg: { display: 'block' },
  nodeLabel: { fontSize: 10, fontWeight: 500 },
  relLabel: { fontSize: 9, fill: '#6B6560', fontFamily: 'Inter, system-ui, sans-serif' },
  legend: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: '4px 16px',
    padding: '8px 16px 12px',
    borderTop: '1px solid #2D2A28',
  },
  legendItem: { display: 'flex', alignItems: 'center', gap: 5 },
  legendDot: { width: 6, height: 6, borderRadius: '50%', display: 'block', flexShrink: 0 },
  legendText: { fontSize: 11, color: '#6B6560' },
}
