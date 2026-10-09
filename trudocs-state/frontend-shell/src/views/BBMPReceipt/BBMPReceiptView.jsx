import { useState, useEffect, useRef } from 'react'
import StatusMessage from '../../components/common/StatusMessage.jsx'
import PDFViewer from '../../components/common/PDFViewer.jsx'
import CaptchaField from '../../components/common/CaptchaField.jsx'
import { startBBMPReceipt, downloadBBMPReceipt } from '../../utils/api.js'

export default function BBMPReceiptView() {
  const [appNo, setAppNo]       = useState('')
  const [session, setSession]   = useState(null)   // { id, years, img }
  const [captcha, setCaptcha]   = useState('')
  const [status, setStatus]     = useState(null)
  const [loading, setLoading]   = useState(false)  // fetching captcha
  const [fetching, setFetching] = useState(false)  // fetching receipt
  const [receipt, setReceipt]   = useState(null)   // { blob, filename }
  const busy = loading || fetching

  const appRef     = useRef(null)
  const pdfRef     = useRef(null)
  const typingRef  = useRef(null)   // debounce timer for auto-loading the captcha
  const reqRef     = useRef(0)      // id of the latest captcha request (drops stale replies)

  useEffect(() => () => clearTimeout(typingRef.current), [])

  // The number box is locked while busy, which drops its focus — restore it after an error
  useEffect(() => {
    if (!busy && !session && status?.kind === 'error') appRef.current?.focus()
  }, [busy, session, status])

  function handleAppNoChange(e) {
    const digits = e.target.value.replace(/\D/g, '').slice(0, 10)
    setAppNo(digits)
    // A captcha belongs to one application number — drop it if the number changes
    reqRef.current += 1
    setSession(null); setReceipt(null); setStatus(null); setCaptcha('')
    // Like the portal itself, load years + captcha as soon as the number is complete
    clearTimeout(typingRef.current)
    if (digits.length === 10) {
      typingRef.current = setTimeout(() => loadCaptcha(false, digits), 400)
    }
  }

  // Opens a portal session for appNo. `keepStatus` leaves an existing message
  // (e.g. "wrong captcha") on screen when the fresh captcha loads fine.
  async function loadCaptcha(keepStatus = false, number = appNo) {
    if (!/^\d{10}$/.test(number)) {
      setStatus({ kind: 'error', message: 'Enter the 10-digit application number.' })
      return
    }
    const reqId = ++reqRef.current
    setLoading(true); setCaptcha('')
    if (!keepStatus) setStatus({ kind: 'info', message: 'Loading captcha…' })
    try {
      const data = await startBBMPReceipt(number)
      if (reqId !== reqRef.current) return          // number was edited meanwhile
      setSession({
        id:    data.session_id,
        years: data.years,
        img:   `data:${data.captcha_mime};base64,${data.captcha_b64}`,
      })
      if (!keepStatus) setStatus(null)
    } catch (err) {
      if (reqId !== reqRef.current) return
      setSession(null)
      setStatus({ kind: 'error', message: err.message })
    } finally {
      if (reqId === reqRef.current) setLoading(false)
    }
  }

  async function fetchReceipt(text = captcha) {
    if (!text.trim()) {
      setStatus({ kind: 'error', message: 'Enter the captcha shown in the image.' })
      return
    }
    setFetching(true); setReceipt(null)
    setStatus({ kind: 'info', message: 'Fetching receipt…' })
    try {
      const result = await downloadBBMPReceipt({ sessionId: session.id, year: session.years[0], captcha: text.trim() })
      setReceipt(result)
      setSession(null); setCaptcha('')       // the captcha is single-use
      setStatus({ kind: 'success', message: 'Receipt loaded.' })
      setTimeout(() => pdfRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100)
    } catch (err) {
      setStatus({ kind: 'error', message: err.message })
      // Rate-limited requests never reached the portal, so the captcha is still valid;
      // any other failure has used it up and needs a fresh one.
      if (err.code !== 429) await loadCaptcha(true)
    } finally {
      setFetching(false)
    }
  }

  function handleSubmit(e) {
    e.preventDefault()
    if (session) fetchReceipt()
    else loadCaptcha()
  }

  return (
    <div className="page">
      <div className="page-heading">
        <div className="page-badge">
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#7c4a1a', display: 'inline-block' }} />
          BBMP Records
        </div>
        <h1 className="page-title">Tax Receipt</h1>
        <p className="page-subtitle">
          Download BBMP property tax receipts by application number
        </p>
        <ul className="page-features">
          <li>Enter the 10-digit application number</li>
          <li>Type the 5-character captcha</li>
          <li>Preview and download the receipt PDF</li>
        </ul>
      </div>

      <div>
        <div className="card" style={{ padding: 24 }}>
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label>Application No. <span className="req">*</span></label>
              <input
                ref={appRef}
                type="text"
                inputMode="numeric"
                value={appNo}
                onChange={handleAppNoChange}
                disabled={busy}
                placeholder="10 digit No."
                autoComplete="off"
              />
            </div>

            {session && (
              <>
                <div className="field">
                  <label>Assessment Year</label>
                  <input
                    className="field-readonly"
                    type="text"
                    value={session.years[0]}
                    disabled
                    readOnly
                    aria-label="Assessment year"
                  />
                </div>

                <CaptchaField
                  image={session.img}
                  value={captcha}
                  onChange={setCaptcha}
                  onComplete={fetchReceipt}
                  onRefresh={() => loadCaptcha()}
                  busy={busy}
                />
              </>
            )}

            {status && (
              <div style={{ marginBottom: 12 }}>
                <StatusMessage kind={status.kind} message={status.message} />
              </div>
            )}

            <button type="submit" className="submit-btn" disabled={busy}>
              {busy
                ? <><i className="ti ti-loader" style={{ animation: 'spin 1s linear infinite' }} /> {fetching ? 'Fetching…' : 'Loading…'}</>
                : session
                  ? <><i className="ti ti-receipt-tax" /> Get Receipt</>
                  : <><i className="ti ti-receipt-tax" /> Continue</>
              }
            </button>
          </form>
        </div>

        {receipt && (
          <div ref={pdfRef}>
            <PDFViewer blob={receipt.blob} filename={receipt.filename} />
          </div>
        )}
      </div>
    </div>
  )
}
