import { useState, useEffect, useCallback, useRef } from 'react'
import { loadVillages, loadPropertyTypes, searchEC } from '../../utils/api.js'
import { createBlobUrl, downloadBlob } from '../../utils/pdf.js'

export default function useKarnatakaEC() {
  const [villages, setVillages] = useState([])
  const [propertyTypes, setPropertyTypes] = useState([])
  const [villageInput, setVillageInput] = useState('')
  const [selectedVillageCode, setSelectedVillageCode] = useState(null)
  const [searchBy, setSearchBy] = useState('party')
  const [inputValue, setInputValue] = useState('')
  const [duration, setDuration] = useState(null)
  const [customRange, setCustomRange] = useState(null)
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [blob, setBlob] = useState(null)
  const [filename, setFilename] = useState(null)
  const [blobUrl, setBlobUrl] = useState(null)
  const abortRef = useRef(null)

  useEffect(() => {
    loadVillages().then(setVillages).catch(() => {})
    loadPropertyTypes().then(setPropertyTypes).catch(() => {})
  }, [])

  useEffect(() => {
    return () => { if (blobUrl) URL.revokeObjectURL(blobUrl) }
  }, [blobUrl])

  const villageItems = villages.map((v) => ({
    ...v,
    name: v.villageName,
    meta: `${v.hobliName}, ${v.talukName}, ${v.districtName}`,
  }))

  const filterVillages = useCallback((q) => {
    if (!q) return []
    const ql = q.toLowerCase()
    const t1 = [], t2 = [], t3 = []
    for (const v of villages) {
      const vn = v.villageName.toLowerCase()
      if (vn.startsWith(ql)) t1.push({ ...v, name: v.villageName, meta: `${v.hobliName}, ${v.talukName}, ${v.districtName}` })
      else if (vn.includes(ql)) t2.push({ ...v, name: v.villageName, meta: `${v.hobliName}, ${v.talukName}, ${v.districtName}` })
      else if (v.hobliName?.toLowerCase().includes(ql) || v.talukName?.toLowerCase().includes(ql) || v.districtName?.toLowerCase().includes(ql))
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

  function clearResult() {
    if (blobUrl) URL.revokeObjectURL(blobUrl)
    setBlob(null)
    setFilename(null)
    setBlobUrl(null)
    setStatus(null)
  }

  async function submit() {
    if (!selectedVillageCode) {
      setStatus({ kind: 'error', message: 'Please select a village from the dropdown.' })
      return
    }
    if (!inputValue.trim()) {
      setStatus({ kind: 'error', message: `Please enter a ${searchBy === 'party' ? 'party name' : 'property number'}.` })
      return
    }
    if (!duration) {
      setStatus({ kind: 'error', message: 'Please select a duration.' })
      return
    }
    if (duration === 'custom' && !customRange) {
      setStatus({ kind: 'error', message: 'Please pick a custom date range.' })
      return
    }

    clearResult()
    setLoading(true)
    setStatus({ kind: 'info', message: 'Searching Kaveri Online…' })

    const controller = new AbortController()
    abortRef.current = controller

    try {
      const result = await searchEC(
        { villageCode: selectedVillageCode, searchBy, inputValue: inputValue.trim(), duration, customRange },
        { signal: controller.signal }
      )

      if (result.type === 'pdf') {
        const url = createBlobUrl(result.blob)
        setBlob(result.blob)
        setFilename(result.filename)
        setBlobUrl(url)
        setStatus({ kind: 'success', message: `Found! ${result.filename}` })
      } else if (result.type === 'empty') {
        setStatus({ kind: 'warning', message: 'No EC records found for this search.' })
      } else {
        setStatus({ kind: 'info', message: result.message })
      }
    } catch (err) {
      if (err.name === 'AbortError') return
      const kind = err.code === 503 ? 'warning' : 'error'
      setStatus({ kind, message: err.message })
    } finally {
      setLoading(false)
    }
  }

  function cancelSearch() {
    abortRef.current?.abort()
    setLoading(false)
    setStatus(null)
  }

  function download() {
    if (blob && filename) downloadBlob(blob, filename)
  }

  return {
    villageItems,
    filterVillages,
    villageInput,
    setVillageInput,
    selectedVillageCode,
    handleVillageSelect,
    handleVillageClear,
    propertyTypes,
    searchBy,
    setSearchBy,
    inputValue,
    setInputValue,
    duration,
    setDuration,
    customRange,
    setCustomRange,
    status,
    loading,
    blob,
    filename,
    blobUrl,
    submit,
    cancelSearch,
    download,
  }
}
