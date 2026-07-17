import { useQuery } from '@tanstack/react-query'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, Legend, LineChart, Line, AreaChart, Area,
} from 'recharts'
import api from '@/lib/api'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { formatCurrency, formatNumber, capitalize } from '@/lib/utils'

const COLORS = ['#1E3A5F','#2E86AB','#F0A500','#10B981','#EF4444','#8B5CF6','#F59E0B','#06B6D4']

export default function AnalyticsPage() {
  const { data: dash } = useQuery({ queryKey: ['dashboard'], queryFn: () => api.get('/analytics/dashboard').then(r => r.data) })
  const { data: trends } = useQuery({ queryKey: ['cost-trends'], queryFn: () => api.get('/analytics/cost-trends').then(r => r.data) })
  const { data: matUsage } = useQuery({ queryKey: ['material-usage'], queryFn: () => api.get('/analytics/material-usage').then(r => r.data) })

  const statusData = dash?.charts?.status_distribution ?? []
  const typeData   = dash?.charts?.building_type_distribution ?? []
  const matData    = matUsage?.chart_data ?? []

  return (
    <div className="space-y-6">
      {/* KPI Summary */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Projects',   value: dash?.kpis?.total_projects ?? 0,    fmt: String },
          { label: 'Active Projects',  value: dash?.kpis?.active_projects ?? 0,   fmt: String },
          { label: 'Total Est. Cost',  value: dash?.kpis?.total_estimated_cost ?? 0, fmt: formatCurrency },
          { label: 'Total BOQs',       value: dash?.kpis?.total_boqs ?? 0,         fmt: String },
        ].map(({ label, value, fmt }) => (
          <Card key={label}>
            <CardContent className="p-5">
              <p className="text-sm text-muted-foreground">{label}</p>
              <p className="text-3xl font-bold mt-1">{fmt(value as any)}</p>
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Cost Trends */}
      <Card>
        <CardHeader><CardTitle>Monthly Cost Trends (Last 12 Months)</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={280}>
            <AreaChart data={trends ?? []}>
              <defs>
                <linearGradient id="colorCost" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#1E3A5F" stopOpacity={0.15} />
                  <stop offset="95%" stopColor="#1E3A5F" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="month_label" tick={{ fontSize: 11 }} />
              <YAxis tickFormatter={v => `${(v/1e6).toFixed(1)}M`} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(v: any) => formatCurrency(v)} />
              <Area type="monotone" dataKey="total_cost" stroke="#1E3A5F" fill="url(#colorCost)" strokeWidth={2} />
            </AreaChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Project Status Pie */}
        <Card>
          <CardHeader><CardTitle>Project Status Distribution</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <PieChart>
                <Pie data={statusData.filter((d: any) => d.count > 0)} dataKey="count" nameKey="status"
                  cx="50%" cy="50%" outerRadius={80} label={({ status }) => capitalize(status)}>
                  {statusData.map((_: any, i: number) => <Cell key={i} fill={COLORS[i]} />)}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Building Types Bar */}
        <Card>
          <CardHeader><CardTitle>Building Types</CardTitle></CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={240}>
              <BarChart data={typeData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" tick={{ fontSize: 10 }} />
                <YAxis dataKey="type" type="category" tick={{ fontSize: 10 }} width={90} tickFormatter={capitalize} />
                <Tooltip />
                <Bar dataKey="count" fill="#2E86AB" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>

        {/* Material Usage Bar */}
        <Card>
          <CardHeader><CardTitle>Material Consumption</CardTitle></CardHeader>
          <CardContent>
            <div className="space-y-3">
              {matData.map((m: any) => (
                <div key={m.material} className="flex items-center justify-between">
                  <span className="text-sm font-medium w-24 truncate">{m.material}</span>
                  <div className="flex-1 mx-3 bg-muted rounded-full h-2">
                    <div
                      className="bg-primary h-2 rounded-full"
                      style={{ width: `${Math.min((m.quantity / (matData[0]?.quantity || 1)) * 100, 100)}%` }}
                    />
                  </div>
                  <span className="text-sm text-muted-foreground w-24 text-right">
                    {formatNumber(m.quantity)} {m.unit}
                  </span>
                </div>
              ))}
              {matData.length === 0 && <p className="text-sm text-muted-foreground text-center py-8">Run estimation to see material usage.</p>}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Project count by month */}
      <Card>
        <CardHeader><CardTitle>Projects Created Per Month</CardTitle></CardHeader>
        <CardContent>
          <ResponsiveContainer width="100%" height={220}>
            <BarChart data={trends ?? []}>
              <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--border))" />
              <XAxis dataKey="month_label" tick={{ fontSize: 11 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip />
              <Bar dataKey="project_count" fill="#F0A500" radius={[4, 4, 0, 0]} name="Projects" />
            </BarChart>
          </ResponsiveContainer>
        </CardContent>
      </Card>
    </div>
  )
}
