import { useState, useEffect, useRef, useCallback } from 'react'
import QueryInput from './components/QueryInput.jsx'
import AnswerPanel from './components/AnswerPanel.jsx'
import ReasoningChain from './components/ReasoningChain.jsx'
import GraphVisualization from './components/GraphVisualization.jsx'
import HITLModal from './components/HITLModal.jsx'
import FeedbackBar from './components/FeedbackBar.jsx'

const USER_ID = `user_${Math.random().toString(36).slice(2, 8)}`

const C = {
  bg: '#141210',
  surface: '#1E1B19',
  surfaceEl: '#272421',
  border: '#353230',
  borderLight: '#2A2725',
  textPrimary: '#F5F0E8',
  textSecondary: '#9A9088',
  textMuted: '#5C5854',
  accent: '#D97659',
  accentGlow: 'rgba(217,118,89,0.15)',
}

// Pipeline step definitions — order matches the SequentialAgent execution
const PIPELINE_STEPS = [
  { key: 'orchestrator', label: 'Orchestrator', agentNames: ['biomedical_orchestrator'] },
  {
    key: 'parallel',
    label: 'Parallel Retrieval',
    parallel: true,
    agentNames: ['cypher_agent', 'semantic_agent', 'web_agent'],
    icons: {
      cypher_agent: '⬡',
      semantic_agent: '◎',
      web_agent: '⊕',
    },
    subLabels: {
      cypher_agent: 'Graph',
      semantic_agent: 'Semantic',
      web_agent: 'Web',
    },
  },
  { key: 'synthesis', label: 'Synthesis', agentNames: ['synthesis_agent'] },
]

function PipelineStep({ step, activeAgents }) {
  if (step.parallel) {
    const anyActive = step.agentNames.some(n => activeAgents.includes(n))
    return (
      <div style={pStyles.parallelBlock}>
        <div style={pStyles.parallelHeader}>
          <span style={pStyles.parallelLabel}>Parallel</span>
        </div>
        <div style={pStyles.parallelRow}>
          {step.agentNames.map(name => {
            const active = activeAgents.includes(name)
            const isCurrent = active && activeAgents[activeAgents.length - 1] === name
            return (
              <div
                key={name}
                style={{
                  ...pStyles.subChip,
                  ...(active ? pStyles.subChipActive : {}),
                  ...(isCurrent ? pStyles.subChipCurrent : {}),
                }}
              >
                {isCurrent && <span style={pStyles.pulsingDot} />}
                <span style={pStyles.subIcon}>{step.icons?.[name]}</span>
                <span>{step.subLabels?.[name] || name.replace('_agent', '')}</span>
              </div>
            )
          })}
        </div>
      </div>
    )
  }

  const name = step.agentNames[0]
  const active = activeAgents.includes(name)
  const isCurrent = active && activeAgents[activeAgents.length - 1] === name
  return (
    <div
      style={{
        ...pStyles.chip,
        ...(active ? pStyles.chipActive : {}),
        ...(isCurrent ? pStyles.chipCurrent : {}),
      }}
    >
      {isCurrent && <span style={pStyles.pulsingDot} />}
      {step.label}
    </div>
  )
}

