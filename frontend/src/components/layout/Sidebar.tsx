import { NavLink, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'
import {
  LayoutDashboard, FolderOpen, Building2, Calculator, Package,
  FileText, BarChart3, Upload, Eye, Settings, LogOut, HardHat, UserCircle,
} from 'lucide-react'

const navItems = [
  { to: '/dashboard',    icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/projects',     icon: FolderOpen,       label: 'Projects' },
  { to: '/buildings',    icon: Building2,         label: 'Buildings' },
  { to: '/estimation',   icon: Calculator,        label: 'Estimation' },
  { to: '/materials',    icon: Package,           label: 'Materials' },
  { to: '/boq',          icon: FileText,          label: 'BOQ' },
  { to: '/analytics',    icon: BarChart3,         label: 'Analytics' },
  { to: '/dxf',          icon: Upload,            label: 'DXF Import' },
  { to: '/inspection',   icon: Eye,               label: 'AI Inspection' },
]

const bottomItems = [
  { to: '/profile',      icon: UserCircle,        label: 'My Profile' },
]

interface SidebarProps { collapsed: boolean }

export default function Sidebar({ collapsed }: SidebarProps) {
  const { user, logout } = useAuth()
  const loc = useLocation()

  return (
    <aside className={cn(
      'fixed inset-y-0 left-0 z-40 flex flex-col bg-[hsl(var(--primary))] text-white transition-all duration-300',
      collapsed ? 'w-16' : 'w-64'
    )}>
      {/* Logo */}
      <div className="flex h-16 items-center gap-3 px-4 border-b border-white/10">
        <HardHat className="h-7 w-7 shrink-0 text-amber-400" />
        {!collapsed && (
          <div>
            <p className="font-bold text-sm leading-tight">SmartBOQ</p>
            <p className="text-xs text-white/60">Pro</p>
          </div>
        )}
      </div>

      {/* Nav */}
      <nav className="flex-1 overflow-y-auto py-4 space-y-1 px-2">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) => cn(
              'flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors',
              isActive
                ? 'bg-white/20 text-white'
                : 'text-white/70 hover:bg-white/10 hover:text-white'
            )}
          >
            <Icon className="h-5 w-5 shrink-0" />
            {!collapsed && <span>{label}</span>}
          </NavLink>
        ))}

        {user?.role === 'admin' && (
          <>
            <div className={cn('mt-4 mb-2 border-t border-white/10 pt-4', collapsed && 'mx-2')} />
            {bottomItems.map(({ to, icon: Icon, label }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) => cn(
                  'flex items-center gap-3 rounded-md px-3 py-2.5 text-sm font-medium transition-colors',
                  isActive ? 'bg-white/20 text-white' : 'text-white/70 hover:bg-white/10 hover:text-white'
                )}
              >
                <Icon className="h-5 w-5 shrink-0" />
                {!collapsed && <span>{label}</span>}
              </NavLink>
            ))}
          </>
        )}
      </nav>

      {/* User */}
      <div className="border-t border-white/10 p-3">
        <NavLink
          to="/profile"
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
              <p className="text-xs text-white/50 capitalize leading-tight">{user?.role?.replace(/_/g, ' ')}</p>
            </div>
          )}
        </NavLink>
        <button
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-white/70 hover:bg-white/10 hover:text-white transition-colors"
        >
          <LogOut className="h-4 w-4 shrink-0" />
          {!collapsed && <span>Logout</span>}
        </button>
      </div>
    </aside>
  )
}
