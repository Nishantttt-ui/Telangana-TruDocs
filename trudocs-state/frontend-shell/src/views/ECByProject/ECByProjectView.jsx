import Typeahead from '../../components/common/Typeahead.jsx'
import StatusMessage from '../../components/common/StatusMessage.jsx'
import PDFViewer from '../../components/common/PDFViewer.jsx'
import LoaderModal from '../../components/common/LoaderModal.jsx'
import useECByProject from './useECByProject.js'

const PROJ_NAMES = [
  'Prestige Ferns Residency',
  'Aratt Cityscapes',
  'Goyal Orchid Whitefield',
  'Santorini @ Sobha City',
  'Puravankara Purva Parkridge',
]

export default function ECByProjectView() {
  const {
    projectItems,
    inputValue,
    setInputValue,
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
  } = useECByProject()

  function handleSubmit(e) {
    e.preventDefault()
    submit()
  }

  const dynamicLabel = searchBy === 'party' ? 'Party Name' : 'Flat No'
  const dynamicPlaceholder = searchBy === 'party' ? 'eg. SHARMA RAJESH KUMAR' : 'eg. A-402'

  return (
    <div className="page">
      <div className="page-heading">
        <div className="page-badge">
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#f59e0b', display: 'inline-block' }} />
          Primary Search
        </div>
        <h1 className="page-title">EC by Project</h1>
        <p className="page-subtitle">Search Encumbrance Certificates across all villages in a project at once</p>
        <ul className="page-features">
          <li>Covers every village in a project simultaneously</li>
          <li>Search by party name or flat number</li>
          <li>Download EC as PDF instantly</li>
        </ul>
      </div>

      <div className="card" style={{ padding: '24px' }}>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Project Name <span className="req">*</span></label>
            <Typeahead
              items={projectItems}
              value={inputValue}
              onChange={setInputValue}
              onSelect={handleSelect}
              onClear={handleClear}
              placeholder={PROJ_NAMES[0] + '…'}
              maxResults={15}
            />
          </div>

          <div className="field">
            <label>Search By</label>
            <div className="radio-group">
              {[{ value: 'party', label: 'Party Name' }, { value: 'flat', label: 'Flat No' }].map((opt) => (
                <label
                  key={opt.value}
                  className={`radio-option${searchBy === opt.value ? ' selected' : ''}`}
                >
                  <input
                    type="radio"
                    name="proj-searchby"
                    value={opt.value}
                    checked={searchBy === opt.value}
                    onChange={() => { setSearchBy(opt.value); setSearchValue('') }}
                  />
                  {opt.label}
                </label>
              ))}
            </div>
          </div>

          <div className="field">
            <label>{dynamicLabel} <span className="req">*</span></label>
            <input
              type="text"
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              placeholder={dynamicPlaceholder}
            />
          </div>

          {status && <div style={{ marginBottom: 12 }}><StatusMessage kind={status.kind} message={status.message} /></div>}

          <button type="submit" className="submit-btn" disabled={loading}>
            {loading
              ? <><i className="ti ti-loader" style={{ animation: 'spin 1s linear infinite' }} /> Searching…</>
              : <><i className="ti ti-search" /> Search EC Records</>
            }
          </button>
        </form>

        {blob && (
          <div className="result-actions" style={{ marginTop: 16 }}>
            <button className="download-btn" onClick={download}>
              <i className="ti ti-download" /> Download PDF
            </button>
            {filename && <span className="result-meta">{filename}</span>}
          </div>
        )}
      </div>

      <PDFViewer blob={blob} filename={filename} />

      <LoaderModal
        visible={loading}
        onCancel={cancelSearch}
        title="Searching across all project areas…"
      />
    </div>
  )
}
