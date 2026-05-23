import { useState } from 'react'

export default function HITLModal({ event, userId, onClose }) {
  const [loading, setLoading] = useState(false)
  const isNewEdge = event.type === 'new_edge' || event.event_type === 'new_edge'

  const handleAction = async (approved) => {
    if (!isNewEdge) { onClose(); return }
    setLoading(true)
    try {
      await fetch('/approve-edge', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: event.session_id,
          user_id: userId,
          edge: { new_edge: event.new_edge },
          approved,
        }),
      })
    } finally {
      setLoading(false)
      onClose()
    }
  }

  const pct = Math.round((event.confidence || 0) * 100)

  return (
    <div style={styles.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={styles.modal}>
        <div style={styles.iconRow}>
          <div style={{ ...styles.iconWrap, background: isNewEdge ? '#1C2A3A' : '#2A1C1C', borderColor: isNewEdge ? '#2D4A6A' : '#4A2D2D' }}>
            {isNewEdge ? (
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                <circle cx="5" cy="11" r="3" stroke="#5BA4CF" strokeWidth="1.5" />
                <circle cx="17" cy="11" r="3" stroke="#5BA4CF" strokeWidth="1.5" />
                <line x1="8" y1="11" x2="14" y2="11" stroke="#5BA4CF" strokeWidth="1.5" strokeDasharray="2 2" />
                <circle cx="11" cy="11" r="1.5" fill="#5BA4CF" />
              </svg>
            ) : (
              <svg width="22" height="22" viewBox="0 0 22 22" fill="none">
                <path d="M11 2L20 19H2L11 2Z" stroke="#D97659" strokeWidth="1.5" strokeLinejoin="round" />
                <line x1="11" y1="9" x2="11" y2="13" stroke="#D97659" strokeWidth="1.5" strokeLinecap="round" />
                <circle cx="11" cy="16" r="0.8" fill="#D97659" />
              </svg>
            )}
          </div>
        </div>

        <h2 style={styles.title}>
          {isNewEdge ? 'New Relationship Detected' : 'Low Confidence Answer'}
        </h2>

        <p style={styles.subtitle}>
          {isNewEdge
            ? 'The web agent found a potential new biomedical relationship not in Hetionet.'
            : `Confidence is ${pct}% — below the 70% threshold. Review before accepting this answer.`}
        </p>

        {isNewEdge && event.new_edge && (
          <div style={styles.edgeBox}>
            <span style={styles.edgeText}>{event.new_edge}</span>
          </div>
        )}

        {!isNewEdge && event.reasoning && (
          <div style={styles.reasoningBox}>
            <p style={styles.reasoningText}>{event.reasoning}</p>
          </div>
        )}

        <div style={styles.actions}>
          {isNewEdge && (
            <button
              style={styles.approveBtn}
              onClick={() => handleAction(true)}
              disabled={loading}
              onMouseEnter={e => !loading && (e.currentTarget.style.background = '#2E5C3E')}
              onMouseLeave={e => e.currentTarget.style.background = '#1C3A2E'}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                <path d="M2.5 7l3 3 6-6" stroke="#4CAF81" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
              Approve & Write to Graph
            </button>
          )}
          <button
            style={{ ...styles.dismissBtn, ...(isNewEdge ? {} : styles.dismissBtnFull) }}
            onClick={() => handleAction(false)}
            disabled={loading}
            onMouseEnter={e => !loading && (e.currentTarget.style.background = '#2D2A28')}
            onMouseLeave={e => e.currentTarget.style.background = 'transparent'}
          >
            {isNewEdge ? 'Reject' : 'Dismiss'}
          </button>
        </div>
      </div>
    </div>
  )
}

const styles = {
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.6)',
    backdropFilter: 'blur(4px)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 100,
  },
  modal: {
    background: '#252220',
    borderRadius: 14,
    padding: '28px 28px 24px',
    maxWidth: 440,
    width: '90%',
    border: '1px solid #3D3A38',
    boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
  },
  iconRow: { display: 'flex', justifyContent: 'center', marginBottom: 16 },
  iconWrap: {
    width: 52, height: 52, borderRadius: 14,
    border: '1px solid',
    display: 'flex', alignItems: 'center', justifyContent: 'center',
  },
  title: { fontSize: 17, fontWeight: 600, color: '#F5F0E8', textAlign: 'center', marginBottom: 8 },
  subtitle: { fontSize: 13, color: '#A09890', textAlign: 'center', lineHeight: 1.6, marginBottom: 16 },
  edgeBox: {
    background: '#1C2A3A',
    border: '1px solid #2D4A6A',
    borderRadius: 8,
    padding: '10px 14px',
    marginBottom: 20,
  },
  edgeText: { fontSize: 12, color: '#5BA4CF', fontFamily: 'monospace', wordBreak: 'break-all' },
  reasoningBox: {
    background: '#2D2A28',
    borderRadius: 8,
    padding: '10px 14px',
    marginBottom: 20,
    maxHeight: 120,
    overflowY: 'auto',
  },
  reasoningText: { fontSize: 12, color: '#A09890', lineHeight: 1.6 },
  actions: { display: 'flex', gap: 10 },
  approveBtn: {
    flex: 1,
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: 7,
    padding: '10px 16px',
    borderRadius: 8,
    background: '#1C3A2E',
    border: '1px solid #2D5C44',
    color: '#4CAF81',
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: 500,
    transition: 'background 0.15s',
  },
  dismissBtn: {
    flex: 1,
    padding: '10px 16px',
    borderRadius: 8,
    background: 'transparent',
    border: '1px solid #3D3A38',
    color: '#A09890',
    cursor: 'pointer',
    fontSize: 13,
    fontWeight: 500,
    transition: 'background 0.15s',
  },
  dismissBtnFull: { flex: 'none', width: '100%' },
}
