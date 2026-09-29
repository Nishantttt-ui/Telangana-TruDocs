import { useEffect, useState } from 'react'
import './App.css'

function useApi() {
  async function post(path, body) {
    const res = await fetch(path, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || 'Something went wrong.')
    return data
  }
  async function get(path) {
    const res = await fetch(path)
    const data = await res.json().catch(() => ({}))
    if (!res.ok) throw new Error(data.detail || 'Something went wrong.')
    return data
  }
  return { post, get }
}

// A handful of field names we've confirmed live (GHMC's ASP.NET label IDs
// are cryptic, e.g. "grd_SearchResult_lblowner_0") — give these a proper
// human label; fall back to a generic prettifier for anything unmapped.
const KNOWN_FIELD_LABELS = {
  ptinno: 'PTIN Number',
  owner: 'Owner Name',
  door: 'Door Number',
  assessmentnum: 'Assessment Number',
}

function fieldLabel(key) {
  const stripped = key
    .replace(/^(grd_SearchResult_|ContentPlaceHolder1_)/i, '')
    .replace(/^lbl/i, '')
    .replace(/_\d+$/, '')
  const known = KNOWN_FIELD_LABELS[stripped.toLowerCase()]
  if (known) return known
  const spaced = stripped.replace(/([a-z])([A-Z])/g, '$1 $2').replace(/[_-]+/g, ' ').trim()
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : key
}

