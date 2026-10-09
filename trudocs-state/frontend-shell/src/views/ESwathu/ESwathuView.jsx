import { useState, useEffect, useCallback, useRef } from 'react'
import Typeahead from '../../components/common/Typeahead.jsx'
import StatusMessage from '../../components/common/StatusMessage.jsx'
import LoaderModal from '../../components/common/LoaderModal.jsx'
import PDFViewer from '../../components/common/PDFViewer.jsx'
import { loadESwathuLocations, searchESwathu, getESwathuCertUrl } from '../../utils/api.js'

export default function ESwathuView() {
  const [locations, setLocations]         = useState([])
  const [locationInput, setLocationInput] = useState('')
  const [selectedLoc, setSelectedLoc]     = useState(null)
  const [searchVal, setSearchVal]         = useState('')

  const [status, setStatus]       = useState(null)
  const [loading, setLoading]     = useState(false)
  const [certLoading, setCertLoading] = useState(false)
  const [properties, setProperties]   = useState(null)
  const [certBlob, setCertBlob]       = useState(null)
  const [certTitle, setCertTitle]     = useState('')

  const certRef = useRef(null)

  useEffect(() => {
    loadESwathuLocations()
      .then(data => setLocations(data))
      .catch(() => setStatus({ kind: 'error', message: 'Failed to load villages.' }))
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
        meta: `${loc.panchayat_name} · ${loc.taluk_name} · ${loc.district_name}`,
      }
      if (vn.startsWith(ql)) t1.push(item)
      else if (
        vn.includes(ql) ||
        (loc.taluk_name || '').toLowerCase().includes(ql) ||
        (loc.district_name || '').toLowerCase().includes(ql)
      ) t2.push(item)
      if (t1.length + t2.length >= 200) break
    }
    return [...t1, ...t2].slice(0, 15)
  }, [locations])

  const handleLocSelect = useCallback((item) => {
    setSelectedLoc(item)
    setLocationInput(`${item.village_name} · ${item.panchayat_name} · ${item.taluk_name}`)
    setProperties(null); setCertBlob(null)
  }, [])

  async function handleSubmit(e) {
    e.preventDefault()
    if (!selectedLoc) { setStatus({ kind: 'error', message: 'Please select a village.' }); return }

    setLoading(true); setProperties(null); setCertBlob(null)
    setStatus({ kind: 'info', message: 'Searching properties…' })

    try {
      const data = await searchESwathu({
        district_code:  selectedLoc.district_code,
        taluk_code:     selectedLoc.taluk_code,
        panchayat_code: selectedLoc.panchayat_code,
        village_code:   selectedLoc.village_code,
        search_type:    '0',
        search_val:     searchVal.trim(),
      })
      setProperties(data.properties || [])
      if ((data.properties || []).length === 0) {
        setStatus({ kind: 'warning', message: 'No properties found.' })
      } else {
        setStatus({ kind: 'success', message: `Found ${data.count || data.properties.length} properties.` })
      }
    } catch (err) {
      setStatus({ kind: 'error', message: err.message })
    } finally {
      setLoading(false)
    }
  }

  async function handleViewCert(propId, ownerName) {
    setCertBlob(null); setCertLoading(true)
    setCertTitle(`Certificate — ${propId} (${ownerName})`)
    setStatus({ kind: 'info', message: 'Fetching certificate…' })
    try {
      const url  = getESwathuCertUrl(propId)
      const res  = await fetch(url)
      const blob = await res.blob()
      setCertBlob(blob)
      setCertLoading(false)
      setStatus({ kind: 'success', message: 'Certificate loaded.' })
      setTimeout(() => certRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 100)
    } catch (err) {
      setCertLoading(false)
      setStatus({ kind: 'error', message: err.message })
    }
  }

  return (
    <div className="page">
      <div className="page-heading">
        <div className="page-badge">
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#7c4a1a', display: 'inline-block' }} />
          Panchayat Records
        </div>
        <h1 className="page-title">E-Swathu</h1>
        <p className="page-subtitle">
          Search E-Swathu property records for gram panchayat villages
        </p>
        <ul className="page-features">
          <li>Search by village across all panchayats</li>
          <li>View and download property certificate</li>
          <li>Optional search value to filter results</li>
        </ul>
      </div>

      <div>
        <div className="card" style={{ padding: 24 }}>
          <form onSubmit={handleSubmit}>
            <div className="field">
              <label>Village <span className="req">*</span></label>
              <Typeahead
                value={locationInput}
                onChange={setLocationInput}
                onSelect={handleLocSelect}
                onClear={() => { setSelectedLoc(null); setLocationInput(''); setProperties(null); setCertBlob(null) }}
                filterFn={filterLocations}
                placeholder="Search village name…"
              />
            </div>

            <div className="field">
              <label>Search Value <span style={{ fontWeight: 400, color: 'var(--text-faint)', fontSize: 12 }}>(optional)</span></label>
              <input
                type="text"
                value={searchVal}
                onChange={e => setSearchVal(e.target.value)}
                placeholder="Owner name, property ID, etc."
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
                : <><i className="ti ti-home-check" /> Search Properties</>
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
                No properties found for this village.
              </div>
            ) : (
              <div className="result-table-wrapper">
                <table className="result-table">
                  <thead>
                    <tr>
                      <th>#</th>
                      <th>Panchayat</th>
                      <th>Village</th>
                      <th>Property ID</th>
                      <th>Asset No</th>
                      <th>Owner</th>
                      <th>Type</th>
                      <th>Certificate</th>
                    </tr>
                  </thead>
                  <tbody>
                    {properties.map((p, i) => (
                      <tr key={i}>
                        <td>{i + 1}</td>
                        <td>{p.panchayat || '—'}</td>
                        <td>{p.village || '—'}</td>
                        <td style={{ fontWeight: 600 }}>{p.property_id || '—'}</td>
                        <td>{p.asset_number || '—'}</td>
                        <td>{p.owner_name || '—'}</td>
                        <td>{p.property_type || '—'}</td>
                        <td>
                          {p.has_draft ? (
                            <button
                              type="button"
                              className="table-action-btn"
                              onClick={() => handleViewCert(p.property_id, p.owner_name)}
                              disabled={certLoading}
                            >
                              View
                            </button>
                          ) : (
                            <span style={{ color: 'var(--text-faint)', fontSize: 12 }}>N/A</span>
                          )}
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
          <div ref={certRef}>
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

      <LoaderModal visible={loading} onCancel={() => {}} title="Searching E-Swathu properties…" />
    </div>
  )
}
