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

function ResultBox({ error, result }) {
  if (error) return <div className="result error">{error}</div>
  if (result) return <pre className="result">{JSON.stringify(result, null, 2)}</pre>
  return null
}

function MutationCard() {
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
    <section className="card">
      <h2>GHMC Mutation Status</h2>
      <p className="hint">Enter your Assessment / PTIN number.</p>
      <form onSubmit={submit}>
        <input
          placeholder="Assessment Number"
          value={assessmentNumber}
          onChange={(e) => setAssessmentNumber(e.target.value)}
          required
        />
        <button type="submit" disabled={loading}>{loading ? 'Checking…' : 'Check Status'}</button>
      </form>
      <ResultBox error={error} result={result} />
    </section>
  )
}

function PropertyTaxCard() {
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
    <section className="card">
      <h2>GHMC Property Tax</h2>
      <p className="hint">Select your Circle and enter your PTIN number.</p>
      <form onSubmit={submit}>
        <select value={circle} onChange={(e) => setCircle(e.target.value)} required>
          <option value="">Select Circle</option>
          {circles.map((c) => (
            <option key={c.value} value={c.value}>{c.label}</option>
          ))}
        </select>
        <input placeholder="PTIN Number" value={ptin} onChange={(e) => setPtin(e.target.value)} required />
        <button type="submit" disabled={loading}>{loading ? 'Checking…' : 'Check Tax Status'}</button>
      </form>
      <ResultBox error={error} result={result} />
    </section>
  )
}

function AdangalCard() {
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
    <section className="card">
      <h2>Adangal Extract (Pahani)</h2>
      <p className="hint">
        Select District → Division → Mandal → Village, then enter your Survey Number.
      </p>
      <p className="warning">
        Note: the location dropdowns below are fully live and working. Final
        search submission to the government portal is still being verified —
        you may see an error here even for a valid survey number.
      </p>
      <form onSubmit={submit}>
        <select value={districtId} onChange={(e) => onDistrict(e.target.value)} required>
          <option value="">Select District</option>
          {districts.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
        </select>
        <select value={divisionId} onChange={(e) => onDivision(e.target.value)} disabled={!districtId} required>
          <option value="">Select Division</option>
          {divisions.map((d) => <option key={d.value} value={d.value}>{d.label}</option>)}
        </select>
        <select value={mandalId} onChange={(e) => onMandal(e.target.value)} disabled={!divisionId} required>
          <option value="">Select Mandal</option>
          {mandals.map((m) => <option key={m.value} value={m.value}>{m.label}</option>)}
        </select>
        <select value={villageId} onChange={(e) => setVillageId(e.target.value)} disabled={!mandalId} required>
          <option value="">Select Village</option>
          {villages.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
        </select>
        <input placeholder="Survey Number" value={surveyNo} onChange={(e) => setSurveyNo(e.target.value)} required />
        <button type="submit" disabled={loading}>{loading ? 'Searching…' : 'Get Adangal'}</button>
      </form>
      <ResultBox error={error} result={result} />
    </section>
  )
}

export default function App() {
  return (
    <div className="app">
      <header>
        <h1>Telangana TruDocs</h1>
        <p>Real-estate document search for Telangana</p>
      </header>
      <main>
        <MutationCard />
        <PropertyTaxCard />
        <AdangalCard />
      </main>
    </div>
  )
}
