import { useState, useEffect, useCallback, useRef } from 'react'
import Typeahead from '../../components/common/Typeahead.jsx'
import StatusMessage from '../../components/common/StatusMessage.jsx'
import LoaderModal from '../../components/common/LoaderModal.jsx'
import PDFViewer from '../../components/common/PDFViewer.jsx'
import { loadRTCLocations, loadRTCCombinations, fetchRTCRecord, downloadRTCPdf } from '../../utils/api.js'

function removeNavBtns(html) {
  return html.replace(/<input[^>]*(btnFirst|btnPrev|btnNext|btnLast)[^>]*>/gi, '')
}

export default function RTCView() {
  const [locations, setLocations]         = useState([])
  const [locationInput, setLocationInput] = useState('')
  const [selectedLoc, setSelectedLoc]     = useState(null)

  const [combos, setCombos]               = useState([])
  const [comboInput, setComboInput]       = useState('')
  const [selectedCombo, setSelectedCombo] = useState(null)
  const [combosLoading, setCombosLoading] = useState(false)

  const [status, setStatus]   = useState(null)
  const [loading, setLoading] = useState(false)
  const [pdfBlob, setPdfBlob] = useState(null)
  const [pdfName, setPdfName] = useState('')

  const abortRef = useRef(null)

  useEffect(() => {
    loadRTCLocations()
      .then(data => setLocations(data))
      .catch(() => setStatus({ kind: 'error', message: 'Failed to load locations.' }))
  }, [])

  const filterLocations = useCallback((q) => {
    if (!q) return []
    const ql = q.toLowerCase()
    const t1 = [], t2 = []
    for (const loc of locations) {
      const vn = loc.village.toLowerCase()
      const item = { ...loc, name: loc.village, meta: `${loc.district} · ${loc.taluk} · ${loc.hobli}` }
      if (vn.startsWith(ql)) t1.push(item)
      else if (vn.includes(ql) || loc.taluk.toLowerCase().includes(ql) || loc.hobli.toLowerCase().includes(ql)) t2.push(item)
      if (t1.length + t2.length >= 200) break
    }
    return [...t1, ...t2].slice(0, 15)
  }, [locations])

  const handleLocSelect = useCallback(async (item) => {
    setSelectedLoc(item)
    setLocationInput(item.village)
    setSelectedCombo(null)
    setComboInput('')
    setCombos([])
    setPdfBlob(null); setPdfName('')
    setCombosLoading(true)
    setStatus({ kind: 'info', message: 'Loading survey combinations…' })
    try {
      const data = await loadRTCCombinations(item)
      setCombos(data)
      setStatus(null)
    } catch {
      setStatus({ kind: 'error', message: 'Failed to load combinations.' })
    } finally {
      setCombosLoading(false)
    }
  }, [])

  const filterCombos = useCallback((q) => {
    if (!q) return []
    const ql = q.toLowerCase()
    return combos
      .filter(c => c.label.toLowerCase().includes(ql) || c.survey.includes(ql))
      .slice(0, 20)
      .map(c => ({ ...c, name: c.label }))
  }, [combos])

  const handleComboSelect = useCallback((item) => {
    setSelectedCombo(item)
    setComboInput(item.label)
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!selectedLoc)   { setStatus({ kind: 'error', message: 'Please select a village.' }); return }
    if (!selectedCombo) { setStatus({ kind: 'error', message: 'Please select a survey combination.' }); return }

    setLoading(true)
    setPdfBlob(null); setPdfName('')
    setStatus({ kind: 'info', message: 'Fetching from Bhoomi portal… (20–30 sec)' })

    const controller = new AbortController()
    abortRef.current = controller
    const filename = `RTC_${selectedLoc.village}_${selectedCombo.label}.pdf`

    try {
      const data = await fetchRTCRecord({
        district_name:  selectedLoc.district,
        taluk_name:     selectedLoc.taluk,
        hobli_name:     selectedLoc.hobli,
        village_name:   selectedLoc.village,
        survey_number:  selectedCombo.survey,
        surnoc:         selectedCombo.surnoc,
        hissa:          selectedCombo.hissa,
      }, { signal: controller.signal })
      const kn = removeNavBtns(data.html_kn || '')

      setStatus({ kind: 'info', message: 'Rendering certificate PDF…' })
      const blob = await downloadRTCPdf({ html: kn, filename })
      setPdfBlob(blob); setPdfName(filename)
      setStatus({ kind: 'success', message: 'RTC fetched successfully.' })
    } catch (err) {
      if (err.name !== 'AbortError') {
        setStatus({ kind: 'error', message: err.message })
      }
    } finally {
      setLoading(false)
    }
  }

  function handleCancel() {
    abortRef.current?.abort()
    setLoading(false)
    setStatus(null)
  }

  function handleReset() {
    setSelectedLoc(null); setLocationInput('')
    setSelectedCombo(null); setComboInput('')
    setCombos([]); setPdfBlob(null); setPdfName('')
    setStatus(null)
  }

  return (
    <div className="page">
      <div className="page-heading">
        <div className="page-badge">
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#1a6b4a', display: 'inline-block' }} />
          Bhoomi Records
        </div>
        <h1 className="page-title">RTC</h1>
        <p className="page-subtitle">
          Fetch Rights, Tenancy &amp; Crops records from the Bhoomi portal
        </p>
        <ul className="page-features">
          <li>Live data from official Bhoomi portal</li>
          <li>Returns PDF document</li>
        </ul>
      </div>

      <div className="card" style={{ padding: 24 }}>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Village <span className="req">*</span></label>
            <Typeahead
              value={locationInput}
              onChange={setLocationInput}
              onSelect={handleLocSelect}
              onClear={() => { setSelectedLoc(null); setLocationInput(''); setCombos([]); setSelectedCombo(null); setComboInput('') }}
              filterFn={filterLocations}
              placeholder="Search village name…"
            />
          </div>

          <div className="field">
            <label>Survey / Combination <span className="req">*</span></label>
            <Typeahead
              value={comboInput}
              onChange={setComboInput}
              onSelect={handleComboSelect}
              onClear={() => { setSelectedCombo(null); setComboInput('') }}
              filterFn={filterCombos}
              placeholder={selectedLoc ? 'Type to search e.g. 1, 86…' : 'Select village first'}
              disabled={!selectedLoc || combosLoading}
            />
          </div>

          {status && (
            <div style={{ marginBottom: 12 }}>
              <StatusMessage kind={status.kind} message={status.message} />
            </div>
          )}

          <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
            <button type="submit" className="submit-btn" disabled={loading} style={{ flex: 1 }}>
              {loading
                ? <><i className="ti ti-loader" style={{ animation: 'spin 1s linear infinite' }} /> Fetching…</>
                : <><i className="ti ti-file-search" /> Search RTC Records</>
              }
            </button>
            {pdfBlob && (
              <button type="button" className="submit-btn" onClick={handleReset}
                style={{ flex: '0 0 auto', width: 48, background: 'var(--surface-2)', color: 'var(--text-muted)' }}>
                <i className="ti ti-refresh" />
              </button>
            )}
          </div>
        </form>
      </div>

      <PDFViewer blob={pdfBlob} filename={pdfName} />

      <LoaderModal visible={loading} onCancel={handleCancel} title="Fetching RTC from Bhoomi…" />
    </div>
  )
}
