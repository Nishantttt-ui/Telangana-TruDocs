export default function MobileHeader({ onMenuOpen }) {
  return (
    <header className="mobile-header">
      <button className="hamburger-btn" onClick={onMenuOpen} aria-label="Open menu">
        <span />
        <span />
        <span />
      </button>
      <div className="mobile-header-logo">
        <div className="mobile-header-logo-row">
          <div className="mobile-header-monogram">TE</div>
          {/* <span className="mobile-header-name">ACN</span> */}
        </div>
        <span className="mobile-header-powered">Powered by TruEstate</span>
      </div>
      <div className="mobile-status-pill">
        <span className="mobile-status-dot" />
        Live
      </div>
    </header>
  )
}
