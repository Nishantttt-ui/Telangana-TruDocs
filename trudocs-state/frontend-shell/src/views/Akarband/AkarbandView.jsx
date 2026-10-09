import { useState, useEffect, useCallback } from 'react'
import Typeahead from '../../components/common/Typeahead.jsx'
import StatusMessage from '../../components/common/StatusMessage.jsx'
import LoaderModal from '../../components/common/LoaderModal.jsx'
import PDFViewer from '../../components/common/PDFViewer.jsx'
import { loadAkarbandLocations, loadAkarbandSurveys, fetchAkarbandRecord } from '../../utils/api.js'

export default function AkarbandView() {
  const [locations, setLocations]         = useState([])
  const [locationInput, setLocationInput] = useState('')
  const [selectedLoc, setSelectedLoc]     = useState(null)

  const [surveys, setSurveys]             = useState({})
  const [surveyInput, setSurveyInput]     = useState('')
  const [selectedSurvey, setSelectedSurvey] = useState(null)
  const [surveysLoading, setSurveysLoading] = useState(false)

  const [status, setStatus]   = useState(null)
  const [loading, setLoading] = useState(false)
  const [pdfBlob, setPdfBlob] = useState(null)
  const [pdfName, setPdfName] = useState('')

  useEffect(() => {
    loadAkarbandLocations()
      .then(data => setLocations(data))
      .catch(() => setStatus({ kind: 'error', message: 'Failed to load locations.' }))
  }, [])

  const filterLocations = useCallback((q) => {
    if (!q) return []
    const ql = q.toLowerCase()
    const t1 = [], t2 = []
    for (const loc of locations) {
      const vn = (loc.village_name || '').toLowerCase()
      const item = {
        ...loc,
        name: loc.village_name,
        meta: `${loc.district_name} · ${loc.taluk_name} · ${loc.hobli_name}`,
      }
      if (vn.startsWith(ql)) t1.push(item)
      else if (vn.includes(ql) || (loc.taluk_name || '').toLowerCase().includes(ql)) t2.push(item)
      if (t1.length + t2.length >= 200) break
    }
    return [...t1, ...t2].slice(0, 15)
  }, [locations])

  const handleLocSelect = useCallback(async (item) => {
    setSelectedLoc(item)
    setLocationInput(item.village_name)
    setSelectedSurvey(null); setSurveyInput(''); setSurveys({})
    setPdfBlob(null); setPdfName('')
    setSurveysLoading(true)
    setStatus({ kind: 'info', message: 'Loading surveys…' })
    try {
      const data = await loadAkarbandSurveys({
        distId: item.district_code,
        tlkId:  item.taluk_code,
        hblId:  item.hobli_code,
        vlgId:  item.village_bhm,
      })
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
    return Object.entries(surveys)
      .filter(([, v]) => {
        const label = v.label || `${v.Item1}/${v.Item2}/${v.Item3}`
        return label.toLowerCase().includes(ql) || v.Item1.includes(ql)
      })
      .slice(0, 20)
      .map(([, v]) => ({ ...v, name: v.label || `${v.Item1}/${v.Item2}/${v.Item3}` }))
  }, [surveys])

  const handleSurveySelect = useCallback((item) => {
    setSelectedSurvey(item)
    setSurveyInput(item.label || item.name)
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!selectedLoc)    { setStatus({ kind: 'error', message: 'Please select a village.' }); return }
    if (!selectedSurvey) { setStatus({ kind: 'error', message: 'Please select a survey.' }); return }

    setLoading(true); setPdfBlob(null); setPdfName('')
    setStatus({ kind: 'info', message: 'Fetching Akarband PDF…' })

    try {
      const result = await fetchAkarbandRecord({
        distId: selectedLoc.district_code,
        tlkId:  selectedLoc.taluk_code,
        hblId:  selectedLoc.hobli_code,
        vlgId:  selectedLoc.village_bhm,
        syno:   selectedSurvey.Item1,
        surnoc: selectedSurvey.Item2,
        hissa:  selectedSurvey.Item3,
      })

      let blob = null
      if (result.type === 'pdf_blob') {
        blob = result.blob
      } else if (result.type === 'json') {
        const data = result.data
        if (data.PdfFile) {
          const byteChars = atob(data.PdfFile)
          const arr = new Uint8Array(byteChars.length)
          for (let i = 0; i < byteChars.length; i++) arr[i] = byteChars.charCodeAt(i)
          blob = new Blob([arr], { type: 'application/pdf' })
        } else if (data.ReturnVal === 'NoParent') {
          throw new Error('Record not found in Bhoomi database.')
        } else if (data.IsMatch === -1) {
          throw new Error('Invalid Survey / Sarnok / Hissa combination.')
        } else {
          throw new Error('Unexpected response from Bhoomi.')
        }
      }

      if (blob) {
        const name = `akarband_${selectedLoc.village_name}_${selectedSurvey.Item1}.pdf`
        setPdfBlob(blob); setPdfName(name)
        setStatus({ kind: 'success', message: 'Akarband loaded successfully.' })
      }
    } catch (err) {
      setStatus({ kind: 'error', message: err.message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="page">
      <div className="page-heading">
        <div className="page-badge">
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#1a6b4a', display: 'inline-block' }} />
          Bhoomi Records
        </div>
        <h1 className="page-title">Akarband</h1>
        <p className="page-subtitle">
          Fetch Akarband (land measurement) records from Bhoomi
        </p>
        <ul className="page-features">
          <li>Official Bhoomi portal data</li>
          <li>Returns PDF document</li>
          <li>Downloadable</li>
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
              onClear={() => { setSelectedLoc(null); setLocationInput(''); setSurveys({}); setSelectedSurvey(null); setSurveyInput('') }}
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
              placeholder={selectedLoc ? 'Type to search…' : 'Select village first'}
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
              : <><i className="ti ti-map-2" /> View Akarband</>
            }
          </button>
        </form>
      </div>

      <PDFViewer blob={pdfBlob} filename={pdfName} />

      <LoaderModal visible={loading} onCancel={() => {}} title="Fetching Akarband from Bhoomi…" />
    </div>
  )
}
