import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/useAuth'
import {
  LayoutDashboard, FolderOpen, Building2, Calculator, Package,
  FileText, BarChart3, Upload, Eye, LogOut, HardHat,
  BookOpen, Ruler, TrendingUp, Receipt, X,
} from 'lucide-react'

const navItems = [
  { to: '/dashboard',      icon: LayoutDashboard, label: 'Dashboard',        group: 'main' },
  { to: '/projects',       icon: FolderOpen,      label: 'Projects',          group: 'main' },
  { to: '/buildings',      icon: Building2,       label: 'Buildings',         group: 'main' },
  { to: '/estimation',     icon: Calculator,      label: 'Estimation',        group: 'main' },
  { to: '/sor',            icon: BookOpen,        label: 'Item Master / SOR', group: 'civil' },
  { to: '/measurements',   icon: Ruler,           label: 'Measurement Book',  group: 'civil' },
  { to: '/boq',            icon: FileText,        label: 'BOQ',               group: 'civil' },
  { to: '/rate-analysis',  icon: TrendingUp,      label: 'Rate Analysis',     group: 'civil' },
  { to: '/billing',        icon: Receipt,         label: 'RA Billing',        group: 'civil' },
  { to: '/materials',      icon: Package,         label: 'Materials',         group: 'other' },
  { to: '/analytics',      icon: BarChart3,       label: 'Analytics',         group: 'other' },
  { to: '/dxf',            icon: Upload,          label: 'DXF Import',        group: 'other' },
  { to: '/drawing-takeoff',icon: Ruler,           label: 'Drawing Takeoff',   group: 'other' },
  { to: '/inspection',     icon: Eye,             label: 'AI Inspection',     group: 'other' },
]

const GROUP_LABELS: Record<string, string> = {
  main: '',
  civil: 'CIVIL ENGINEERING',
  other: 'OTHER',
}

interface SidebarProps {
  collapsed: boolean       // desktop collapsed state
  mobileOpen: boolean      // mobile drawer open state
  onMobileClose: () => void
}

export default function Sidebar({ collapsed, mobileOpen, onMobileClose }: SidebarProps) {
  const { user, logout } = useAuth()
  const groups = ['main', 'civil', 'other'] as const

  // On mobile: full-width drawer (transform-based show/hide)
  // On desktop: fixed sidebar, width controlled by collapsed prop
  return (
    <aside className={cn(
      // Base: fixed, full height, primary bg, transition
      'fixed inset-y-0 left-0 z-40 flex flex-col bg-[hsl(var(--primary))] text-white transition-transform duration-300',
      // Mobile: always w-72, shown/hidden via translate
      'w-72 lg:w-auto',
      // Mobile translate — off-screen when closed
      mobileOpen ? 'translate-x-0' : '-translate-x-full',
      // Desktop: override translate, width based on collapsed
      'lg:translate-x-0',
      collapsed ? 'lg:w-16' : 'lg:w-64',
    )}>
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 px-4 border-b border-white/10 shrink-0">
        <HardHat className="h-7 w-7 shrink-0 text-amber-400" />
        {/* Always show text on mobile drawer; on desktop hide when collapsed */}
        <div className={cn('lg:hidden')}>
          <p className="font-bold text-sm leading-tight">SmartBOQ Pro</p>
          <p className="text-xs text-white/60">Civil Engineering Suite</p>
        </div>
        <div className={cn('hidden', !collapsed && 'lg:block')}>
          <p className="font-bold text-sm leading-tight">SmartBOQ Pro</p>
          <p className="text-xs text-white/60">Civil Engineering Suite</p>
        </div>
        {/* Close button — mobile only */}
        <button
          onClick={onMobileClose}
          className="ml-auto lg:hidden p-1 rounded text-white/70 hover:text-white hover:bg-white/10"
          aria-label="Close menu"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        {groups.map(g => (
          <div key={g}>
            {/* Group label — hidden when desktop collapsed, always shown on mobile */}
            {GROUP_LABELS[g] && (
              <p className={cn(
                'text-xs font-semibold text-white/40 uppercase tracking-wider px-3 pt-4 pb-1',
                collapsed ? 'lg:hidden' : '',
              )}>
                {GROUP_LABELS[g]}
              </p>
            )}
            {navItems.filter(n => n.group === g).map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                onClick={onMobileClose}
                className={({ isActive }) => cn(
                  'flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-white/20 text-white'
                    : 'text-white/70 hover:bg-white/10 hover:text-white',
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {/* Always show label on mobile; desktop respects collapsed */}
                <span className={cn('lg:hidden')}>{label}</span>
                <span className={cn('hidden', !collapsed && 'lg:inline')}>{label}</span>
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* User + Logout */}
      <div className="border-t border-white/10 p-3 shrink-0">
        <NavLink
          to="/profile"
          onClick={onMobileClose}
          className={({ isActive }) => cn(
            'flex items-center gap-3 rounded-md px-3 py-2 mb-1 text-sm transition-colors',
            isActive ? 'bg-white/20 text-white' : 'text-white/70 hover:bg-white/10 hover:text-white',
          )}
        >
          <div className="h-7 w-7 rounded-full bg-white/20 flex items-center justify-center text-white text-xs font-bold shrink-0">
            {user?.full_name?.charAt(0).toUpperCase()}
          </div>
          <div className={cn('min-w-0 lg:hidden')}>
            <p className="text-sm font-medium truncate leading-tight">{user?.full_name}</p>
            <p className="text-xs text-white/50 capitalize leading-tight">{user?.role?.replace(/_/g, ' ')}</p>
          </div>
          <div className={cn('min-w-0 hidden', !collapsed && 'lg:block')}>
            <p className="text-sm font-medium truncate leading-tight">{user?.full_name}</p>
            <p className="text-xs text-white/50 capitalize leading-tight">{user?.role?.replace(/_/g, ' ')}</p>
          </div>
        </NavLink>

        <button
          onClick={() => { onMobileClose(); logout() }}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-white/70 hover:bg-white/10 hover:text-white transition-colors"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          <span className="lg:hidden">Logout</span>
          <span className={cn('hidden', !collapsed && 'lg:inline')}>Logout</span>
        </button>
      </div>
    </aside>
  )
}
