import { useState, useEffect, useCallback, useRef } from 'react'
import Typeahead from '../../components/common/Typeahead.jsx'
import StatusMessage from '../../components/common/StatusMessage.jsx'
import LoaderModal from '../../components/common/LoaderModal.jsx'
import PDFViewer from '../../components/common/PDFViewer.jsx'
import {
  loadEKhataAllWards,
  searchEKhata,
  getEKhataJobStatus,
  startEKhataDownload,
  getEKhataPdfBlob,
} from '../../utils/api.js'

export default function EKhataView() {
  const [wards, setWards]                 = useState([])
  const [wardsLoaded, setWardsLoaded]     = useState(false)
  const [wardInput, setWardInput]         = useState('')
  const [selectedWard, setSelectedWard]   = useState(null)
  const [ownerName, setOwnerName]         = useState('')

  const [status, setStatus]       = useState(null)
  const [loading, setLoading]     = useState(false)
  const [certLoading, setCertLoading] = useState(false)
  const [properties, setProperties]   = useState(null)
  const [certBlob, setCertBlob]       = useState(null)
  const [certTitle, setCertTitle]     = useState('')

  const pollRef        = useRef(null)
  const iframeRef      = useRef(null)
  const wardsLoadingRef = useRef(false)

  useEffect(() => {
    loadAllWards()
  }, [])

  async function loadAllWards() {
    if (wardsLoaded || wardsLoadingRef.current) return
    wardsLoadingRef.current = true
    try {
      const data = await loadEKhataAllWards()
      const allWards = []
      for (const zone of data.zones) {
        for (const ward of zone.wards) {
          allWards.push({
            zone_id:   zone.zone_id,
            zone_name: zone.zone_name,
            ward_id:   ward.ward_id,
            ward_name: ward.ward_name,
            name:      ward.ward_name,
            meta:      zone.zone_name,
          })
        }
      }
      setWards(allWards)
      setWardsLoaded(true)
    } catch {
      setStatus({ kind: 'error', message: 'Failed to load wards.' })
    } finally {
      wardsLoadingRef.current = false
    }
  }

  const filterWards = useCallback((q) => {
    if (!q || q.length < 1) return []
    const ql = q.toLowerCase()
    return wards
      .filter(w =>
        w.ward_name.toLowerCase().includes(ql) ||
        w.zone_name.toLowerCase().includes(ql)
      )
      .slice(0, 30)
  }, [wards])

  const handleWardInputChange = useCallback((v) => {
    setWardInput(v)
  }, [])

  const handleWardSelect = useCallback((item) => {
    setSelectedWard(item)
    setWardInput(item.ward_name)
    setProperties(null); setCertBlob(null)
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!selectedWard) { setStatus({ kind: 'error', message: 'Please select a ward.' }); return }
    if (!ownerName.trim()) { setStatus({ kind: 'error', message: 'Please enter owner name.' }); return }

    if (pollRef.current) clearInterval(pollRef.current)
    setLoading(true); setProperties(null); setCertBlob(null)
    setStatus({ kind: 'info', message: 'Searching…' })

    try {
      const res = await searchEKhata({
        zone_id:    selectedWard.zone_id,
        ward_id:    selectedWard.ward_id,
        owner_name: ownerName.trim(),
        page:       1,
        page_size:  20,
      })
      const jobId = res.job_id

      pollRef.current = setInterval(async () => {
        try {
          const data = await getEKhataJobStatus(jobId)
          if (data.status === 'done') {
            clearInterval(pollRef.current); setLoading(false)
            setProperties(data.results || [])
            if ((data.results || []).length === 0) {
              setStatus({ kind: 'warning', message: 'No properties found.' })
            } else {
              setStatus({ kind: 'success', message: `Found ${data.total || data.results.length} properties.` })
            }
          } else if (data.status === 'error') {
            clearInterval(pollRef.current); setLoading(false)
            setStatus({ kind: 'error', message: data.error || 'Search failed.' })
          }
        } catch {
          clearInterval(pollRef.current); setLoading(false)
        }
      }, 1000)
    } catch (err) {
      setLoading(false)
      setStatus({ kind: 'error', message: err.message })
    }
  }

  async function handleViewCert(prop) {
    setCertBlob(null); setCertLoading(true)
    setCertTitle(`E-Khata — ePID ${prop.epid}`)
    setStatus({ kind: 'info', message: 'Fetching certificate…' })
    try {
      const dlRes = await startEKhataDownload({ epid: prop.epid, prop })
      const jobId = dlRes.job_id

      const poll = setInterval(async () => {
        try {
          const data = await getEKhataJobStatus(jobId)
          if (data.status === 'done') {
            clearInterval(poll)
            const blob = await getEKhataPdfBlob(jobId)
            setCertBlob(blob)
            setCertLoading(false)
            setStatus({ kind: 'success', message: 'Certificate loaded.' })
            setTimeout(() => {
              iframeRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
            }, 100)
          } else if (data.status === 'error') {
            clearInterval(poll); setCertLoading(false)
            setStatus({ kind: 'error', message: data.error || 'Failed to fetch certificate.' })
          }
        } catch {
          clearInterval(poll); setCertLoading(false)
        }
      }, 1000)
    } catch (err) {
      setCertLoading(false)
      setStatus({ kind: 'error', message: err.message })
    }
  }

  useEffect(() => () => { if (pollRef.current) clearInterval(pollRef.current) }, [])

  return (
    <div className="page">
      <div className="page-heading">
        <div className="page-badge">
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#7c4a1a', display: 'inline-block' }} />
          BBMP Records
        </div>
        <h1 className="page-title">E-Khata</h1>
        <p className="page-subtitle">
          Search BBMP E-Khata records by ward and owner name
        </p>
        <ul className="page-features">
          <li>Search by owner name within a ward</li>
          <li>View and download Khata certificate</li>
          <li>Covers all BBMP zones and wards</li>
        </ul>
      </div>

      <div>
        <div className="card" style={{ padding: 24 }}>
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label>Ward <span className="req">*</span></label>
              <Typeahead
                value={wardInput}
                onChange={handleWardInputChange}
                onSelect={handleWardSelect}
                onClear={() => { setSelectedWard(null); setWardInput(''); setProperties(null); setCertBlob(null) }}
                filterFn={filterWards}
                placeholder="Search ward name…"
              />
            </div>

            <div className="field">
              <label>Owner Name <span className="req">*</span></label>
              <input
                type="text"
                value={ownerName}
                onChange={e => setOwnerName(e.target.value)}
                placeholder="Enter property owner's name"
              />
            </div>

            {status && (
              <div style={{ marginBottom: 12 }}>
                <StatusMessage kind={status.kind} message={status.message} />
              </div>
            )}

            <button type="submit" className="submit-btn" disabled={loading}>
              {loading
                ? <><i className="ti ti-loader" style={{ animation: 'spin 1s linear infinite' }} /> Searching…</>
                : <><i className="ti ti-building-community" /> Search E-Khata</>
              }
            </button>
          </form>
        </div>

        {properties !== null && (
          <div className="card" style={{ marginTop: 20, overflow: 'hidden' }}>
            <div className="result-viewer-bar">
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-muted)' }}>
                {properties.length} Properties Found
              </span>
            </div>
            {properties.length === 0 ? (
              <div style={{ padding: '24px', textAlign: 'center', color: 'var(--text-faint)', fontSize: 13 }}>
                No properties found for this search.
              </div>
            ) : (
              <div className="result-table-wrapper">
                <table className="result-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>ePID</th>
                      <th>SAS ID</th>
                      <th>Owner Name</th>
                      <th>Address</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {properties.map((p, i) => (
                      <tr key={i}>
                        <td>{i + 1}</td>
                        <td style={{ fontWeight: 600 }}>{p.epid || '—'}</td>
                        <td>{p.sas_id || '—'}</td>
                        <td>{p.owner_name || '—'}</td>
                        <td style={{ fontSize: 12 }}>{p.address || '—'}</td>
                        <td>
                          <button
                            type="button"
                            className="table-action-btn"
                            onClick={() => handleViewCert(p)}
                            disabled={certLoading}
                          >
                            View Khata
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {(certLoading || certBlob) && (
          <div ref={iframeRef}>
            {certLoading && (
              <div className="pdf-preview-wrapper" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-faint)', fontSize: 13 }}>
                <i className="ti ti-loader" style={{ animation: 'spin 1s linear infinite', fontSize: 24, display: 'block', marginBottom: 10 }} />
                Loading certificate…
              </div>
            )}
            <PDFViewer blob={certBlob} filename={certTitle} />
          </div>
        )}
      </div>

      <LoaderModal visible={loading} onCancel={() => {}} title="Searching E-Khata records…" />
    </div>
  )
}
