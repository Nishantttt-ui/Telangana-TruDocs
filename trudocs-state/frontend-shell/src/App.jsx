import { useState, useEffect } from 'react'
import AppHeader from './components/layout/AppHeader.jsx'
import DrawerMenu from './components/layout/DrawerMenu.jsx'
import BottomSheet from './components/common/BottomSheet.jsx'
import ECByProjectView from './views/ECByProject/ECByProjectView.jsx'
import KarnatakaECView from './views/KarnatakaEC/KarnatakaECView.jsx'
import OwnershipChainView from './views/OwnershipChain/OwnershipChainView.jsx'
import RTCView from './views/RTC/RTCView.jsx'
import MutationView from './views/Mutation/MutationView.jsx'
import AkarbandView from './views/Akarband/AkarbandView.jsx'
import EKhataView from './views/EKhata/EKhataView.jsx'
import BBMPReceiptView from './views/BBMPReceipt/BBMPReceiptView.jsx'
import ESwathuView from './views/ESwathu/ESwathuView.jsx'

const SECTION_IDS = {
  project:  'section-project',
  ec:       'section-ec',
  chain:    'section-chain',
  rtc:      'section-rtc',
  mutation: 'section-mutation',
  akarband: 'section-akarband',
  ekhata:   'section-ekhata',
  bbmptax:  'section-bbmptax',
  eswathu:  'section-eswathu',
}

const SHEET_TITLES = {
  ec:       'Karnataka EC (Kaveri)',
  chain:    'Ownership Chain',
  rtc:      'RTC (Land Records)',
  mutation: 'Mutation',
  akarband: 'Akarband',
  ekhata:   'E-Khata (BBMP)',
  bbmptax:  'Tax Receipt (BBMP)',
  eswathu:  'E-Swathu',
}

const EXPLORE_CARDS = [
  { id: 'ec',       iconClass: 'ti ti-map-pin',            name: 'Karnataka EC',    desc: 'Search by village or party name' },
  { id: 'chain',    iconClass: 'ti ti-git-merge',          name: 'Ownership Chain', desc: 'Trace full property ownership history' },
  { id: 'rtc',      iconClass: 'ti ti-file-certificate',   name: 'RTC',             desc: 'Rights, Tenancy & Crops records' },
  { id: 'mutation', iconClass: 'ti ti-pencil-check',       name: 'Mutation',        desc: 'Bhoomi mutation certificate' },
  { id: 'akarband', iconClass: 'ti ti-map-2',              name: 'Akarband',        desc: 'Land measurement records' },
  { id: 'ekhata',   iconClass: 'ti ti-building-community', name: 'E-Khata',         desc: 'BBMP property records' },
  { id: 'bbmptax',  iconClass: 'ti ti-receipt-tax',        name: 'Tax Receipt',     desc: 'BBMP property tax receipts' },
  { id: 'eswathu',  iconClass: 'ti ti-home-check',         name: 'E-Swathu',        desc: 'Gram panchayat property records' },
]

function scrollToSection(id) {
  const el = document.getElementById(SECTION_IDS[id])
  if (!el) return
  const top = el.getBoundingClientRect().top + window.scrollY - 68
  window.scrollTo({ top, behavior: 'smooth' })
}

