import { useState, useRef, useEffect, useCallback } from 'react'

function escHtml(s) {
  return s.replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c])
}

function hlText(text, q) {
  if (!q) return escHtml(text)
  const rx = new RegExp('(' + q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + ')', 'gi')
  return escHtml(text).replace(rx, '<mark>$1</mark>')
}

export default function Typeahead({
  items = [],
  value = '',
  onChange,
  onSelect,
  onClear,
  placeholder = 'Search…',
  renderItem,
  filterFn,
  maxResults = 15,
  disabled = false,
}) {
  const [open, setOpen] = useState(false)
  const [highlighted, setHighlighted] = useState(-1)
  const [matches, setMatches] = useState([])
  const inputRef = useRef(null)
  const listRef = useRef(null)

  const defaultFilter = useCallback((q) => {
    if (!q) return []
    const ql = q.toLowerCase()
    const t1 = [], t2 = []
    for (const item of items) {
      const name = (item.name || item.projectName || item.villageName || '').toLowerCase()
      if (name.startsWith(ql)) t1.push(item)
      else if (name.includes(ql)) t2.push(item)
      if (t1.length + t2.length >= 200) break
    }
    return [...t1, ...t2].slice(0, maxResults)
  }, [items, maxResults])

  const computeMatches = useCallback((q) => {
    if (!q || q.length < 1) { setMatches([]); setOpen(false); return }
    const fn = filterFn || defaultFilter
    const result = fn(q)
    setMatches(result)
    setHighlighted(-1)
    setOpen(result.length > 0)
  }, [filterFn, defaultFilter])

  function handleInput(e) {
    const q = e.target.value
    onChange?.(q)
    computeMatches(q)
  }

  function handleFocus() {
    if (value.trim()) computeMatches(value.trim())
  }

  function handleKeyDown(e) {
    if (!open) return
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      const next = Math.min(highlighted + 1, matches.length - 1)
      setHighlighted(next)
      listRef.current?.children[next]?.scrollIntoView({ block: 'nearest' })
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      const prev = Math.max(highlighted - 1, 0)
      setHighlighted(prev)
      listRef.current?.children[prev]?.scrollIntoView({ block: 'nearest' })
    } else if (e.key === 'Enter' && highlighted >= 0) {
      e.preventDefault()
      select(highlighted)
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  function select(i) {
    const item = matches[i]
    if (!item) return
    onSelect?.(item)
    setOpen(false)
    setHighlighted(-1)
  }

  useEffect(() => {
    function onMouseDown(e) {
      if (!inputRef.current?.contains(e.target) && !listRef.current?.contains(e.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onMouseDown)
    return () => document.removeEventListener('mousedown', onMouseDown)
  }, [])

  return (
    <div className="typeahead-wrapper">
      <div className="typeahead-input-row">
        <input
          ref={inputRef}
          type="text"
          value={value}
          onChange={handleInput}
          onFocus={handleFocus}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={disabled}
          autoComplete="off"
          spellCheck={false}
          aria-expanded={open}
          aria-autocomplete="list"
        />
        {value && (
          <button
            type="button"
            className="typeahead-clear"
            onClick={() => { onChange?.(''); onClear?.(); setOpen(false) }}
            aria-label="Clear"
          >
            ×
          </button>
        )}
      </div>
      {open && matches.length > 0 && (
        <div className="typeahead-results" ref={listRef} role="listbox">
          {matches.map((item, i) => (
            <div
              key={i}
              className={`typeahead-item${highlighted === i ? ' highlighted' : ''}`}
              role="option"
              aria-selected={highlighted === i}
              onMouseDown={(e) => { e.preventDefault(); select(i) }}
              onMouseOver={() => setHighlighted(i)}
            >
              {renderItem ? renderItem(item, value) : (
                <>
                  <span
                    className="typeahead-item-name"
                    dangerouslySetInnerHTML={{ __html: hlText(item.name || item.projectName || item.villageName || '', value) }}
                  />
                  {item.meta && (
                    <span
                      className="typeahead-item-meta"
                      dangerouslySetInnerHTML={{ __html: hlText(item.meta, value) }}
                    />
                  )}
                </>
              )}
            </div>
          ))}
        </div>
      )}
      {open && matches.length === 0 && value.length > 0 && (
        <div className="typeahead-results">
          <div className="typeahead-empty">No results found</div>
        </div>
      )}
    </div>
  )
}