export default function App() {
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [streamText, setStreamText] = useState('')
  const [activeAgents, setActiveAgents] = useState([])
  const [hitlEvent, setHitlEvent] = useState(null)
  const [lastQuery, setLastQuery] = useState('')
  const wsRef = useRef(null)
  const sessionIdRef = useRef(null)

  useEffect(() => {
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const ws = new WebSocket(`${proto}://${window.location.host}/ws/${USER_ID}`)
    ws.onmessage = (e) => {
      try {
        const event = JSON.parse(e.data)
        if (
          (event.type === 'low_confidence' || event.type === 'new_edge') &&
          event.session_id === sessionIdRef.current
        ) setHitlEvent(event)
      } catch {}
    }
    wsRef.current = ws
    return () => ws.close()
  }, [])

  const handleQuery = useCallback(async (query) => {
    const sessionId = `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
    sessionIdRef.current = sessionId
    setLoading(true)
    setResult(null)
    setStreamText('')
    setActiveAgents([])
    setHitlEvent(null)
    setLastQuery(query)

    try {
      const res = await fetch('/query/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query, user_id: USER_ID, session_id: sessionId }),
      })
      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n\n')
        buffer = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            const event = JSON.parse(line.slice(6))
            if (event.type === 'agent') {
              setActiveAgents(prev => [...new Set([...prev, event.name])])
            } else if (event.type === 'delta') {
              setStreamText(prev => prev + event.text)
            } else if (event.type === 'hitl') {
              setHitlEvent(event)
            } else if (event.type === 'done') {
              setResult(event)
              setStreamText('')
              setLoading(false)
            } else if (event.type === 'error') {
              setResult({ answer: `Error: ${event.message}`, confidence: 0, sources: '', reasoning: '', raw: '' })
              setLoading(false)
            }
          } catch {}
        }
      }
    } catch (err) {
      setResult({ answer: `Error: ${err.message}`, confidence: 0, sources: '', reasoning: '', raw: '' })
    } finally {
      setLoading(false)
    }
  }, [])

  const handleHITLClose = useCallback(() => setHitlEvent(null), [])

  return (
    <div style={styles.root}>
      {/* ── Header ── */}
      <header style={styles.header}>
        <div style={styles.headerInner}>
          <div style={styles.logoRow}>
            <div style={styles.logoIcon}>
              <svg width="22" height="22" viewBox="0 0 28 28" fill="none">
                <circle cx="14" cy="14" r="13" stroke={C.accent} strokeWidth="1.5" />
                <circle cx="14" cy="14" r="4" fill={C.accent} />
                <line x1="14" y1="1" x2="14" y2="8" stroke={C.accent} strokeWidth="1.5" />
                <line x1="14" y1="20" x2="14" y2="27" stroke={C.accent} strokeWidth="1.5" />
                <line x1="1" y1="14" x2="8" y2="14" stroke={C.accent} strokeWidth="1.5" />
                <line x1="20" y1="14" x2="27" y2="14" stroke={C.accent} strokeWidth="1.5" />
                <line x1="4.22" y1="4.22" x2="9.17" y2="9.17" stroke={C.accent} strokeWidth="1.5" />
                <line x1="18.83" y1="18.83" x2="23.78" y2="23.78" stroke={C.accent} strokeWidth="1.5" />
              </svg>
            </div>
            <div>
              <h1 style={styles.siteTitle}>Hetionet GraphRAG</h1>
              <p style={styles.siteSubtitle}>Biomedical knowledge graph · 47K nodes · 388K relationships</p>
            </div>
          </div>
          <div style={styles.statusPill}>
            <span style={styles.dotGreen} />
            <span style={styles.statusText}>Connected</span>
          </div>
        </div>
      </header>

      {/* ── Hero search ── */}
      <section style={styles.hero}>
        <h2 style={styles.heroHeading}>Ask a biomedical question</h2>
        <p style={styles.heroSub}>
          Query drugs, diseases, genes and their relationships across Hetionet's knowledge graph
        </p>
        <div style={styles.searchWrap}>
          <QueryInput onQuery={handleQuery} loading={loading} />
        </div>
      </section>

      {/* ── Main content ── */}
      <main style={styles.main}>

        {/* Pipeline progress */}
        {loading && (
          <div style={styles.pipelineCard}>
            <div style={styles.pipelineTitle}>
              <span style={styles.pipelineDot} />
              Running Pipeline
            </div>
            <div style={styles.pipelineRow}>
              {PIPELINE_STEPS.map((step, idx) => (
                <>
                  <PipelineStep key={step.key} step={step} activeAgents={activeAgents} />
                  {idx < PIPELINE_STEPS.length - 1 && (
                    <div key={`arrow-${idx}`} style={pStyles.arrow}>→</div>
                  )}
                </>
              ))}
            </div>
            {streamText && (
              <div style={styles.streamBox}>
                <p style={styles.streamText}>{streamText}<span style={styles.cursor}>▌</span></p>
              </div>
            )}
          </div>
        )}

        {/* Results */}
        {result && (
          <div style={styles.results}>
            <AnswerPanel
              answer={result.answer}
              confidence={result.confidence}
              sources={result.sources}
              citations={result.citations}
            />
            <div style={styles.twoCol}>
              <ReasoningChain reasoning={result.reasoning} />
              <GraphVisualization raw={result.raw} query={lastQuery} />
            </div>
            <FeedbackBar
              sessionId={result.session_id}
              query={lastQuery}
              answer={result.answer}
              userId={USER_ID}
            />
          </div>
        )}

        {/* Empty state */}
        {!result && !loading && (
          <div style={styles.emptyState}>
            <div style={styles.emptyGrid}>
              {[
                { icon: '⬡', title: 'Graph Retrieval', desc: 'Direct Cypher queries over 388K Hetionet relationships' },
                { icon: '◎', title: 'Semantic Search', desc: 'Vector embeddings + BM25 + CrossEncoder reranking' },
                { icon: '⊕', title: 'Web Augmentation', desc: 'Google Search fills post-2016 biomedical gaps' },
                { icon: '◈', title: 'Synthesized Answer', desc: 'Multi-source fusion with confidence score & HITL review' },
              ].map(card => (
                <div key={card.title} style={styles.featureCard}>
                  <div style={styles.featureIcon}>{card.icon}</div>
                  <div style={styles.featureTitle}>{card.title}</div>
                  <div style={styles.featureDesc}>{card.desc}</div>
                </div>
              ))}
            </div>
          </div>
        )}
      </main>

      {hitlEvent && <HITLModal event={hitlEvent} userId={USER_ID} onClose={handleHITLClose} />}
    </div>
  )
}

// ── Pipeline sub-styles ─────────────────────────────────────────
const pStyles = {
  chip: {
    padding: '10px 20px',
    borderRadius: 10,
    background: C.surfaceEl,
    border: `1px solid ${C.border}`,
    color: C.textMuted,
    fontSize: 14,
    fontWeight: 500,
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    transition: 'all 0.2s',
    whiteSpace: 'nowrap',
  },
  chipActive: {
    color: C.textSecondary,
    borderColor: '#4A4745',
    background: '#272421',
  },
  chipCurrent: {
    background: '#2D1C14',
    color: C.accent,
    borderColor: '#6B3A20',
    boxShadow: `0 0 12px ${C.accentGlow}`,
  },
  parallelBlock: {
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: 8,
  },
  parallelHeader: {
    fontSize: 11,
    fontWeight: 600,
    color: C.textMuted,
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
  },
  parallelLabel: {},
  parallelRow: {
    display: 'flex',
    gap: 8,
  },
  subChip: {
    padding: '8px 14px',
    borderRadius: 8,
    background: C.surfaceEl,
    border: `1px solid ${C.border}`,
    color: C.textMuted,
    fontSize: 13,
    fontWeight: 500,
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    transition: 'all 0.2s',
    whiteSpace: 'nowrap',
  },
  subChipActive: {
    color: C.textSecondary,
    borderColor: '#4A4745',
  },
  subChipCurrent: {
    background: '#2D1C14',
    color: C.accent,
    borderColor: '#6B3A20',
    boxShadow: `0 0 10px ${C.accentGlow}`,
  },
  subIcon: { fontSize: 14, lineHeight: 1 },
  pulsingDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: C.accent,
    boxShadow: `0 0 6px ${C.accent}`,
    display: 'block',
    flexShrink: 0,
  },
  arrow: {
    fontSize: 18,
    color: C.textMuted,
    display: 'flex',
    alignItems: 'center',
    paddingTop: 8,
  },
}

// ── Page-level styles ────────────────────────────────────────────
const styles = {
  root: {
    minHeight: '100vh',
    background: C.bg,
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif',
  },
  header: {
    borderBottom: `1px solid ${C.borderLight}`,
    background: C.bg,
    position: 'sticky',
    top: 0,
    zIndex: 10,
    backdropFilter: 'blur(12px)',
  },
  headerInner: {
    maxWidth: 1200,
    margin: '0 auto',
    padding: '14px 32px',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  logoRow: { display: 'flex', alignItems: 'center', gap: 14 },
  logoIcon: {
    width: 40,
    height: 40,
    borderRadius: 10,
    background: 'rgba(217,118,89,0.1)',
    border: '1px solid rgba(217,118,89,0.2)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
  },
  siteTitle: {
    fontSize: 17,
    fontWeight: 650,
    color: C.textPrimary,
    letterSpacing: '-0.03em',
  },
  siteSubtitle: { fontSize: 12, color: C.textMuted, marginTop: 2 },
  statusPill: {
    display: 'flex',
    alignItems: 'center',
    gap: 7,
    padding: '6px 14px',
    borderRadius: 20,
    background: 'rgba(76,175,80,0.08)',
    border: '1px solid rgba(76,175,80,0.2)',
  },
  dotGreen: {
    width: 7,
    height: 7,
    borderRadius: '50%',
    background: '#4CAF50',
    boxShadow: '0 0 8px #4CAF5088',
    display: 'block',
    flexShrink: 0,
  },
  statusText: { fontSize: 12, color: '#4CAF80', fontWeight: 500 },

  // Hero section
  hero: {
    textAlign: 'center',
    padding: '56px 32px 36px',
    maxWidth: 860,
    margin: '0 auto',
  },
  heroHeading: {
    fontSize: 36,
    fontWeight: 700,
    color: C.textPrimary,
    letterSpacing: '-0.04em',
    marginBottom: 12,
  },
  heroSub: {
    fontSize: 16,
    color: C.textSecondary,
    lineHeight: 1.6,
    marginBottom: 32,
    maxWidth: 560,
    margin: '0 auto 32px',
  },
  searchWrap: { maxWidth: 780, margin: '0 auto' },

  // Main
  main: {
    maxWidth: 1100,
    margin: '0 auto',
    padding: '0 32px 80px',
  },

  // Pipeline card
  pipelineCard: {
    background: C.surface,
    borderRadius: 14,
    border: `1px solid ${C.border}`,
    padding: '20px 28px',
    marginBottom: 28,
  },
  pipelineTitle: {
    fontSize: 12,
    fontWeight: 600,
    color: C.textMuted,
    textTransform: 'uppercase',
    letterSpacing: '0.1em',
    marginBottom: 20,
    display: 'flex',
    alignItems: 'center',
    gap: 8,
  },
  pipelineDot: {
    width: 6,
    height: 6,
    borderRadius: '50%',
    background: C.accent,
    boxShadow: `0 0 8px ${C.accent}`,
    display: 'block',
    flexShrink: 0,
    animation: 'pulse 1.5s ease-in-out infinite',
  },
  pipelineRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 16,
    flexWrap: 'wrap',
  },
  streamBox: {
    marginTop: 20,
    paddingTop: 16,
    borderTop: `1px solid ${C.borderLight}`,
  },
  streamText: {
    fontSize: 14,
    color: C.textSecondary,
    lineHeight: 1.8,
    whiteSpace: 'pre-wrap',
  },
  cursor: { color: C.accent },

  // Results
  results: { marginTop: 0 },
  twoCol: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: 16,
    marginTop: 16,
  },

  // Empty / feature cards
  emptyState: {
    marginTop: 40,
    paddingBottom: 40,
  },
  emptyGrid: {
    display: 'grid',
    gridTemplateColumns: 'repeat(4, 1fr)',
    gap: 16,
  },
  featureCard: {
    background: C.surface,
    borderRadius: 12,
    border: `1px solid ${C.border}`,
    padding: '24px 20px',
    textAlign: 'center',
  },
  featureIcon: {
    fontSize: 28,
    color: C.accent,
    marginBottom: 12,
  },
  featureTitle: {
    fontSize: 14,
    fontWeight: 600,
    color: C.textPrimary,
    marginBottom: 8,
    letterSpacing: '-0.01em',
  },
  featureDesc: {
    fontSize: 13,
    color: C.textSecondary,
    lineHeight: 1.6,
  },
}
