import { useState } from 'react'

const EXAMPLES = [
  'What diseases does Ibuprofen treat?',
  'What genes are associated with type 2 diabetes mellitus?',
  'What compounds bind the TNF gene?',
  'What side effects does Aspirin cause?',
]

const C = {
  surface: '#252220',
  surfaceEl: '#2D2A28',
  border: '#3D3A38',
  borderFocus: '#D97659',
  textPrimary: '#F5F0E8',
  textSecondary: '#A09890',
  textMuted: '#6B6560',
  accent: '#D97659',
  accentHover: '#C4653F',
}

export default function QueryInput({ onQuery, loading }) {
  const [value, setValue] = useState('')
  const [focused, setFocused] = useState(false)

  const submit = () => { if (value.trim() && !loading) onQuery(value.trim()) }

  return (
    <div style={styles.wrap}>
      <div style={{ ...styles.inputRow, ...(focused ? styles.inputRowFocused : {}) }}>
        <svg style={styles.searchIcon} width="18" height="18" viewBox="0 0 18 18" fill="none">
          <circle cx="8" cy="8" r="5.5" stroke={focused ? C.accent : C.textMuted} strokeWidth="1.5" />
          <line x1="12.5" y1="12.5" x2="16" y2="16" stroke={focused ? C.accent : C.textMuted} strokeWidth="1.5" strokeLinecap="round" />
        </svg>
        <input
          style={styles.input}
          value={value}
          onChange={e => setValue(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && submit()}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder="Ask a biomedical question…"
          disabled={loading}
        />
        <button
          style={{ ...styles.btn, ...(loading || !value.trim() ? styles.btnDisabled : {}) }}
          onClick={submit}
          disabled={loading || !value.trim()}
        >
          {loading ? (
            <span style={styles.loadingRow}>
              <span style={styles.spinner} />
              Searching
            </span>
          ) : 'Search'}
        </button>
      </div>

      <div style={styles.examples}>
        <span style={styles.examplesLabel}>Try:</span>
        {EXAMPLES.map(ex => (
          <button
            key={ex}
            style={styles.pill}
            onClick={() => { setValue(ex); onQuery(ex) }}
            onMouseEnter={e => e.currentTarget.style.borderColor = C.accent}
            onMouseLeave={e => e.currentTarget.style.borderColor = C.border}
          >
            {ex}
          </button>
        ))}
      </div>
    </div>
  )
}

const styles = {
  wrap: {},
  inputRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 0,
    background: '#252220',
    border: '1px solid #3D3A38',
    borderRadius: 10,
    padding: '4px 4px 4px 14px',
    transition: 'border-color 0.15s',
  },
  inputRowFocused: { borderColor: '#D97659' },
  searchIcon: { flexShrink: 0, marginRight: 8 },
  input: {
    flex: 1,
    padding: '10px 0',
    background: 'none',
    border: 'none',
    color: '#F5F0E8',
    fontSize: 15,
    outline: 'none',
  },
  btn: {
    padding: '9px 20px',
    borderRadius: 7,
    background: '#D97659',
    color: '#fff',
    border: 'none',
    cursor: 'pointer',
    fontSize: 14,
    fontWeight: 600,
    letterSpacing: '-0.01em',
    transition: 'background 0.15s',
    flexShrink: 0,
    minWidth: 90,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
  },
  btnDisabled: { background: '#3D3A38', color: '#6B6560', cursor: 'not-allowed' },
  loadingRow: { display: 'flex', alignItems: 'center', gap: 8 },
  spinner: {
    width: 12,
    height: 12,
    border: '2px solid rgba(255,255,255,0.3)',
    borderTopColor: '#fff',
    borderRadius: '50%',
    animation: 'spin 0.7s linear infinite',
    display: 'block',
  },
  examples: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 8,
    marginTop: 12,
    alignItems: 'center',
  },
  examplesLabel: { fontSize: 12, color: '#6B6560', marginRight: 2 },
  pill: {
    padding: '5px 12px',
    borderRadius: 20,
    background: 'transparent',
    color: '#A09890',
    border: '1px solid #3D3A38',
    cursor: 'pointer',
    fontSize: 12,
    transition: 'border-color 0.15s, color 0.15s',
  },
}
