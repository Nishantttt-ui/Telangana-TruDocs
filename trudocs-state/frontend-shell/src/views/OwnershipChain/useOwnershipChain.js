import { useState, useEffect, useCallback, useRef } from 'react'
import { loadVillages, searchChain } from '../../utils/api.js'

export const FILTER_OPTIONS = [
  { value: 'flat', label: 'Flat No' },
  { value: 'villa', label: 'Villa No' },
  { value: 'plot', label: 'Plot No' },
  { value: 'door', label: 'Door No' },
  { value: 'block', label: 'Block No' },
  { value: 'survey', label: 'Survey No' },
  { value: 'project', label: 'Project Name' },
]

export const MAX_FILTERS = 2

export default function useOwnershipChain() {
  const [villages, setVillages] = useState([])
  const [villageInput, setVillageInput] = useState('')
  const [selectedVillageCode, setSelectedVillageCode] = useState(null)
  const [partyName, setPartyName] = useState('')
  const [filters, setFilters] = useState([])
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [chainData, setChainData] = useState(null)
  const abortRef       = useRef(null)
  const userCancelRef  = useRef(false)

  useEffect(() => {
    loadVillages().then(setVillages).catch(() => {})
  }, [])

  const filterVillages = useCallback((q) => {
    if (!q) return []
    const ql = q.toLowerCase()
    const t1 = [], t2 = [], t3 = []
    for (const v of villages) {
      const vn = v.villageName.toLowerCase()
      if (vn.startsWith(ql)) t1.push({ ...v, name: v.villageName, meta: `${v.hobliName}, ${v.talukName}, ${v.districtName}` })
      else if (vn.includes(ql)) t2.push({ ...v, name: v.villageName, meta: `${v.hobliName}, ${v.talukName}, ${v.districtName}` })
      else if (v.hobliName?.toLowerCase().includes(ql) || v.talukName?.toLowerCase().includes(ql))
        t3.push({ ...v, name: v.villageName, meta: `${v.hobliName}, ${v.talukName}, ${v.districtName}` })
      if (t1.length + t2.length + t3.length >= 200) break
    }
    return [...t1, ...t2, ...t3].slice(0, 15)
  }, [villages])

  const handleVillageSelect = useCallback((item) => {
    setSelectedVillageCode(item.villageCode)
    setVillageInput(`${item.villageName}, ${item.hobliName}, ${item.talukName}`)
    setStatus(null)
  }, [])

  const handleVillageClear = useCallback(() => {
    setSelectedVillageCode(null)
    setVillageInput('')
  }, [])

  function addFilter() {
    if (filters.length >= MAX_FILTERS) return
    const usedTypes = filters.map((f) => f.filterType)
    const available = FILTER_OPTIONS.find((o) => !usedTypes.includes(o.value))
    if (!available) return
    setFilters([...filters, { filterType: available.value, value: '' }])
  }

  function removeFilter(idx) {
    setFilters(filters.filter((_, i) => i !== idx))
  }

  function updateFilter(idx, key, val) {
    setFilters(filters.map((f, i) => i === idx ? { ...f, [key]: val } : f))
  }

  async function submit() {
    if (!selectedVillageCode) {
      setStatus({ kind: 'error', message: 'Please select a village.' })
      return
    }
    if (!partyName.trim()) {
      setStatus({ kind: 'error', message: 'Please enter a party name.' })
      return
    }

    setChainData(null)
    setLoading(true)
    setStatus({ kind: 'info', message: 'Tracing ownership chain…' })

    userCancelRef.current = false
    const controller = new AbortController()
    abortRef.current = controller

    try {
      const data = await searchChain(
        { villageCode: selectedVillageCode, partyName: partyName.trim(), filters: filters.filter((f) => f.value.trim()) },
        { signal: controller.signal }
      )

      setChainData(data)

      if (data.status === 'kaveri_error') {
        setStatus({ kind: 'error', message: 'Kaveri portal is temporarily unreachable. Please try again in a few minutes.' })
      } else if (data.status === 'too_many_properties') {
        setStatus({ kind: 'warning', message: `Found ${data.propertyCount} properties — please add a filter to narrow down.` })
      } else {
        const nodeCount = data.status === 'dual_chain'
          ? (data.chains || []).reduce((s, p) => s + (p.chain?.length || 0), 0)
          : (data.chain?.length || 0)
        if (nodeCount === 0) {
          setStatus({ kind: 'warning', message: 'No transactions found for this name in this village.' })
        } else {
          setStatus({ kind: 'success', message: 'Chain traced successfully.' })
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') {
        if (!userCancelRef.current) {
          setStatus({ kind: 'error', message: 'Connection timed out. Please try again.' })
        }
        return
      }
      if (err.code === 503) {
        setStatus({ kind: 'error', message: 'Session is initialising. Please try again in 2 minutes.' })
      } else {
        setStatus({ kind: 'error', message: 'Something went wrong. Please try again.' })
      }
    } finally {
      setLoading(false)
    }
  }

  function cancelSearch() {
    userCancelRef.current = true
    abortRef.current?.abort()
    setLoading(false)
    setStatus(null)
  }

  return {
    filterVillages,
    villageInput,
    setVillageInput,
    handleVillageSelect,
    handleVillageClear,
    partyName,
    setPartyName,
    filters,
    addFilter,
    removeFilter,
    updateFilter,
    status,
    loading,
    chainData,
    submit,
    cancelSearch,
  }
}
