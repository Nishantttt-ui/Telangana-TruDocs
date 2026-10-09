import { useState } from 'react'

const MIN_DATE = '2003-01-01'
const PRESETS = [
  // { label: '1 yr', value: '1' },
  // { label: '3 yrs', value: '3' },
  { label: '5 yrs', value: '5' },
  { label: '15 yrs', value: '15' },
  { label: '20 yrs', value: '20' },
  { label: 'Custom', value: 'custom' },
]

function presetHint(value) {
  if (value === 'custom') return null
  const y = parseFloat(value)
  if (!y) return null
  const from = new Date()
  from.setFullYear(from.getFullYear() - y)
  return `${from.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })} – Today`
}

export default function DurationPicker({ value, onChange, customRange, onCustomRange }) {
  const [modalOpen, setModalOpen] = useState(false)
  const [fromVal, setFromVal] = useState('')
  const [toVal, setToVal] = useState('')
  const [error, setError] = useState('')
  const todayStr = new Date().toISOString().slice(0, 10)

  function selectPreset(v) {
    if (v === 'custom') {
      setModalOpen(true)
    } else {
      onChange(v)
    }
  }

  function applyCustom() {
    setError('')
    if (!fromVal || !toVal) { setError('Please select both dates.'); return }
    if (fromVal > toVal) { setError('Start date must be before end date.'); return }
    if (fromVal < MIN_DATE || toVal > todayStr) { setError('Dates must be between 1 Jan 2003 and today.'); return }
    onCustomRange({ from: new Date(fromVal), to: new Date(toVal) })
    onChange('custom')
    setModalOpen(false)
  }

  const hint = value === 'custom' && customRange
    ? `${customRange.from.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })} – ${customRange.to.toLocaleDateString('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })}`
    : presetHint(value)

  return (
    <>
      <div className="duration-group">
        {PRESETS.map((p) => (
          <button
            key={p.value}
            type="button"
            className={`duration-chip${value === p.value ? ' selected' : ''}`}
            onClick={() => selectPreset(p.value)}
          >
            {p.label}
          </button>
        ))}
      </div>
      {hint && <div className="preset-hint">{hint}</div>}

      {modalOpen && (
        <div className="date-modal-overlay" onClick={(e) => e.target === e.currentTarget && setModalOpen(false)}>
          <div className="date-modal" role="dialog" aria-modal="true">
            <h3 className="date-modal-title">Custom Date Range</h3>
            <div className="date-modal-fields">
              <div className="field">
                <label>From</label>
                <input
                  type="date"
                  value={fromVal}
                  min={MIN_DATE}
                  max={toVal || todayStr}
                  onChange={(e) => { setFromVal(e.target.value); if (toVal && e.target.value > toVal) setToVal(e.target.value) }}
                />
              </div>
              <div className="field">
                <label>To</label>
                <input
                  type="date"
                  value={toVal}
                  min={fromVal || MIN_DATE}
                  max={todayStr}
                  onChange={(e) => { setToVal(e.target.value); if (fromVal && e.target.value < fromVal) setFromVal(e.target.value) }}
                />
              </div>
            </div>
            {error && <p className="date-modal-error">{error}</p>}
            <div className="date-modal-actions">
              <button type="button" className="btn-secondary" onClick={() => setModalOpen(false)}>Cancel</button>
              <button type="button" className="btn-primary" onClick={applyCustom}>Apply</button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
