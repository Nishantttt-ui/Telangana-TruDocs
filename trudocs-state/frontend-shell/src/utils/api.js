const SEARCH_TIMEOUT_MS = 150_000

function iso(date) {
  return date.toISOString().slice(0, 10)
}

export function rangeForDuration(duration, customRange) {
  const today = new Date()
  today.setHours(23, 59, 59, 999)
  const from = new Date(today)

  if (duration === 'custom' && customRange) {
    return customRange
  }

  const years = parseFloat(duration)
  from.setFullYear(from.getFullYear() - years)
  from.setHours(0, 0, 0, 0)
  return { from, to: today }
}

async function fetchWithTimeout(url, options = {}) {
  const { signal: userSignal, ...restOptions } = options
  const controller = new AbortController()
  const id = setTimeout(() => controller.abort(), SEARCH_TIMEOUT_MS)
  // Forward the caller's abort signal so cancelSearch() actually stops the fetch
  if (userSignal) {
    if (userSignal.aborted) { clearTimeout(id); throw new DOMException('Aborted', 'AbortError') }
    userSignal.addEventListener('abort', () => controller.abort(), { once: true })
  }
  try {
    const res = await fetch(url, { ...restOptions, signal: controller.signal })
    return res
  } finally {
    clearTimeout(id)
  }
}

// ── Error normalization ──────────────────────────────────────────────────────
// Map any backend error to a friendly, user-facing message. NEVER expose raw HTTP
// status codes or internal jargon. Keep the genuinely useful messages (no-records,
// rate-limit); everything else collapses to one clean line.
function friendlyMessage(status, detail) {
  if (status === 404) return detail || 'No records found for your search.'
  if (status === 429) return detail || 'Too many searches right now. Please wait a minute and try again.'
  if (status >= 500) return 'The records service is temporarily busy. Please try again shortly.'
  if (status === 401 || status === 403) return 'Please try again in a moment.'
  return 'Something went wrong. Please try again.'
}

// Build (don't throw) a friendly Error. `code` carries the status for callers that
// branch on it; `detail` keeps raw backend text for logging only (never rendered).
function makeFriendlyError(status, detail = '') {
  const err = new Error(friendlyMessage(status, detail))
  err.code = status
  err.detail = detail
  return err
}

// Read the response body (best-effort) and throw a friendly Error. Use at every
// terminal non-2xx site where the body hasn't already been consumed.
async function throwFriendly(res) {
  let detail = ''
  try {
    const d = await res.json()
    detail = d?.detail || d?.message || d?.error || ''
    if (Array.isArray(detail)) detail = detail.map((e) => e?.msg || '').join('; ')
  } catch { /* non-JSON body */ }
  throw makeFriendlyError(res.status, detail)
}

export async function loadVillages() {
  const res = await fetch('/api/villages')
  if (!res.ok) await throwFriendly(res)
  const data = await res.json()
  return data.villages || data
}

export async function loadProjects() {
  const res = await fetch('/api/projects')
  if (!res.ok) await throwFriendly(res)
  const data = await res.json()
  return data.projects || []
}

export async function loadPropertyTypes() {
  const res = await fetch('/PropertyType.json')
  if (!res.ok) await throwFriendly(res)
  return res.json()
}

