import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line,
} from 'recharts'
import { FolderOpen, DollarSign, Package, TrendingUp } from 'lucide-react'
import api from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatCurrency, formatDate, capitalize, statusColor } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'

const COLORS = ['#1E3A5F', '#2E86AB', '#F0A500', '#10B981', '#EF4444', '#8B5CF6']

function KPICard({ icon: Icon, label, value, sub, color }: {
  icon: React.ElementType; label: string; value: string | number; sub?: string; color: string
}) {
  return (
    <Card>
      <CardContent className="p-4 sm:p-5 flex items-center gap-3 sm:gap-4">
        <div className={`h-10 w-10 sm:h-12 sm:w-12 rounded-xl flex items-center justify-center shrink-0 ${color}`}>
          <Icon className="h-5 w-5 sm:h-6 sm:w-6 text-white" />
        </div>
        <div className="min-w-0">
          <p className="text-xs sm:text-sm text-muted-foreground truncate">{label}</p>
          <p className="text-lg sm:text-2xl font-bold truncate">{value}</p>
          {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
        </div>
      </CardContent>
    </Card>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const isAdmin = user?.role === 'admin'
  const isPM    = user?.role === 'project_manager'
  const canSeeGlobalRecent = isAdmin  // only admin sees all recent projects

  const { data: dash } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get('/analytics/dashboard').then(r => r.data),
  })
  const { data: trends } = useQuery({
    queryKey: ['cost-trends'],
    queryFn: () => api.get('/analytics/cost-trends').then(r => r.data),
  })

  const kpis        = dash?.kpis ?? {}
  const statusData  = (dash?.charts?.status_distribution ?? []).filter((d: any) => d.count > 0)
  const typeData    = (dash?.charts?.building_type_distribution ?? []).filter((d: any) => d.count > 0)
  // recent_projects from dashboard API is already scoped by the backend to the current user's role
  const recentProjects = dash?.recent_projects ?? []

  return (
    <div className="space-y-5 sm:space-y-6">
      {/* Welcome */}
      <div>
        <h2 className="text-xl sm:text-2xl font-bold">
          Welcome back, {user?.full_name?.split(' ')[0]} 👋
        </h2>
        <p className="text-sm text-muted-foreground mt-1">
          {canSeeGlobalRecent
            ? 'System overview — all projects visible.'
            : 'Here\'s your project overview.'}
        </p>
      </div>

      {/* KPI Cards — 2 col on mobile, 4 on desktop */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        <KPICard icon={FolderOpen} label="Total Projects"  value={kpis.total_projects ?? 0}            color="bg-[hsl(var(--primary))]" />
        <KPICard icon={TrendingUp} label="Active Projects" value={kpis.active_projects ?? 0}           color="bg-green-600" />
        <KPICard icon={DollarSign} label="Total Est. Cost" value={formatCurrency(kpis.total_estimated_cost ?? 0)} color="bg-amber-500" />
        <KPICard icon={Package}    label="Materials"       value={kpis.total_materials ?? 0}           color="bg-[hsl(var(--secondary))]" />
      </div>

      {/* Charts — stack on mobile, side by side on lg */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        {/* Monthly cost trends */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-base sm:text-lg">Monthly Cost Trends</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={trends ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="month_label" tick={{ fontSize: 10 }} />
                <YAxis tickFormatter={v => `${(v / 1e6).toFixed(1)}M`} tick={{ fontSize: 10 }} width={45} />
                <Tooltip formatter={(v: number) => formatCurrency(v)} />
                <Line type="monotone" dataKey="total_cost" stroke="#1E3A5F" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Status pie */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base sm:text-lg">Project Status</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={statusData}
                  dataKey="count"
                  nameKey="status"
                  cx="50%"
                  cy="50%"
                  outerRadius={70}
                  label={({ status, count }) => count > 0 ? capitalize(status) : ''}
                  labelLine={false}
                >
                  {statusData.map((_: any, i: number) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip formatter={(v: number, name: string) => [v, capitalize(name)]} />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Building types + recent projects */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 sm:gap-6">
        {/* Building types */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base sm:text-lg">Building Types</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={typeData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fontSize: 10 }} />
                <YAxis
                  dataKey="type"
                  type="category"
                  tick={{ fontSize: 10 }}
                  width={75}
                  tickFormatter={capitalize}
                />
                <Tooltip />
                <Bar dataKey="count" fill="#2E86AB" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Recent Projects — scoped by role */}
        <Card className="lg:col-span-2">
          <CardHeader className="pb-2">
            <CardTitle className="text-base sm:text-lg">
              {canSeeGlobalRecent ? 'Recent Projects (All)' : 'My Recent Projects'}
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 sm:space-y-3">
              {recentProjects.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-8">
                  No projects yet. Create your first project!
                </p>
              )}
              {recentProjects.map((p: any) => (
                <div
                  key={p.id}
                  className="flex flex-col sm:flex-row sm:items-center sm:justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors gap-1 sm:gap-3"
                >
                  <div className="min-w-0">
                    <p className="font-medium text-sm truncate">{p.project_name}</p>
                    <p className="text-xs text-muted-foreground truncate">{p.client_name} · {p.project_code}</p>
                  </div>
                  <div className="flex items-center gap-2 sm:gap-3 shrink-0">
                    <span className="text-sm font-medium">{formatCurrency(p.total_estimated_cost ?? p.estimated_cost ?? 0)}</span>
                    <span className={`text-xs px-2 py-0.5 rounded-full ${statusColor(p.status)}`}>
                      {capitalize(p.status)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Footer branding */}
      <p className="text-xs text-muted-foreground text-center pb-2">
        SmartBOQ Pro · Built by Rahul Singh · © {new Date().getFullYear()}
      </p>
    </div>
  )
}
