import { useState, useEffect, useCallback, useRef } from 'react'
import { loadProjects, searchProject } from '../../utils/api.js'
import { createBlobUrl, downloadBlob } from '../../utils/pdf.js'

export default function useECByProject() {
  const [projects, setProjects] = useState([])
  const [inputValue, setInputValue] = useState('')
  const [selectedProject, setSelectedProject] = useState(null)
  const [searchBy, setSearchBy] = useState('party')
  const [searchValue, setSearchValue] = useState('')
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(false)
  const [blob, setBlob] = useState(null)
  const [filename, setFilename] = useState(null)
  const [blobUrl, setBlobUrl] = useState(null)
  const abortRef = useRef(null)

  useEffect(() => {
    loadProjects()
      .then(setProjects)
      .catch(() => setProjects([]))
  }, [])

  useEffect(() => {
    return () => {
      if (blobUrl) URL.revokeObjectURL(blobUrl)
    }
  }, [blobUrl])

  const projectItems = projects.map((p) => ({
    ...p,
    name: p.projectName,
    meta: p.villages?.length
      ? p.villages[0].villageName + (p.villages.length > 1 ? ` +${p.villages.length - 1} more` : '')
      : '',
  }))

  const handleSelect = useCallback((item) => {
    setSelectedProject(item)
    setInputValue(item.projectName)
    setStatus(null)
  }, [])

  const handleClear = useCallback(() => {
    setSelectedProject(null)
    setInputValue('')
  }, [])

  function clearResult() {
    if (blobUrl) URL.revokeObjectURL(blobUrl)
    setBlob(null)
    setFilename(null)
    setBlobUrl(null)
    setStatus(null)
  }

  async function submit() {
    if (!selectedProject) {
      setStatus({ kind: 'error', message: 'Please select a project from the dropdown.' })
      return
    }
    if (!searchValue.trim()) {
      setStatus({ kind: 'error', message: `Please enter a ${searchBy === 'party' ? 'party name' : 'flat number'}.` })
      return
    }

    clearResult()
    setLoading(true)
    setStatus({ kind: 'info', message: `Searching across ${selectedProject.villages?.length || 1} area(s)…` })

    try {
      const result = await searchProject({
        projectName: selectedProject.projectName,
        searchBy,
        searchValue: searchValue.trim(),
      })

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
    projects,
    projectItems,
    inputValue,
    setInputValue,
    selectedProject,
    handleSelect,
    handleClear,
    searchBy,
    setSearchBy,
    searchValue,
    setSearchValue,
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