export async function searchEC({ villageCode, searchBy, inputValue, duration, customRange }, { signal, onRetry } = {}) {
  const r = rangeForDuration(duration, customRange)

  let endpoint, payload
  if (searchBy === 'party') {
    endpoint = '/api/search'
    payload = {
      villageCode,
      firstName: inputValue,
      middleName: '',
      lastName: '',
      fromDate: iso(r.from),
      toDate: iso(r.to),
    }
  } else {
    endpoint = '/api/search-property'
    payload = {
      villageCode,
      propertyTypeId: searchBy,
      propertyNumber: inputValue,
      fromDate: iso(r.from),
      toDate: iso(r.to),
      isAgricultural: false,
    }
  }

  let captchaRetries = 0
  let sessionRetries = 0
  const MAX_CAPTCHA = 5
  const MAX_SESSION = 2

  while (true) {
    if (signal?.aborted) throw new DOMException('Aborted', 'AbortError')

    const res = await fetchWithTimeout(endpoint, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      signal,
    })

    const contentType = (res.headers.get('Content-Type') || '').toLowerCase()

    if (res.status === 422) {
      captchaRetries++
      if (captchaRetries <= MAX_CAPTCHA) {
        onRetry?.('captcha', captchaRetries)
        await sleep(1500)
        continue
      }
      throw new Error('Could not solve captcha after several attempts. Please try again.')
    }

    if (res.status === 401) {
      sessionRetries++
      if (sessionRetries <= MAX_SESSION) {
        onRetry?.('session', sessionRetries)
        await sleep(10000)
        continue
      }
      throw new Error('Session unavailable. Please try again in a moment.')
    }

    if (!res.ok) await throwFriendly(res)

    if (contentType.includes('application/pdf')) {
      const blob = await res.blob()
      const cd = res.headers.get('Content-Disposition') || ''
      const fnMatch = cd.match(/filename[^;=\n]*=(?:(['"])([^'"]*)\1|([^;\n]*))/i)
      const filename = fnMatch ? (fnMatch[2] || fnMatch[3] || 'EC.pdf').trim() : 'EC.pdf'
      return { type: 'pdf', blob, filename }
    }

    const json = await res.json()
    if (Array.isArray(json) && json.length === 0) {
      return { type: 'empty' }
    }
    const msg = json.message || json.detail || 'No records found for this search.'
    return { type: 'message', message: msg }
  }
}

export async function searchProject({ projectName, searchBy, searchValue }, { signal } = {}) {
  const res = await fetchWithTimeout('/api/search-project', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      projectName,
      searchBy,
      searchValue,
      fromDate: '2003-01-01',
      toDate: new Date().toISOString().slice(0, 10),
    }),
  })

  if (!res.ok) await throwFriendly(res)

  const contentType = (res.headers.get('Content-Type') || '').toLowerCase()
  if (contentType.includes('application/pdf')) {
    const blob = await res.blob()
    const cd = res.headers.get('Content-Disposition') || ''
    const fnMatch = cd.match(/filename[^;=\n]*=(?:(['"])([^'"]*)\1|([^;\n]*))/i)
    const filename = fnMatch ? (fnMatch[2] || fnMatch[3] || 'EC_Project.pdf').trim() : 'EC_Project.pdf'
    return { type: 'pdf', blob, filename }
  }

  const json = await res.json()
  if (Array.isArray(json) && json.length === 0) return { type: 'empty' }
  const msg = json.message || json.detail || 'No records found.'
  return { type: 'message', message: msg }
}

export async function searchChain({ villageCode, partyName, maxHops, filters }, { signal } = {}) {
  const res = await fetchWithTimeout('/api/title-chain', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ villageCode, partyName, maxHops, filters }),
    signal,
  })

  if (!res.ok) await throwFriendly(res)

  return res.json()
}

function sleep(ms) {
  return new Promise((r) => setTimeout(r, ms))
}

// ── RTC (Bhoomi Land Records) ────────────────────────────────────────────────

export async function loadRTCLocations() {
  const res = await fetch('/api/bhoomi/villages-all')
  if (!res.ok) await throwFriendly(res)
  return res.json()
}

export async function loadRTCCombinations(loc) {
  const p = new URLSearchParams({
    village_code:  loc.village_code,
    district_name: loc.district,
    taluk_name:    loc.taluk,
    hobli_name:    loc.hobli,
    district_code: loc.district_code || '',
    taluk_code:    loc.taluk_code    || '',
    hobli_code:    loc.hobli_code    || '',
  })
  const res = await fetch(`/api/bhoomi/combinations?${p}`)
  if (!res.ok) await throwFriendly(res)
  return res.json()
}

export async function fetchRTCRecord(payload, { signal } = {}) {
  const res = await fetchWithTimeout('/api/fetch-rtc', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
    signal,
  })
  if (!res.ok) await throwFriendly(res)
  return res.json()
}

// Server-side render (Playwright) — used on mobile where window.print() to PDF
// isn't a reliable one-tap flow.
export async function downloadRTCPdf({ html, filename }) {
  const res = await fetch('/api/rtc/download-pdf', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ html, filename }),
  })
  if (!res.ok) await throwFriendly(res)
  return res.blob()
}

// ── Mutation ─────────────────────────────────────────────────────────────────

export async function loadMutationLocations() {
  const res = await fetch('/api/mutation/villages')
  if (!res.ok) await throwFriendly(res)
  return res.json()
}

export async function loadMutationSurveys(villageName) {
  const res = await fetch(`/api/mutation/surveys?village=${encodeURIComponent(villageName)}`)
  if (!res.ok) await throwFriendly(res)
  return res.json()
}

export async function startMutationFetch(payload) {
  const res = await fetch('/api/mutation/fetch-single', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  })
  const data = await res.json()
  if (!res.ok) throw makeFriendlyError(res.status, data?.detail || data?.error || '')
  return data
}

export async function getMutationJobStatus(jobId) {
  const res = await fetch(`/api/mutation/jobs/${jobId}/status`)
  if (!res.ok) await throwFriendly(res)
  return res.json()
}

export async function getMutationCertificate(jobId) {
  const res = await fetch(`/api/mutation/jobs/${jobId}/certificate`)
  if (!res.ok) await throwFriendly(res)
  return res.text()
}

