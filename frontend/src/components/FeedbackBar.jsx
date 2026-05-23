import { useState } from 'react'

export default function FeedbackBar({ sessionId, query, answer, userId }) {
  const [submitted, setSubmitted] = useState(null)

  const submit = async (rating) => {
    setSubmitted(rating)
    await fetch('/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ session_id: sessionId, user_id: userId, query, answer, rating }),
    })
  }

  return (
    <div style={styles.wrap}>
      <span style={styles.label}>Was this helpful?</span>
      {submitted ? (
        <span style={styles.thanks}>
          <svg width="13" height="13" viewBox="0 0 13 13" fill="none" style={{ verticalAlign: 'middle', marginRight: 5 }}>
            <circle cx="6.5" cy="6.5" r="6" stroke="#4CAF50" strokeWidth="1.2" />
            <path d="M4 6.5l1.8 1.8L9 4.5" stroke="#4CAF50" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Thanks for the feedback
        </span>
      ) : (
        <div style={styles.btns}>
          <button
            style={styles.btn}
            onClick={() => submit('up')}
            onMouseEnter={e => { e.currentTarget.style.borderColor = '#4CAF50'; e.currentTarget.style.color = '#4CAF50' }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = '#3D3A38'; e.currentTarget.style.color = '#A09890' }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M2 8h2V13H2zM4 8l3-6.5 1 .5v4h4l-1 7H5V8H4z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
            </svg>
            Helpful
          </button>
          <button
            style={styles.btn}
            onClick={() => submit('down')}
            onMouseEnter={e => { e.currentTarget.style.borderColor = '#EF4444'; e.currentTarget.style.color = '#EF4444' }}
            onMouseLeave={e => { e.currentTarget.style.borderColor = '#3D3A38'; e.currentTarget.style.color = '#A09890' }}
          >
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M12 6h-2V1h2zM10 6l-3 6.5-1-.5V8H2l1-7h5v5h2z" stroke="currentColor" strokeWidth="1.2" strokeLinejoin="round" />
            </svg>
            Not helpful
          </button>
        </div>
      )}
    </div>
  )
}

const styles = {
  wrap: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    marginTop: 12,
    padding: '10px 16px',
    background: '#252220',
    borderRadius: 8,
    border: '1px solid #3D3A38',
  },
  label: { fontSize: 13, color: '#6B6560' },
  btns: { display: 'flex', gap: 8 },
  btn: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    padding: '5px 12px',
    borderRadius: 6,
    background: 'transparent',
    border: '1px solid #3D3A38',
    cursor: 'pointer',
    fontSize: 12,
    color: '#A09890',
    transition: 'border-color 0.15s, color 0.15s',
  },
  thanks: { fontSize: 13, color: '#4CAF50', display: 'flex', alignItems: 'center' },
}
