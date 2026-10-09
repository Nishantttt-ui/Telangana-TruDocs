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

const ALL_NAV_ITEMS = [...KAVERI_ITEMS, ...BHOOMI_ITEMS, ...OTHER_ITEMS]

export default function AppHeader({ activeView, onNavigate, onMenuOpen }) {
  return (
    <header className="app-nav">
      <div className="app-nav-brand">
        <div className="app-nav-brand-text">
          <span className="app-nav-tagline">
            <img src="/TruEstate full gold.png" alt="TruEstate" height={32} />
          </span>
        </div>
      </div>

      <nav className="app-nav-tabs" aria-label="Main navigation">
        {KAVERI_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`app-nav-tab${activeView === item.id ? ' active' : ''}`}
            onClick={() => onNavigate(item.id)}
            aria-current={activeView === item.id ? 'page' : undefined}
          >
            <i className={`ti ${item.icon}`} />
            <span>{item.label}</span>
          </button>
        ))}

        <div className="app-nav-sep" aria-hidden="true" />

        {BHOOMI_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`app-nav-tab app-nav-tab-sm${activeView === item.id ? ' active' : ''}`}
            onClick={() => onNavigate(item.id)}
            aria-current={activeView === item.id ? 'page' : undefined}
          >
            <i className={`ti ${item.icon}`} />
            <span>{item.label}</span>
          </button>
        ))}

        <div className="app-nav-sep" aria-hidden="true" />

        {OTHER_ITEMS.map((item) => (
          <button
            key={item.id}
            className={`app-nav-tab app-nav-tab-sm${activeView === item.id ? ' active' : ''}`}
            onClick={() => onNavigate(item.id)}
            aria-current={activeView === item.id ? 'page' : undefined}
          >
            <i className={`ti ${item.icon}`} />
            <span>{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="app-nav-end">
        <button
          className="app-nav-hamburger"
          onClick={onMenuOpen}
          aria-label="Open menu"
        >
          <span />
          <span />
          <span />
        </button>
      </div>
    </header>
  )
}