export function getMutationPdfUrl(jobId) {
  return `/api/mutation/jobs/${jobId}/download-pdf`
}

export async function downloadMutationPdf(jobId) {
  const res = await fetch(getMutationPdfUrl(jobId))
  if (!res.ok) await throwFriendly(res)
  return res.blob()
}

// ── Akarband ─────────────────────────────────────────────────────────────────

export async function loadAkarbandLocations() {
  const res = await fetch('/api/akarband/villages-all')
  if (!res.ok) await throwFriendly(res)
  return res.json()
}

export async function loadAkarbandSurveys({ distId, tlkId, hblId, vlgId }) {
  const res = await fetch(`/api/akarband/surveys/${distId}/${tlkId}/${hblId}/${vlgId}`)
  if (!res.ok) await throwFriendly(res)
  return res.json()
}

export async function fetchAkarbandRecord(payload) {
  const res = await fetchWithTimeout('/api/akarband/fetch', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  })
  if (res.status === 503) await throwFriendly(res)
  const ct = res.headers.get('content-type') || ''
  if (ct.includes('pdf')) {
    const blob = await res.blob()
    return { type: 'pdf_blob', blob }
  }
  const data = await res.json()
  if (!res.ok) throw makeFriendlyError(res.status, data?.detail || '')
  return { type: 'json', data }
}

// ── E-Khata (BBMP) ───────────────────────────────────────────────────────────

export async function loadEKhataZones() {
  const res = await fetch('/api/ekhata/zones')
  if (!res.ok) await throwFriendly(res)
  return res.json()
}

export async function loadEKhataWards(zoneId) {
  const res = await fetch(`/api/ekhata/wards?zone_id=${zoneId}`)
  if (!res.ok) await throwFriendly(res)
  return res.json()
}

export async function loadEKhataAllWards() {
  const res = await fetch('/api/ekhata/all-wards')
  if (!res.ok) await throwFriendly(res)
  return res.json()
}

export async function searchEKhata(payload) {
  const res = await fetch('/api/ekhata/search', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  })
  const data = await res.json()
  if (!res.ok) throw makeFriendlyError(res.status, data?.detail || '')
  return data
}

export async function getEKhataJobStatus(jobId) {
  const res = await fetch(`/api/ekhata/jobs/${jobId}/status`)
  if (!res.ok) await throwFriendly(res)
  return res.json()
}

export async function startEKhataDownload(payload) {
  const res = await fetch('/api/ekhata/download', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  })
  const data = await res.json()
  if (!res.ok) throw makeFriendlyError(res.status, data?.detail || '')
  return data
}

export async function getEKhataPdfBlob(jobId) {
  const res = await fetch(`/api/ekhata/jobs/${jobId}/download-pdf`)
  if (!res.ok) await throwFriendly(res)
  return res.blob()
}

// ── E-Swathu ─────────────────────────────────────────────────────────────────

export async function loadESwathuLocations() {
  const res = await fetch('/api/eswathu/villages-all')
  if (!res.ok) await throwFriendly(res)
  return res.json()
}

export async function searchESwathu(payload) {
  const res = await fetch('/api/eswathu/search', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify(payload),
  })
  const data = await res.json()
  if (!res.ok) throw makeFriendlyError(res.status, data?.detail || '')
  return data
}

export function getESwathuCertUrl(propertyId) {
  return `/api/eswathu/certificate/${encodeURIComponent(propertyId)}`
}

// ── BBMP Tax Receipt ─────────────────────────────────────────────────────────
// The backend's own messages here (wrong captcha, number not found, ...) are
// actionable for the user, so unlike the other services they're shown as-is.

async function throwBBMP(res) {
  let detail = ''
  try { detail = (await res.json())?.detail || '' } catch { /* non-JSON body */ }
  const err = new Error(typeof detail === 'string' && detail ? detail : 'Something went wrong. Please try again.')
  err.code = res.status
  throw err
}

export async function startBBMPReceipt(applicationNo) {
  const res = await fetch('/api/bbmp/captcha', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ application_no: applicationNo }),
  })
  if (!res.ok) await throwBBMP(res)
  return res.json()
}

export async function downloadBBMPReceipt({ sessionId, year, captcha }) {
  const res = await fetch('/api/bbmp/receipt', {
    method:  'POST',
    headers: { 'Content-Type': 'application/json' },
    body:    JSON.stringify({ session_id: sessionId, assessment_year: year, captcha }),
  })
  if (!res.ok) await throwBBMP(res)
  const m = /filename="?([^";]+)"?/.exec(res.headers.get('Content-Disposition') || '')
  return { blob: await res.blob(), filename: m ? m[1] : 'BBMP_Tax_Receipt.pdf' }
}
