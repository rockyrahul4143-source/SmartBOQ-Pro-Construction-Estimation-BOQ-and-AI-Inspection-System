import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, LineChart, Line,
} from 'recharts'
import { FolderOpen, DollarSign, Package, FileText, TrendingUp, AlertTriangle } from 'lucide-react'
import api from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { formatCurrency, formatDate, capitalize, statusColor } from '@/lib/utils'
import { useAuth } from '@/contexts/AuthContext'

const COLORS = ['#1E3A5F', '#2E86AB', '#F0A500', '#10B981', '#EF4444', '#8B5CF6']

function KPICard({ icon: Icon, label, value, sub, color }: any) {
  return (
    <Card>
      <CardContent className="p-5 flex items-center gap-4">
        <div className={`h-12 w-12 rounded-xl flex items-center justify-center ${color}`}>
          <Icon className="h-6 w-6 text-white" />
        </div>
        <div>
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-bold">{value}</p>
          {sub && <p className="text-xs text-muted-foreground">{sub}</p>}
        </div>
      </CardContent>
    </Card>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()

  const { data: dash } = useQuery({
    queryKey: ['dashboard'],
    queryFn: () => api.get('/analytics/dashboard').then(r => r.data),
  })
  const { data: trends } = useQuery({
    queryKey: ['cost-trends'],
    queryFn: () => api.get('/analytics/cost-trends').then(r => r.data),
  })

  const kpis = dash?.kpis ?? {}
  const statusData = dash?.charts?.status_distribution ?? []
  const typeData   = dash?.charts?.building_type_distribution ?? []
  const recentProjects = dash?.recent_projects ?? []

  return (
    <div className="space-y-6">
      {/* Welcome */}
      <div>
        <h2 className="text-2xl font-bold">Welcome back, {user?.full_name?.split(' ')[0]} 👋</h2>
        <p className="text-muted-foreground">Here's your project overview for today.</p>
      </div>

      {/* KPI Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KPICard icon={FolderOpen}  label="Total Projects"   value={kpis.total_projects ?? 0}  color="bg-[hsl(var(--primary))]" />
        <KPICard icon={TrendingUp}  label="Active Projects"  value={kpis.active_projects ?? 0}  color="bg-green-600" />
        <KPICard icon={DollarSign}  label="Total Est. Cost"  value={formatCurrency(kpis.total_estimated_cost ?? 0)} color="bg-amber-500" />
        <KPICard icon={Package}     label="Materials"        value={kpis.total_materials ?? 0}  color="bg-[hsl(var(--secondary))]" />
      </div>

      {/* Charts row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Monthly cost trends */}
        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>Monthly Cost Trends</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={trends ?? []}>
                <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
                <XAxis dataKey="month_label" tick={{ fontSize: 11 }} />
                <YAxis tickFormatter={v => `${(v/1e6).toFixed(1)}M`} tick={{ fontSize: 11 }} />
                <Tooltip formatter={(v: any) => formatCurrency(v)} />
                <Line type="monotone" dataKey="total_cost" stroke="#1E3A5F" strokeWidth={2} dot={{ r: 4 }} />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Status distribution */}
        <Card>
          <CardHeader><CardTitle>Project Status</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={220}>
              <PieChart>
                <Pie data={statusData} dataKey="count" nameKey="status" cx="50%" cy="50%" outerRadius={70} label={({ status, count }) => count > 0 ? status : ''}>
                  {statusData.map((_: any, i: number) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      </div>

      {/* Building types + recent projects */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card>
          <CardHeader><CardTitle>Building Types</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={typeData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fontSize: 10 }} />
                <YAxis dataKey="type" type="category" tick={{ fontSize: 10 }} width={80} tickFormatter={capitalize} />
                <Tooltip />
                <Bar dataKey="count" fill="#2E86AB" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2">
          <CardHeader><CardTitle>Recent Projects</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-3">
              {recentProjects.length === 0 && (
                <p className="text-sm text-muted-foreground text-center py-8">No projects yet. Create your first project!</p>
              )}
              {recentProjects.map((p: any) => (
                <div key={p.id} className="flex items-center justify-between p-3 rounded-lg border hover:bg-muted/50 transition-colors">
                  <div>
                    <p className="font-medium text-sm">{p.project_name}</p>
                    <p className="text-xs text-muted-foreground">{p.client_name} · {p.project_code}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="text-sm font-medium">{formatCurrency(p.estimated_cost)}</span>
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
    </div>
  )
}
