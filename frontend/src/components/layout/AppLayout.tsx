import { useState } from 'react'
import { Outlet, useLocation } from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import { cn } from '@/lib/utils'

const TITLES: Record<string, string> = {
  '/dashboard':  'Dashboard',
  '/projects':   'Projects',
  '/buildings':  'Building Information',
  '/estimation': 'Quantity Estimation',
  '/materials':  'Material Database',
  '/boq':        'Bill of Quantities',
  '/analytics':  'Analytics',
  '/dxf':        'DXF Import',
  '/inspection': 'AI Visual Inspection',
  '/settings':   'Settings',
  '/profile':    'My Profile',
}

export default function AppLayout() {
  const [collapsed, setCollapsed] = useState(false)
  const loc = useLocation()
  const base = '/' + loc.pathname.split('/')[1]
  const title = TITLES[base] ?? 'SmartBOQ Pro'

  return (
    <div className="min-h-screen bg-background">
      <Sidebar collapsed={collapsed} />
      <div className={cn('flex flex-col transition-all duration-300', collapsed ? 'ml-16' : 'ml-64')}>
        <Header onToggleSidebar={() => setCollapsed(c => !c)} title={title} />
        <main className="flex-1 p-6 overflow-auto">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
