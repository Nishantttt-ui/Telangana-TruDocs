const NAV_ITEMS = [
  { id: 'project', label: 'EC by Project', icon: 'ti-building-estate', description: 'Search across project areas' },
  { id: 'ec', label: 'Karnataka EC', icon: 'ti-map-search', description: 'Search by village' },
  { id: 'chain', label: 'Ownership Chain', icon: 'ti-git-branch', description: 'Trace property ownership' },
]

export default function Sidebar({ activeView, onNavigate }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-logo">
        <div className="sidebar-logo-img">
          <div className="sidebar-logo-monogram">TE</div>
          {/* <span className="sidebar-logo-name">ACN</span> */}
        </div>
        <span className="sidebar-powered">Powered by TruEstate</span>
      </div>

      <nav className="sidebar-nav" aria-label="Main navigation">
        <div className="sidebar-section-title">Karnataka</div>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`sidebar-nav-item${activeView === item.id ? ' active' : ''}`}
            onClick={() => onNavigate(item.id)}
            aria-current={activeView === item.id ? 'page' : undefined}
          >
            <i className={`ti ${item.icon}`} />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="sidebar-status">
        <span className="sidebar-status-dot" />
        <span>Kaveri Online</span>
      </div>
    </aside>
  )
}
