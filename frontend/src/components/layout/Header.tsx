import { Menu, Sun, Moon, Bell } from 'lucide-react'
import { useTheme } from '@/contexts/ThemeContext'
import { useAuth } from '@/hooks/useAuth'
import { Button } from '@/components/ui/button'

interface HeaderProps {
  onToggleSidebar: () => void
  title: string
}

export default function Header({ onToggleSidebar, title }: HeaderProps) {
  const { theme, toggle } = useTheme()
  const { user } = useAuth()

  return (
    <header className="h-16 border-b bg-card flex items-center justify-between px-4 shadow-sm">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={onToggleSidebar}>
          <Menu className="h-5 w-5" />
        </Button>
        <h1 className="text-lg font-semibold text-foreground">{title}</h1>
      </div>
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="icon" onClick={toggle}>
          {theme === 'dark' ? <Sun className="h-5 w-5" /> : <Moon className="h-5 w-5" />}
        </Button>
        <Button variant="ghost" size="icon">
          <Bell className="h-5 w-5" />
        </Button>
        <div className="ml-2 flex items-center gap-2">
          <div className="h-8 w-8 rounded-full bg-primary flex items-center justify-center text-primary-foreground text-sm font-bold">
            {user?.full_name?.charAt(0).toUpperCase()}
          </div>
        </div>
      </div>
    </header>
  )
}
