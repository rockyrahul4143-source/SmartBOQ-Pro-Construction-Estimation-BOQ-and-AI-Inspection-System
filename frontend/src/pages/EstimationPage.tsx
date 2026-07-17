import { useState } from 'react'
import { useQuery, useMutation } from '@tanstack/react-query'
import { Calculator, Play, Download, Loader2, CheckCircle2, AlertCircle } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { formatNumber, capitalize } from '@/lib/utils'
import { toast } from '@/hooks/useToast'

function StatCard({ label, value, unit, color }: { label: string; value: number; unit: string; color: string }) {
  return (
    <div className={`rounded-lg p-4 ${color}`}>
      <p className="text-xs font-medium opacity-70 mb-1">{label}</p>
      <p className="text-xl font-bold">{formatNumber(value, value < 10 ? 3 : 1)}</p>
      <p className="text-xs opacity-60 mt-0.5">{unit}</p>
    </div>
  )
}

export default function EstimationPage() {
  const [projectId, setProjectId] = useState('')
  const [buildingId, setBuildingId] = useState('')
  const [result, setResult] = useState<any>(null)

  // Use a unique query key to avoid conflicts with BOQPage
  const { data: projects } = useQuery({
    queryKey: ['estimation-projects-list'],
    queryFn: () => api.get('/projects/', { params: { limit: 200 } }).then(r => r.data.data),
  })

  const { data: buildings } = useQuery({
    queryKey: ['estimation-buildings', projectId],
    queryFn: () => api.get(`/buildings/project/${projectId}`).then(r => r.data),
    enabled: !!projectId,
  })

  const runMut = useMutation({
    mutationFn: () => api.post(`/estimates/run/${buildingId}`),
    onSuccess: ({ data }) => {
      setResult(data)
      toast.success('Estimation complete! Results saved.')
    },
    onError: (e: any) => {
      const detail = e.response?.data?.detail ?? 'Estimation failed. Check building dimensions.'
      toast.error(detail)
    },
  })

  const summary = result?.summary
  const hasResults = summary && (summary.items?.length > 0)

  const handleProjectChange = (id: string) => {
    setProjectId(id)
    setBuildingId('')
    setResult(null)
  }

  return (
    <div className="space-y-6">
      {/* ── Controls ────────────────────────────────── */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Calculator className="h-5 w-5" />
            Quantity Estimation Engine
          </CardTitle>
          <p className="text-sm text-muted-foreground">
            Select a project and building, then run all 14 civil engineering calculations.
          </p>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {/* Project selector */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Project *</label>
              <Select value={projectId} onValueChange={handleProjectChange}>
                <SelectTrigger>
                  <SelectValue placeholder="Select project..." />
                </SelectTrigger>
                <SelectContent>
                  {(projects ?? []).length === 0 && (
                    <SelectItem value="__none__" disabled>No projects found</SelectItem>
                  )}
                  {(projects ?? []).map((p: any) => (
                    <SelectItem key={p.id} value={p.id}>{p.project_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            {/* Building selector */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Building *</label>
              <Select value={buildingId} onValueChange={setBuildingId} disabled={!projectId}>
                <SelectTrigger>
                  <SelectValue placeholder={projectId ? 'Select building...' : 'Select project first'} />
                </SelectTrigger>
                <SelectContent>
                  {(buildings ?? []).length === 0 && projectId && (
                    <SelectItem value="__none__" disabled>
                      No buildings — add one in Buildings page
                    </SelectItem>
                  )}
                  {(buildings ?? []).map((b: any) => (
                    <SelectItem key={b.id} value={b.id}>{b.building_name}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          {/* Guidance when building selected but no dimensions */}
          {buildingId && (buildings ?? []).find((b: any) => b.id === buildingId)?.plot_length === 0 && (
            <div className="flex gap-2 bg-yellow-50 border border-yellow-200 rounded-lg p-3 text-sm text-yellow-800">
              <AlertCircle className="h-4 w-4 shrink-0 mt-0.5" />
              Building has no dimensions entered. Go to Buildings page and fill in plot length, width, walls, columns etc.
            </div>
          )}

          <Button
            onClick={() => runMut.mutate()}
            disabled={!buildingId || runMut.isPending}
            className="gap-2"
          >
            {runMut.isPending
              ? <><Loader2 className="h-4 w-4 animate-spin" /> Calculating...</>
              : <><Play className="h-4 w-4" /> Run Estimation</>}
          </Button>
        </CardContent>
      </Card>

      {/* ── Results ──────────────────────────────────── */}
      {hasResults && (
        <>
          <div className="flex items-center gap-2 text-green-700 bg-green-50 rounded-lg px-4 py-2.5 border border-green-200">
            <CheckCircle2 className="h-5 w-5 shrink-0" />
            <span className="font-medium text-sm">
              Estimation complete — {summary.items.length} work types calculated and saved to database.
            </span>
          </div>

          {/* Material Summary Cards */}
          <Card>
            <CardHeader>
              <CardTitle>Material Summary</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
                <StatCard label="Cement"       value={summary.total_cement_bags}    unit="50 kg bags"   color="bg-slate-50 text-slate-800 border border-slate-200" />
                <StatCard label="Sand"         value={summary.total_sand_cft}       unit="CFT"          color="bg-yellow-50 text-yellow-800 border border-yellow-200" />
                <StatCard label="Aggregate"    value={summary.total_aggregate_cft}  unit="CFT"          color="bg-orange-50 text-orange-800 border border-orange-200" />
                <StatCard label="Steel"        value={summary.total_steel_kg}       unit="kg"           color="bg-zinc-50 text-zinc-800 border border-zinc-200" />
                <StatCard label="Steel (tons)" value={summary.total_steel_tons}     unit="metric tons"  color="bg-zinc-50 text-zinc-800 border border-zinc-200" />
                <StatCard label="Bricks"       value={summary.total_bricks}         unit="nos"          color="bg-red-50 text-red-800 border border-red-200" />
                <StatCard label="Paint"        value={summary.total_paint_ltr}      unit="litres"       color="bg-purple-50 text-purple-800 border border-purple-200" />
                <StatCard label="Tiles"        value={summary.total_tiles_sqm}      unit="m²"           color="bg-teal-50 text-teal-800 border border-teal-200" />
              </div>
            </CardContent>
          </Card>

          {/* Work-type Breakdown Table */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between flex-wrap gap-3">
                <CardTitle>Work-Type Breakdown</CardTitle>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => window.open(`/api/v1/reports/quantity/${result.project_id}/pdf`)}
                >
                  <Download className="h-4 w-4 mr-2" /> PDF Report
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                All quantities follow IS 1200 & IS 456. Now go to BOQ page → select this project → Auto-Generate.
              </p>
            </CardHeader>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead className="bg-muted/60 border-b">
                    <tr>
                      {['Work Type', 'Quantity', 'Unit', 'Cement (bags)', 'Sand (CFT)', 'Agg (CFT)', 'Steel (kg)', 'Bricks'].map(h => (
                        <th key={h} className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground">{h}</th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {(summary.items ?? []).map((e: any, i: number) => (
                      <tr key={e.id ?? i} className="hover:bg-muted/20 transition-colors">
                        <td className="px-3 py-2">
                          <Badge variant="outline" className="text-xs font-normal">
                            {capitalize(typeof e.work_type === 'string' ? e.work_type : e.work_type?.value ?? '')}
                          </Badge>
                        </td>
                        <td className="px-3 py-2 font-medium tabular-nums">{formatNumber(e.quantity, 3)}</td>
                        <td className="px-3 py-2 text-muted-foreground">{e.unit}</td>
                        <td className="px-3 py-2 tabular-nums">{formatNumber(e.cement_bags ?? 0, 1)}</td>
                        <td className="px-3 py-2 tabular-nums">{formatNumber(e.sand_cft ?? 0, 1)}</td>
                        <td className="px-3 py-2 tabular-nums">{formatNumber(e.aggregate_cft ?? 0, 1)}</td>
                        <td className="px-3 py-2 tabular-nums">{formatNumber(e.steel_kg ?? 0, 1)}</td>
                        <td className="px-3 py-2 tabular-nums">{formatNumber(e.bricks_nos ?? 0, 0)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>

          {/* Next step hint */}
          <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 text-sm text-blue-800">
            <p className="font-semibold mb-1">✅ Estimation saved! Next steps:</p>
            <ol className="list-decimal list-inside space-y-1 text-blue-700">
              <li>Go to <strong>BOQ</strong> page</li>
              <li>Select this project and create a New BOQ</li>
              <li>Click <strong>Auto-Generate from Estimates</strong></li>
              <li>Fill in rates for each item</li>
              <li>Export as PDF or Excel</li>
            </ol>
          </div>
        </>
      )}
    </div>
  )
}
