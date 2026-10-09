import { useEffect } from 'react'

const KAVERI_ITEMS = [
  { id: 'project',  label: 'EC by Project',   icon: 'ti-building-estate' },
  { id: 'ec',       label: 'Karnataka EC',     icon: 'ti-map-search' },
  { id: 'chain',    label: 'Ownership Chain',  icon: 'ti-git-branch' },
]

const BHOOMI_ITEMS = [
  { id: 'rtc',      label: 'RTC',      icon: 'ti-file-certificate' },
  { id: 'mutation', label: 'Mutation', icon: 'ti-pencil-check' },
  { id: 'akarband', label: 'Akarband', icon: 'ti-map-2' },
]

const OTHER_ITEMS = [
  { id: 'ekhata',  label: 'E-Khata',  icon: 'ti-building-community' },
  { id: 'bbmptax', label: 'Tax Receipt', icon: 'ti-receipt-tax' },
  { id: 'eswathu', label: 'E-Swathu', icon: 'ti-home-check' },
]

export default function DrawerMenu({ open, activeView, onNavigate, onClose }) {
  useEffect(() => {
    if (open) document.body.style.overflow = 'hidden'
    else document.body.style.overflow = ''
    return () => { document.body.style.overflow = '' }
  }, [open])

  function NavItem({ item }) {
    return (
      <button
        className={`sidebar-nav-item${activeView === item.id ? ' active' : ''}`}
        onClick={() => { onNavigate(item.id); onClose() }}
      >
        <i className={`ti ${item.icon}`} />
        <span>{item.label}</span>
      </button>
    )
  }

  return (
    <>
      <div className={`drawer-backdrop${open ? ' open' : ''}`} onClick={onClose} />
      <aside className={`sidebar drawer${open ? ' open' : ''}`} aria-hidden={!open}>
        <div className="sidebar-logo" style={{ paddingTop: 20 }}>
          <div className="sidebar-logo-img">
            <span className="sidebar-logo-name">TrueDocs</span>
          </div>
          <span className="sidebar-powered">
            powered by&nbsp;<img src="/TruEstate full gold.png" alt="TruEstate" className="sidebar-truestate" />
          </span>
        </div>

        <nav className="sidebar-nav">
          <div className="sidebar-section-title">Kaveri (EC)</div>
          {KAVERI_ITEMS.map(item => <NavItem key={item.id} item={item} />)}

          <div className="sidebar-section-title" style={{ marginTop: 8 }}>Bhoomi</div>
          {BHOOMI_ITEMS.map(item => <NavItem key={item.id} item={item} />)}

          <div className="sidebar-section-title" style={{ marginTop: 8 }}>BBMP / Panchayat</div>
          {OTHER_ITEMS.map(item => <NavItem key={item.id} item={item} />)}
        </nav>

        <div className="sidebar-status">
          <span className="sidebar-status-dot" />
          <span>Kaveri Online</span>
        </div>
      </aside>
    </>
  )
}
