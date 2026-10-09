import { useEffect, useRef } from 'react'

/**
 * Captcha box for portals whose captcha the END USER types. We never read or solve it.
 *
 *  - shows the image the backend relayed from the portal, plus a refresh button
 *  - focuses the box whenever a new image arrives
 *  - calls onComplete(text) the moment `length` characters are typed (no extra click)
 *  - while `busy` (loading a captcha / submitting) everything is locked, so the value
 *    can't change under an in-flight request
 *
 * The parent owns `value` and decides what onComplete does (usually: submit).
 * Pair it with a single-use captcha session on the backend (see SKILL.md §7).
 */
export default function CaptchaField({
  image,
  value,
  onChange,
  onComplete,
  onRefresh,
  length = 5,
  busy = false,
  label = 'Captcha',
}) {
  const inputRef = useRef(null)

  // Focus when a new image arrives AND whenever the box becomes usable again. The second
  // part matters: after a wrong captcha the new image lands while the input is still
  // disabled (focus() on a disabled input is a silent no-op), so we refocus once busy ends.
  useEffect(() => {
    if (image && !busy) inputRef.current?.focus()
  }, [image, busy])

  return (
    <div className="field">
      <label>{label} <span className="req">*</span></label>
      <div className="captcha-row">
        <img className="captcha-img" src={image} alt="Captcha" />
        <button
          type="button"
          className="captcha-refresh"
          onClick={onRefresh}
          disabled={busy}
          aria-label="Get a new captcha"
          title="New captcha"
        >
          <i className="ti ti-refresh" />
        </button>
      </div>
      <input
        ref={inputRef}
        type="text"
        maxLength={length}
        value={value}
        onChange={(e) => {
          const v = e.target.value
          onChange(v)
          if (v.length === length && !busy) onComplete?.(v)
        }}
        placeholder="Type the characters shown"
        autoComplete="off"
        disabled={busy}
      />
    </div>
  )
}
