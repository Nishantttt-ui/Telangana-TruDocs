import Typeahead from '../../components/common/Typeahead.jsx'
import StatusMessage from '../../components/common/StatusMessage.jsx'
import PDFViewer from '../../components/common/PDFViewer.jsx'
import LoaderModal from '../../components/common/LoaderModal.jsx'
import DurationPicker from '../../components/search/DurationPicker.jsx'
import useKarnatakaEC from './useKarnatakaEC.js'

const QUICK_TYPES = [
  { value: 'party', label: 'Party Name' },
  { value: 'flat', label: 'Flat No' },
  { value: 'plot', label: 'Plot No' },
  { value: 'survey', label: 'Survey No' },
  { value: 'more', label: 'More…' },
]

export default function KarnatakaECView() {
  const {
    filterVillages,
    villageInput,
    setVillageInput,
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
  } = useKarnatakaEC()

  const isMore = !QUICK_TYPES.slice(0, 4).find((t) => t.value === searchBy)
  const dynamicLabel = searchBy === 'party' ? 'Party Name' : 'Property Number'
  const dynamicPlaceholder = searchBy === 'party' ? 'eg. SHARMA RAJESH KUMAR' : 'eg. 123'

  function handleSubmit(e) {
    e.preventDefault()
    submit()
  }

  return (
    <div className="page">
      <div className="page-heading">
        <div className="page-badge">
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: '#4ade80', display: 'inline-block' }} />
          Kaveri Online
        </div>
        <h1 className="page-title">Karnataka EC</h1>
        <p className="page-subtitle">Search Encumbrance Certificates by village, party name, or property number</p>
        <ul className="page-features">
          <li>Direct lookup via Kaveri Online</li>
          <li>Filter by party, flat, plot, or survey number</li>
          <li>Choose any date range from 2003 to today</li>
        </ul>
      </div>

      <div className="card" style={{ padding: '24px' }}>
        <form onSubmit={handleSubmit}>
          <div className="field">
            <label>Village <span className="req">*</span></label>
            <Typeahead
              items={[]}
              filterFn={filterVillages}
              value={villageInput}
              onChange={setVillageInput}
              onSelect={handleVillageSelect}
              onClear={handleVillageClear}
              placeholder="Search village name…"
            />
          </div>

          <div className="field">
            <label>Duration <span className="req">*</span></label>
            <DurationPicker
              value={duration}
              onChange={setDuration}
              customRange={customRange}
              onCustomRange={setCustomRange}
            />
          </div>

          <div className="field">
            <label>Search By</label>
            <div className="radio-group">
              {QUICK_TYPES.map((opt) => (
                <label
                  key={opt.value}
                  className={`radio-option${
                    opt.value === 'more'
                      ? isMore ? ' selected' : ''
                      : searchBy === opt.value ? ' selected' : ''
                  }`}
                >
                  <input
                    type="radio"
                    name="ec-searchby"
                    value={opt.value}
                    checked={opt.value === 'more' ? isMore : searchBy === opt.value}
                    onChange={() => {
                      if (opt.value !== 'more') { setSearchBy(opt.value); setInputValue('') }
                    }}
                    onClick={() => {
                      if (opt.value === 'more') {
                        const firstMore = propertyTypes.find((t) =>
                          !QUICK_TYPES.slice(0, 4).find((q) => q.value === String(t.propertytypeid))
                        )
                        if (firstMore) { setSearchBy(String(firstMore.propertytypeid)); setInputValue('') }
                      }
                    }}
                  />
                  {opt.label}
                </label>
              ))}
            </div>
            {isMore && propertyTypes.length > 0 && (
              <select
                className="more-options-select"
                style={{ marginTop: 8 }}
                value={searchBy}
                onChange={(e) => { setSearchBy(e.target.value); setInputValue('') }}
              >
                {propertyTypes
                  .filter((t) => !QUICK_TYPES.slice(0, 4).find((q) => q.value === String(t.propertytypeid)))
                  .map((t) => (
                    <option key={t.propertytypeid} value={String(t.propertytypeid)}>
                      {t.typeNameEnglish}
                    </option>
                  ))}
              </select>
            )}
          </div>

          <div className="field">
            <label>{dynamicLabel} <span className="req">*</span></label>
            <input
              type="text"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder={dynamicPlaceholder}
            />
          </div>

          {status && <div style={{ marginBottom: 12 }}><StatusMessage kind={status.kind} message={status.message} /></div>}

          <button type="submit" className="submit-btn" disabled={loading}>
            {loading
              ? <><i className="ti ti-loader" style={{ animation: 'spin 1s linear infinite' }} /> Searching Kaveri…</>
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

      <LoaderModal visible={loading} onCancel={cancelSearch} title="Searching Kaveri Online…" />
    </div>
  )
}
