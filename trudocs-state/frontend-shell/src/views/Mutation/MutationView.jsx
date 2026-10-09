import { useState, useEffect, useCallback, useRef } from 'react'
import Typeahead from '../../components/common/Typeahead.jsx'
import StatusMessage from '../../components/common/StatusMessage.jsx'
import LoaderModal from '../../components/common/LoaderModal.jsx'
import PDFViewer from '../../components/common/PDFViewer.jsx'
import {
  loadMutationLocations,
  loadMutationSurveys,
  startMutationFetch,
  getMutationJobStatus,
  downloadMutationPdf,
} from '../../utils/api.js'

export default function MutationView() {
  const [locations, setLocations]         = useState([])
  const [locationInput, setLocationInput] = useState('')
  const [selectedLoc, setSelectedLoc]     = useState(null)

  const [surveys, setSurveys]             = useState([])
  const [surveyInput, setSurveyInput]     = useState('')
  const [selectedSurvey, setSelectedSurvey] = useState(null)
  const [surveysLoading, setSurveysLoading] = useState(false)

  const [status, setStatus]   = useState(null)
  const [loading, setLoading] = useState(false)
  const [pdfBlob, setPdfBlob] = useState(null)
  const [pdfName, setPdfName] = useState('')

  const pollRef = useRef(null)

  useEffect(() => {
    loadMutationLocations()
      .then(data => setLocations(data))
      .catch(() => setStatus({ kind: 'error', message: 'Failed to load locations.' }))
    return () => { if (pollRef.current) clearInterval(pollRef.current) }
  }, [])

  const filterLocations = useCallback((q) => {
    if (!q) return []
    const ql = q.toLowerCase()
    const t1 = [], t2 = []
    for (const loc of locations) {
      const vn = (loc.village || '').toLowerCase()
      const item = { ...loc, name: loc.village, meta: `${loc.district} · ${loc.taluk} · ${loc.hobli}` }
      if (vn.startsWith(ql)) t1.push(item)
      else if (vn.includes(ql) || (loc.taluk || '').toLowerCase().includes(ql)) t2.push(item)
      if (t1.length + t2.length >= 200) break
    }
    return [...t1, ...t2].slice(0, 15)
  }, [locations])

  const handleLocSelect = useCallback(async (item) => {
    setSelectedLoc(item)
    setLocationInput(item.village)
    setSelectedSurvey(null); setSurveyInput(''); setSurveys([])
    setPdfBlob(null); setPdfName('')
    setSurveysLoading(true)
    setStatus({ kind: 'info', message: 'Loading surveys…' })
    try {
      const data = await loadMutationSurveys(item.village)
      setSurveys(data)
      setStatus(null)
    } catch {
      setStatus({ kind: 'error', message: 'Failed to load surveys.' })
    } finally {
      setSurveysLoading(false)
    }
  }, [])

  const filterSurveys = useCallback((q) => {
    if (!q) return []
    const ql = q.toLowerCase()
    return surveys
      .filter(c => {
        const label = c.display || c.label || `${c.survey_no}/${c.hissa || '*'}`
        return label.toLowerCase().includes(ql)
      })
      .slice(0, 20)
      .map(c => ({ ...c, name: c.display || c.label || `${c.survey_no}/${c.hissa || '*'}` }))
  }, [surveys])

  const handleSurveySelect = useCallback((item) => {
    setSelectedSurvey(item)
    setSurveyInput(item.display || item.label || item.name)
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!selectedLoc)    { setStatus({ kind: 'error', message: 'Please select a village.' }); return }
    if (!selectedSurvey) { setStatus({ kind: 'error', message: 'Please select a survey.' }); return }

    if (pollRef.current) clearInterval(pollRef.current)
    setLoading(true); setPdfBlob(null); setPdfName('')
    setStatus({ kind: 'info', message: 'Fetching Mutation… please wait' })

    const village = selectedLoc.village
    const survey  = selectedSurvey.display || selectedSurvey.label || 'cert'

    try {
      const payload = {
        district:  selectedLoc.district,
        taluk:     selectedLoc.taluk,
        hobli:     selectedLoc.hobli,
        village:   selectedLoc.village,
        survey_no: selectedSurvey.survey_no,
        hissa:     selectedSurvey.hissa,
        label:     selectedSurvey.display || selectedSurvey.label,
      }
      const res = await startMutationFetch(payload)
      const id = res.job_id

      pollRef.current = setInterval(async () => {
        try {
          const data = await getMutationJobStatus(id)
          if (data.latest_log) setStatus({ kind: 'info', message: data.latest_log.msg })
          if (data.status === 'done') {
            clearInterval(pollRef.current)
            if (data.success > 0) {
              setStatus({ kind: 'info', message: 'Rendering certificate PDF…' })
              try {
                const blob = await downloadMutationPdf(id)
                setPdfBlob(blob)
                setPdfName(`Mutation_${village}_${survey}.pdf`)
                setStatus({ kind: 'success', message: 'Mutation certificate fetched successfully.' })
              } catch {
                setStatus({ kind: 'error', message: 'Certificate not available on server. Try fetching again.' })
              }
            } else {
              setStatus({ kind: 'error', message: 'No certificate found for this survey number.' })
            }
            setLoading(false)
          } else if (data.status === 'error') {
            clearInterval(pollRef.current)
            setLoading(false)
            setStatus({ kind: 'error', message: 'Error fetching mutation.' })
          }
        } catch {
          clearInterval(pollRef.current); setLoading(false)
          setStatus({ kind: 'error', message: 'Connection error while checking status.' })
        }
      }, 1500)
    } catch (err) {
      setLoading(false)
      setStatus({ kind: 'error', message: err.message })
    }
  }

  function handleCancel() {
    if (pollRef.current) clearInterval(pollRef.current)
    setLoading(false)
    setStatus(null)
  }

  return (
    <div className="page">
      <div className="page-heading">
        <div className="page-badge">
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#1a6b4a', display: 'inline-block' }} />
          Bhoomi Records
        </div>
        <h1 className="page-title">Mutation</h1>
        <p className="page-subtitle">
          Fetch Mutation (Pahani) certificate from Bhoomi portal
        </p>
        <ul className="page-features">
          <li>Official Bhoomi portal data</li>
          <li>Async fetch with live status updates</li>
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
              onClear={() => { setSelectedLoc(null); setLocationInput(''); setSurveys([]); setSelectedSurvey(null); setSurveyInput('') }}
              filterFn={filterLocations}
              placeholder="Search village name…"
            />
          </div>

          <div className="field">
            <label>Survey No <span className="req">*</span></label>
            <Typeahead
              value={surveyInput}
              onChange={setSurveyInput}
              onSelect={handleSurveySelect}
              onClear={() => { setSelectedSurvey(null); setSurveyInput('') }}
              filterFn={filterSurveys}
              placeholder={selectedLoc ? 'Type to search e.g. 1, 86…' : 'Select village first'}
              disabled={!selectedLoc || surveysLoading}
            />
          </div>

          {status && (
            <div style={{ marginBottom: 12 }}>
              <StatusMessage kind={status.kind} message={status.message} />
            </div>
          )}

          <button type="submit" className="submit-btn" disabled={loading}>
            {loading
              ? <><i className="ti ti-loader" style={{ animation: 'spin 1s linear infinite' }} /> Fetching…</>
              : <><i className="ti ti-certificate" /> Search Mutation Records</>
            }
          </button>
        </form>
      </div>

      <PDFViewer blob={pdfBlob} filename={pdfName} />

      <LoaderModal visible={loading} onCancel={handleCancel} title="Fetching Mutation from Bhoomi…" />
    </div>
  )
}
