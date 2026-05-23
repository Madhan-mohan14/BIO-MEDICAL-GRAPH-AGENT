const C = {
  surface: '#252220',
  border: '#3D3A38',
  textPrimary: '#F5F0E8',
  textSecondary: '#A09890',
  accent: '#D97659',
}

const SOURCE_COLORS = {
  graph: { bg: '#1C3A2E', text: '#4CAF81', border: '#2D5C44' },
  web: { bg: '#1C2A3A', text: '#5BA4CF', border: '#2D4A6A' },
  semantic: { bg: '#3A2A1C', text: '#CF9A5B', border: '#6A4A2D' },
  mixed: { bg: '#2A2820', text: '#B8A878', border: '#4A4428' },
}

export default function AnswerPanel({ answer, confidence, sources, citations }) {
  const pct = Math.round((confidence || 0) * 100)
  const barColor = pct >= 90 ? '#4CAF50' : pct >= 70 ? '#D97659' : '#EF4444'
  const sourceKey = (sources || 'mixed').split(',')[0].trim()
  const sc = SOURCE_COLORS[sourceKey] || SOURCE_COLORS.mixed
  const citeList = Array.isArray(citations) ? citations.filter(Boolean) : []

  return (
    <div style={styles.wrap}>
      <div style={styles.header}>
        <span style={styles.label}>Answer</span>
        <span style={{ ...styles.badge, background: sc.bg, color: sc.text, border: `1px solid ${sc.border}` }}>
          {sources || 'mixed'}
        </span>
      </div>

      <p style={styles.answer}>{answer || '—'}</p>

      <div style={styles.confRow}>
        <span style={styles.confLabel}>Confidence</span>
        <div style={styles.barTrack}>
          <div style={{ ...styles.barFill, width: `${pct}%`, background: barColor }} />
        </div>
        <span style={{ ...styles.confPct, color: barColor }}>{pct}%</span>
      </div>

      {citeList.length > 0 && (
        <div style={styles.citations}>
          <span style={styles.citeLabel}>Sources</span>
          <div style={styles.citeList}>
            {citeList.map((url, i) => {
              let host = url
              try { host = new URL(url).hostname.replace('www.', '') } catch {}
              return (
                <a key={i} href={url} target="_blank" rel="noopener noreferrer" style={styles.citeLink}>
                  <svg width="10" height="10" viewBox="0 0 10 10" fill="none" style={{ flexShrink: 0 }}>
                    <path d="M1 9L9 1M9 1H4M9 1V6" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
                  </svg>
                  {host}
                </a>
              )
            })}
          </div>
        </div>
      )}
    </div>
  )
}

const styles = {
  wrap: {
    background: '#252220',
    borderRadius: 10,
    padding: '20px 24px',
    border: '1px solid #3D3A38',
  },
  header: { display: 'flex', alignItems: 'center', gap: 10, marginBottom: 14 },
  label: {
    fontSize: 11,
    fontWeight: 600,
    color: '#A09890',
    textTransform: 'uppercase',
    letterSpacing: '0.08em',
  },
  badge: {
    fontSize: 11,
    padding: '2px 9px',
    borderRadius: 20,
    fontWeight: 500,
  },
  answer: {
    fontSize: 15,
    lineHeight: 1.7,
    color: '#F5F0E8',
    fontWeight: 400,
  },
  confRow: { display: 'flex', alignItems: 'center', gap: 12, marginTop: 18 },
  confLabel: { fontSize: 12, color: '#A09890', minWidth: 80, flexShrink: 0 },
  barTrack: {
    flex: 1,
    height: 4,
    background: '#3D3A38',
    borderRadius: 2,
    overflow: 'hidden',
  },
  barFill: {
    height: '100%',
    borderRadius: 2,
    transition: 'width 0.6s cubic-bezier(0.4, 0, 0.2, 1)',
  },
  confPct: { fontSize: 13, fontWeight: 600, minWidth: 36, textAlign: 'right', flexShrink: 0 },
  citations: { marginTop: 16, paddingTop: 14, borderTop: '1px solid #2D2A28' },
  citeLabel: { fontSize: 11, fontWeight: 600, color: '#6B6560', textTransform: 'uppercase', letterSpacing: '0.08em' },
  citeList: { display: 'flex', flexWrap: 'wrap', gap: 6, marginTop: 8 },
  citeLink: {
    display: 'inline-flex', alignItems: 'center', gap: 4,
    fontSize: 11, color: '#5BA4CF',
    background: '#1C2A3A', border: '1px solid #2D4A6A',
    borderRadius: 4, padding: '3px 8px',
    textDecoration: 'none',
  },
}
