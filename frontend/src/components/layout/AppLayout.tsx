import { useState, useEffect } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'

const TITLES: Record<string, string> = {
  '/dashboard':      'Dashboard',
  '/projects':       'Projects',
  '/buildings':      'Building Information',
  '/estimation':     'Quantity Estimation',
  '/materials':      'Material Database',
  '/boq':            'Bill of Quantities',
  '/analytics':      'Analytics',
  '/dxf':            'DXF Import',
  '/inspection':     'AI Visual Inspection',
  '/sor':            'Item Master / SOR',
  '/measurements':   'Measurement Book',
  '/rate-analysis':  'Rate Analysis',
  '/billing':        'RA Billing',
  '/drawing-takeoff':'Drawing Takeoff',
  '/settings':       'Settings',
  '/profile':        'My Profile',
}

export default function AppLayout() {
  const loc = useLocation()
  const base = '/' + loc.pathname.split('/')[1]
  const title = TITLES[base] ?? 'SmartBOQ Pro'

  // On mobile: drawer closed by default; on desktop: sidebar always open
  const [mobileOpen, setMobileOpen] = useState(false)
  const [desktopCollapsed, setDesktopCollapsed] = useState(false)

  // Close mobile drawer on route change
  useEffect(() => {
    setMobileOpen(false)
  }, [loc.pathname])

  // Close mobile drawer on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileOpen(false)
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [])

  return (
    <div className="min-h-screen bg-background">
      {/* Mobile overlay backdrop */}
      {mobileOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/50 lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-hidden="true"
        />
      )}

      {/* Sidebar — drawer on mobile, fixed on desktop */}
      <Sidebar
        collapsed={desktopCollapsed}
        mobileOpen={mobileOpen}
        onMobileClose={() => setMobileOpen(false)}
      />

      {/* Main content — no left margin on mobile (drawer), pushed right on desktop */}
      <div className={[
        'flex flex-col min-h-screen transition-all duration-300',
        desktopCollapsed ? 'lg:ml-16' : 'lg:ml-64',
      ].join(' ')}>
        <Header
          onToggleSidebar={() => {
            // On mobile: open drawer; on desktop: collapse sidebar
            if (window.innerWidth < 1024) {
              setMobileOpen(o => !o)
            } else {
              setDesktopCollapsed(c => !c)
            }
          }}
          title={title}
        />
        <main className="flex-1 p-4 sm:p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