export default function App() {
  const [activeView, setActiveView] = useState('project')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [sheetView, setSheetView]   = useState(null)
  const [isMobile, setIsMobile]     = useState(window.innerWidth < 768)

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)')
    const handler = (e) => setIsMobile(e.matches)
    mq.addEventListener('change', handler)
    return () => mq.removeEventListener('change', handler)
  }, [])

  // Update active nav tab based on scroll position (desktop only)
  useEffect(() => {
    if (isMobile) return
    const onScroll = () => {
      const offset = 80
      for (const [id, sectionId] of Object.entries(SECTION_IDS).reverse()) {
        const el = document.getElementById(sectionId)
        if (el && el.getBoundingClientRect().top <= offset) {
          setActiveView(id)
          return
        }
      }
      setActiveView('project')
    }
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [isMobile])

  function handleNavigate(id) {
    setActiveView(id)
    if (!isMobile) scrollToSection(id)
  }

  function renderSheetContent() {
    switch (sheetView) {
      case 'ec':       return <KarnatakaECView />
      case 'chain':    return <OwnershipChainView />
      case 'rtc':      return <RTCView />
      case 'mutation': return <MutationView />
      case 'akarband': return <AkarbandView />
      case 'ekhata':   return <EKhataView />
      case 'bbmptax':  return <BBMPReceiptView />
      case 'eswathu':  return <ESwathuView />
      default:         return null
    }
  }

  return (
    <div className="app-shell">
      <AppHeader
        activeView={activeView}
        onNavigate={handleNavigate}
        onMenuOpen={() => setDrawerOpen(true)}
      />

      <DrawerMenu
        open={drawerOpen}
        activeView={activeView}
        onNavigate={(id) => { setActiveView(id); setDrawerOpen(false) }}
        onClose={() => setDrawerOpen(false)}
      />

      <div className="main-content">
        {isMobile ? (
          <>
            <ECByProjectView />
            <div className="explore-section" style={{ padding: '0 16px 80px' }}>
              {/* City strip decoration */}
              <div className="mobile-city-strip" aria-hidden="true">
                <svg viewBox="0 0 390 72" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
                  <defs>
                    <pattern id="mb-w" width="10" height="13" patternUnits="userSpaceOnUse">
                      <rect x="1.5" y="2"  width="3"   height="4"   fill="#0a3d2e" fillOpacity="0.25" />
                      <rect x="5.5" y="2"  width="3"   height="4"   fill="#0a3d2e" fillOpacity="0.25" />
                      <rect x="1.5" y="8"  width="3"   height="3.5" fill="#0a3d2e" fillOpacity="0.25" />
                      <rect x="5.5" y="8"  width="3"   height="3.5" fill="#0a3d2e" fillOpacity="0.25" />
                    </pattern>
                  </defs>
                  {[
                    { x: 0,   w: 28, h: 32 }, { x: 31,  w: 22, h: 46 }, { x: 56,  w: 28, h: 38 },
                    { x: 87,  w: 24, h: 56 }, { x: 114, w: 20, h: 42 }, { x: 137, w: 32, h: 64 },
                    { x: 172, w: 22, h: 50 }, { x: 197, w: 26, h: 58 }, { x: 226, w: 20, h: 44 },
                    { x: 249, w: 30, h: 62 }, { x: 282, w: 24, h: 52 }, { x: 309, w: 28, h: 42 },
                    { x: 340, w: 22, h: 36 }, { x: 365, w: 25, h: 48 },
                  ].map((b, i) => {
                    const y = 72 - b.h
                    return (
                      <g key={i}>
                        <rect x={b.x + 1} y={y} width={b.w - 2} height={b.h}
                          fill="rgba(10,61,46,0.055)" stroke="rgba(10,61,46,0.13)" strokeWidth="1" />
                        <rect x={b.x + 3} y={y + 6} width={b.w - 6} height={b.h - 10}
                          fill="url(#mb-w)" />
                      </g>
                    )
                  })}
                </svg>
              </div>
              <div className="explore-title">Explore More</div>
              <div className="explore-cards">
                {EXPLORE_CARDS.map((card) => (
                  <button
                    key={card.id}
                    className="explore-card"
                    onClick={() => setSheetView(card.id)}
                    type="button"
                  >
                    <div className="explore-card-icon"><i className={card.iconClass} /></div>
                    <div className="explore-card-name">{card.name}</div>
                    <div className="explore-card-desc">{card.desc}</div>
                  </button>
                ))}
              </div>
            </div>

            <BottomSheet
              open={!!sheetView}
              onClose={() => setSheetView(null)}
              title={sheetView ? SHEET_TITLES[sheetView] : ''}
            >
              {renderSheetContent()}
            </BottomSheet>
          </>
        ) : (
          <div className="single-page">
            <div className="lp-hero">
              {/* Background concentric circles */}
              <div className="lp-hero-circles" aria-hidden="true">
                <div className="lp-hero-circle lp-hero-circle-1" />
                <div className="lp-hero-circle lp-hero-circle-2" />
                <div className="lp-hero-circle lp-hero-circle-3" />
              </div>

              {/* Floating badges — wide screens only */}
              <div className="lp-hero-badge lp-hero-badge-l" aria-hidden="true">
                <div className="lp-hero-badge-icon"><i className="ti ti-building-community" /></div>
                <div className="lp-hero-badge-text">
                  <strong>Kaveri Verified</strong>
                  <span>Live government data</span>
                </div>
              </div>
              <div className="lp-hero-badge lp-hero-badge-r" aria-hidden="true">
                <div className="lp-hero-badge-icon"><i className="ti ti-map-pin" /></div>
                <div className="lp-hero-badge-text">
                  <strong>2,928 Villages</strong>
                  <span>Complete coverage</span>
                </div>
              </div>

              {/* Main content */}
              <div className="lp-hero-inner">
                <h1 className="lp-hero-title">
                  Bangalore&rsquo;s only <em>property records</em> engine.
                </h1>
                <p className="lp-hero-sub">
                  Search Encumbrance Certificates, trace ownership chains, fetch RTC &amp; Mutation records — live from Kaveri &amp; Bhoomi.
                </p>
                <div className="lp-hero-stats">
                  <div className="lp-stat">
                    <em className="lp-stat-num">3,278+</em>
                    <span className="lp-stat-label">Projects Indexed</span>
                  </div>
                  <div className="lp-stat">
                    <em className="lp-stat-num">2,928</em>
                    <span className="lp-stat-label">Villages Covered</span>
                  </div>
                  <div className="lp-stat">
                    <em className="lp-stat-num">2003</em>
                    <span className="lp-stat-label">Records From</span>
                  </div>
                </div>
              </div>

              {/* City skyline illustration */}
              <div className="lp-hero-city" aria-hidden="true">
                <svg viewBox="0 0 1440 200" preserveAspectRatio="none" xmlns="http://www.w3.org/2000/svg">
                  <defs>
                    <pattern id="lp-w" width="12" height="16" patternUnits="userSpaceOnUse">
                      <rect x="1.5" y="2"  width="3.5" height="5"   fill="#0a3d2e" fillOpacity="0.28" />
                      <rect x="7"   y="2"  width="3.5" height="5"   fill="#0a3d2e" fillOpacity="0.28" />
                      <rect x="1.5" y="10" width="3.5" height="4.5" fill="#0a3d2e" fillOpacity="0.28" />
                      <rect x="7"   y="10" width="3.5" height="4.5" fill="#0a3d2e" fillOpacity="0.28" />
                    </pattern>
                  </defs>
                  {[
                    { x: 0,    w: 62,  h: 82  }, { x: 66,   w: 50,  h: 122 }, { x: 120,  w: 64,  h: 102 },
                    { x: 188,  w: 56,  h: 150 }, { x: 248,  w: 46,  h: 110 }, { x: 298,  w: 74,  h: 174 },
                    { x: 376,  w: 52,  h: 134 }, { x: 432,  w: 60,  h: 150 }, { x: 496,  w: 47,  h: 114 },
                    { x: 547,  w: 70,  h: 160 }, { x: 621,  w: 55,  h: 140 }, { x: 680,  w: 76,  h: 188 },
                    { x: 760,  w: 51,  h: 147 }, { x: 815,  w: 61,  h: 164 }, { x: 880,  w: 49,  h: 127 },
                    { x: 933,  w: 72,  h: 178 }, { x: 1009, w: 57,  h: 144 }, { x: 1070, w: 63,  h: 160 },
                    { x: 1137, w: 49,  h: 122 }, { x: 1190, w: 70,  h: 168 }, { x: 1264, w: 56,  h: 140 },
                    { x: 1324, w: 49,  h: 110 }, { x: 1377, w: 63,  h: 124 },
                  ].map((b, i) => {
                    const y = 200 - b.h
                    return (
                      <g key={i}>
                        <rect x={b.x + 1} y={y} width={b.w - 2} height={b.h}
                          fill="rgba(10,61,46,0.055)" stroke="rgba(10,61,46,0.13)" strokeWidth="1" />
                        <rect x={b.x + 5} y={y + 10} width={b.w - 10} height={b.h - 18}
                          fill="url(#lp-w)" />
                      </g>
                    )
                  })}
                </svg>
              </div>
            </div>

            {/* ── Kaveri tools ── */}
            <section id="section-project" className="tool-section">
              <ECByProjectView />
            </section>
            <div className="tool-sep" />
            <section id="section-ec" className="tool-section">
              <KarnatakaECView />
            </section>
            <div className="tool-sep" />
            <section id="section-chain" className="tool-section">
              <OwnershipChainView />
            </section>

            {/* ── Bhoomi tools ── */}
            <div className="tool-sep" />
            <section id="section-rtc" className="tool-section">
              <RTCView />
            </section>
            <div className="tool-sep" />
            <section id="section-mutation" className="tool-section">
              <MutationView />
            </section>
            <div className="tool-sep" />
            <section id="section-akarband" className="tool-section">
              <AkarbandView />
            </section>

            {/* ── BBMP / Panchayat tools ── */}
            <div className="tool-sep" />
            <section id="section-ekhata" className="tool-section">
              <EKhataView />
            </section>
            <div className="tool-sep" />
            <section id="section-bbmptax" className="tool-section">
              <BBMPReceiptView />
            </section>
            <div className="tool-sep" />
            <section id="section-eswathu" className="tool-section">
              <ESwathuView />
            </section>
          </div>
        )}
      </div>
    </div>
  )
}
