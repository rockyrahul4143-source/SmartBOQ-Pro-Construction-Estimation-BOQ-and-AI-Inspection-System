import { NavLink, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import {
  LayoutDashboard, FolderOpen, Building2, Calculator, Package,
  FileText, BarChart3, Upload, Eye, Settings, LogOut, HardHat,
  UserCircle, BookOpen, Ruler, TrendingUp, Receipt,
} from 'lucide-react'

const navItems = [
  { to: '/dashboard',      icon: LayoutDashboard, label: 'Dashboard',        group: 'main' },
  { to: '/projects',       icon: FolderOpen,      label: 'Projects',          group: 'main' },
  { to: '/buildings',      icon: Building2,       label: 'Buildings',         group: 'main' },
  { to: '/estimation',     icon: Calculator,      label: 'Estimation',        group: 'main' },
  // ── Civil Engineering ──────────────────────────────────────────
  { to: '/sor',            icon: BookOpen,        label: 'Item Master / SOR', group: 'civil' },
  { to: '/measurements',   icon: Ruler,           label: 'Measurement Book',  group: 'civil' },
  { to: '/boq',            icon: FileText,        label: 'BOQ',               group: 'civil' },
  { to: '/rate-analysis',  icon: TrendingUp,      label: 'Rate Analysis',     group: 'civil' },
  { to: '/billing',        icon: Receipt,         label: 'RA Billing',        group: 'civil' },
  // ── Other ─────────────────────────────────────────────────────
  { to: '/materials',      icon: Package,         label: 'Materials',         group: 'other' },
  { to: '/analytics',      icon: BarChart3,       label: 'Analytics',         group: 'other' },
  { to: '/dxf',            icon: Upload,          label: 'DXF Import',        group: 'other' },
  { to: '/drawing-takeoff',icon: Ruler,            label: 'Drawing Takeoff',   group: 'other' },
  { to: '/inspection',     icon: Eye,             label: 'AI Inspection',     group: 'other' },
]

const GROUP_LABELS: Record<string,string> = { main:'', civil:'CIVIL ENGINEERING', other:'OTHER' }

interface SidebarProps { collapsed: boolean }

export default function Sidebar({ collapsed }: SidebarProps) {
  const { user, logout } = useAuth()

  const groups = ['main','civil','other'] as const
  const byGroup = (g: string) => navItems.filter(n => n.group === g)

  return (
    <aside className={cn(
      'fixed inset-y-0 left-0 z-40 flex flex-col bg-[hsl(var(--primary))] text-white transition-all duration-300',
      collapsed ? 'w-16' : 'w-64'
    )}>
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 px-4 border-b border-white/10 shrink-0">
        <HardHat className="h-7 w-7 shrink-0 text-amber-400" />
        {!collapsed && (
          <div>
            <p className="font-bold text-sm leading-tight">SmartBOQ</p>
            <p className="text-xs text-white/60">Civil Engineering Suite</p>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-3 px-2 space-y-0.5">
        {groups.map(g => (
          <div key={g}>
            {!collapsed && GROUP_LABELS[g] && (
              <p className="text-xs font-semibold text-white/40 uppercase tracking-wider px-3 pt-4 pb-1">{GROUP_LABELS[g]}</p>
            )}
            {byGroup(g).map(({ to, icon: Icon, label }) => (
              <NavLink key={to} to={to}
                className={({ isActive }) => cn(
                  'flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive ? 'bg-white/20 text-white' : 'text-white/70 hover:bg-white/10 hover:text-white'
                )}
              >
                <Icon className="h-4 w-4 shrink-0" />
                {!collapsed && <span>{label}</span>}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      {/* User + Logout */}
      <div className="border-t border-white/10 p-3 shrink-0">
        <NavLink to="/profile"
          className={({ isActive }) => cn(
            'flex items-center gap-3 rounded-md px-3 py-2 mb-1 text-sm transition-colors',
            isActive ? 'bg-white/20 text-white' : 'text-white/70 hover:bg-white/10 hover:text-white'
          )}
        >
          <div className="h-7 w-7 rounded-full bg-white/20 flex items-center justify-center text-white text-xs font-bold shrink-0">
            {user?.full_name?.charAt(0).toUpperCase()}
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <p className="text-sm font-medium truncate leading-tight">{user?.full_name}</p>
              <p className="text-xs text-white/50 capitalize leading-tight">{user?.role?.replace(/_/g,' ')}</p>
            </div>
          )}
        </NavLink>
        <button onClick={logout}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-white/70 hover:bg-white/10 hover:text-white transition-colors"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          {!collapsed && <span>Logout</span>}
        </button>
      </div>
    </aside>
  )
}
