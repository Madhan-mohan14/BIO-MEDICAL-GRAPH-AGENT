import { useState } from 'react'

export default function ReasoningChain({ reasoning }) {
  const [open, setOpen] = useState(false)
  if (!reasoning) return null

  const steps = reasoning.split('\n').filter(l => l.trim())

  return (
    <div style={styles.wrap}>
      <button style={styles.toggle} onClick={() => setOpen(o => !o)}>
        <div style={styles.toggleLeft}>
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
            <circle cx="7" cy="7" r="6" stroke="#A09890" strokeWidth="1.2" />
            <path d="M5 7l1.5 1.5L9 5" stroke="#A09890" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span style={styles.label}>Reasoning</span>
          <span style={styles.stepCount}>{steps.length} steps</span>
        </div>
        <svg
          style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)', transition: 'transform 0.2s' }}
          width="14" height="14" viewBox="0 0 14 14" fill="none"
        >
          <path d="M3 5l4 4 4-4" stroke="#6B6560" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </button>

      {open && (
        <div style={styles.body}>
          {steps.map((step, i) => (
            <div key={i} style={styles.step}>
              <div style={styles.stepNum}>{i + 1}</div>
              <p style={styles.stepText}>{step.replace(/^\d+[\.\)]\s*/, '')}</p>
            </div>
          ))}
        </div>
      )}
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
  toggle: {
    width: '100%',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '14px 16px',
    background: 'none',
    border: 'none',
    cursor: 'pointer',
    color: '#A09890',
  },
  toggleLeft: { display: 'flex', alignItems: 'center', gap: 8 },
  label: { fontSize: 11, fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em', color: '#A09890' },
  stepCount: { fontSize: 11, color: '#6B6560', background: '#2D2A28', padding: '1px 7px', borderRadius: 10 },
  body: { padding: '4px 16px 16px', borderTop: '1px solid #2D2A28', marginTop: 0 },
  step: { display: 'flex', gap: 10, marginTop: 12, alignItems: 'flex-start' },
  stepNum: {
    width: 20, height: 20, borderRadius: '50%',
    background: '#2D2A28', border: '1px solid #3D3A38',
    fontSize: 10, fontWeight: 600, color: '#A09890',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
    flexShrink: 0, marginTop: 1,
  },
  stepText: { fontSize: 13, color: '#A09890', lineHeight: 1.6, whiteSpace: 'pre-wrap' },
}