function ResultBox({ error, result }) {
  if (error) return <div className="result error">{error}</div>
  if (!result) return null

  const fields = result.raw_fields && Object.entries(result.raw_fields)
  const tables = result.raw_tables_html
  const notFoundMessage = result.not_found_messages?.[0]

  return (
    <div className="result success">
      {result.found ? (
        <p className="result-status found">✓ Record found</p>
      ) : (
        <p className="result-status not-found">{notFoundMessage || 'No record found.'}</p>
      )}

      {result.found && fields && fields.length > 0 && (
        <dl className="field-list">
          {fields.map(([key, value]) => (
            <div className="field-row" key={key}>
              <dt>{fieldLabel(key)}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}

      {result.found && tables && tables.length > 0 && (
        <div className="portal-table-wrapper">
          {tables.map((html, i) => (
            <div key={i} dangerouslySetInnerHTML={{ __html: html }} />
          ))}
        </div>
      )}
    </div>
  )
}

function Field({ label, required, children }) {
  return (
    <div className="field">
      <label>{label}{required && <span className="req">*</span>}</label>
      {children}
    </div>
  )
}

function MutationForm() {
  const { post } = useApi()
  const [assessmentNumber, setAssessmentNumber] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      setResult(await post('/api/ghmc/mutation', { assessment_number: assessmentNumber }))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <Field label="Assessment Number" required>
        <input
          placeholder="e.g. 1010133899"
          value={assessmentNumber}
          onChange={(e) => setAssessmentNumber(e.target.value)}
          required
        />
      </Field>
      <button type="submit" disabled={loading}>{loading ? 'Checking…' : 'Check Status'}</button>
      <ResultBox error={error} result={result} />
    </form>
  )
}

function PropertyTaxForm() {
  const { post, get } = useApi()
  const [circles, setCircles] = useState([])
  const [circle, setCircle] = useState('')
  const [ptin, setPtin] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    get('/api/ghmc/circles').then(setCircles).catch(() => {})
  }, [])

  async function submit(e) {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      setResult(await post('/api/ghmc/property-tax', { circle, ptin }))
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <Field label="Circle" required>
        <select value={circle} onChange={(e) => setCircle(e.target.value)} required>
          <option value="">Select Circle</option>
          {circles.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
      </Field>
      <Field label="PTIN Number" required>
        <input placeholder="e.g. 1010133899" value={ptin} onChange={(e) => setPtin(e.target.value)} required />
      </Field>
      <button type="submit" disabled={loading}>{loading ? 'Checking…' : 'Check Tax Status'}</button>
      <ResultBox error={error} result={result} />
    </form>
  )
}

function AdangalForm() {
  const { post, get } = useApi()
  const [districts, setDistricts] = useState([])
  const [divisions, setDivisions] = useState([])
  const [mandals, setMandals] = useState([])
  const [villages, setVillages] = useState([])
  const [districtId, setDistrictId] = useState('')
  const [divisionId, setDivisionId] = useState('')
  const [mandalId, setMandalId] = useState('')
  const [villageId, setVillageId] = useState('')
  const [surveyNo, setSurveyNo] = useState('')
  const [result, setResult] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    get('/api/adangal/districts').then(setDistricts).catch(() => {})
  }, [])

  async function onDistrict(id) {
    setDistrictId(id)
    setDivisions([]); setMandals([]); setVillages([])
    setDivisionId(''); setMandalId(''); setVillageId('')
    if (id) setDivisions(await get(`/api/adangal/divisions/${id}`))
  }

  async function onDivision(id) {
    setDivisionId(id)
    setMandals([]); setVillages([])
    setMandalId(''); setVillageId('')
    if (id) setMandals(await get(`/api/adangal/mandals/${districtId}/${id}`))
  }

  async function onMandal(id) {
    setMandalId(id)
    setVillages([])
    setVillageId('')
    if (id) setVillages(await get(`/api/adangal/villages/${districtId}/${id}`))
  }

  async function submit(e) {
    e.preventDefault()
    setError('')
    setResult(null)
    setLoading(true)
    try {
      setResult(
        await post('/api/adangal/search', {
          district_id: districtId,
          division_id: divisionId,
          mandal_id: mandalId,
          village_id: villageId,
          survey_or_khata_value: surveyNo,
          option: 'surveyNo',
        })
      )
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <form onSubmit={submit}>
      <Field label="District" required>
        <select value={districtId} onChange={(e) => onDistrict(e.target.value)} required>
          <option value="">Select District</option>
          {districts.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
        </select>
      </Field>
      <Field label="Division" required>
        <select value={divisionId} onChange={(e) => onDivision(e.target.value)} disabled={!districtId} required>
          <option value="">Select Division</option>
          {divisions.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
        </select>
      </Field>
      <Field label="Mandal" required>
        <select value={mandalId} onChange={(e) => onMandal(e.target.value)} disabled={!divisionId} required>
          <option value="">Select Mandal</option>
          {mandals.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
      </Field>
      <Field label="Village" required>
        <select value={villageId} onChange={(e) => setVillageId(e.target.value)} disabled={!mandalId} required>
          <option value="">Select Village</option>
          {villages.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
        </select>
      </Field>
      <Field label="Survey Number" required>
        <input placeholder="e.g. 123" value={surveyNo} onChange={(e) => setSurveyNo(e.target.value)} required />
      </Field>
      <button type="submit" disabled={loading}>{loading ? 'Searching…' : 'Get Adangal'}</button>
      <ResultBox error={error} result={result} />
    </form>
  )
}

const DOCUMENT_TYPES = [
  {
    id: 'ghmc-mutation',
    icon: 'ti ti-home-2',
    navLabel: 'GHMC Mutation',
    tag: 'Municipality',
    heading: 'GHMC Mutation Status',
    description: 'Check the latest ownership mutation status for a Hyderabad property by assessment number.',
    Form: MutationForm,
  },
  {
    id: 'ghmc-property-tax',
    icon: 'ti ti-receipt',
    navLabel: 'GHMC Property Tax',
    tag: 'Municipality',
    heading: 'GHMC Property Tax',
    description: 'Search property tax records by PTIN, owner name, or door number, within a circle.',
    Form: PropertyTaxForm,
  },
  {
    id: 'adangal',
    icon: 'ti ti-map-2',
    navLabel: 'Adangal (Pahani)',
    tag: 'Revenue dept',
    heading: 'Adangal Extract (Pahani)',
    description: 'Land ownership, cultivation, and usage record for agricultural land, by village and survey number.',
    Form: AdangalForm,
  },
]

function Skyline() {
  const buildings = [40, 60, 30, 75, 45, 90, 55, 35, 70, 50, 65, 38, 80, 42]
  return (
    <svg className="skyline" viewBox="0 0 700 90" preserveAspectRatio="none" fill="none">
      {buildings.map((h, i) => (
        <rect key={i} x={i * 50 + 5} y={90 - h} width="36" height={h} fill="currentColor" opacity="0.5" />
      ))}
    </svg>
  )
}

export default function App() {
  const [activeId, setActiveId] = useState(DOCUMENT_TYPES[0].id)

  useEffect(() => {
    const sections = DOCUMENT_TYPES.map((d) => document.getElementById(d.id)).filter(Boolean)
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
        if (visible) setActiveId(visible.target.id)
      },
      { rootMargin: '-35% 0px -50% 0px', threshold: [0, 0.25, 0.5, 0.75, 1] }
    )
    sections.forEach((s) => observer.observe(s))
    return () => observer.disconnect()
  }, [])

  function scrollToSection(id) {
    document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  return (
    <div className="app">
      <nav className="navbar">
        <div className="brand"><i className="ti ti-building-skyscraper" /> TruDocs Telangana</div>
        <div className="nav-tabs">
          {DOCUMENT_TYPES.map((d) => (
            <button
              key={d.id}
              className={`nav-tab${d.id === activeId ? ' active' : ''}`}
              onClick={() => scrollToSection(d.id)}
            >
              <i className={d.icon} /> {d.navLabel}
            </button>
          ))}
        </div>
      </nav>

      <div className="hero">
        <div className="hero-badge left">
          <div className="icon"><i className="ti ti-shield-check" /></div>
          <div>
            <div className="title">Govt. Verified</div>
            <div className="subtitle">Live government data</div>
          </div>
        </div>
        <div className="hero-badge right">
          <div className="icon"><i className="ti ti-map-pin" /></div>
          <div>
            <div className="title">33 Districts</div>
            <div className="subtitle">Statewide coverage</div>
          </div>
        </div>

        <h1>Telangana's own <em>property records</em> engine.</h1>
        <p className="tagline">
          Search property tax, mutation, and land records — verified live from GHMC and CCLA, Telangana.
        </p>

        <div className="stat-bar">
          <div className="stat">
            <span className="num">3</span>
            <span className="label">Live Document Types</span>
          </div>
          <div className="stat">
            <span className="num">33</span>
            <span className="label">Districts Covered</span>
          </div>
          <div className="stat">
            <span className="num">12,777</span>
            <span className="label">Villages Statewide</span>
          </div>
        </div>

        <Skyline />
      </div>

      {DOCUMENT_TYPES.map((d, i) => (
        <div className="search-section" id={d.id} key={d.id}>
          <div className="search-intro">
            <span className="index">{String(i + 1).padStart(2, '0')}</span>
            <span className="pill">{d.tag}</span>
            <h2>{d.heading}</h2>
            <p>{d.description}</p>
          </div>
          <div className="form-card">
            <d.Form />
          </div>
        </div>
      ))}
    </div>
  )
}
