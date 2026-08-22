import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, Plus, Wand2, Download, CheckCircle2, Pencil, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { formatNumber, formatCurrency, capitalize } from '@/lib/utils'
import { toast } from '@/hooks/useToast'

// ── BOQ Table with inline rate editing ───────────────
function BOQTable({ boq, onRefresh }: { boq: any; onRefresh: () => void }) {
  const [editingItem, setEditingItem] = useState<string | null>(null)
  const [editRate, setEditRate] = useState('')

  const updateMut = useMutation({
    mutationFn: ({ itemId, rate }: { itemId: string; rate: number }) =>
      api.put(`/boq/${boq.id}/items/${itemId}`, { rate }),   // ← only send rate, NO amount
    onSuccess: () => {
      setEditingItem(null)
      onRefresh()
      toast.success('Rate updated')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Failed to update rate'),
  })

  const handleSaveRate = (itemId: string) => {
    const rate = parseFloat(editRate)
    if (isNaN(rate) || rate < 0) {
      toast.error('Enter a valid rate')
      return
    }
    updateMut.mutate({ itemId, rate })
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <thead className="bg-[hsl(var(--primary))] text-white">
          <tr>
            {['Item No', 'Description', 'Unit', 'Quantity', 'Rate (INR)', 'Amount (INR)', ''].map(h => (
              <th key={h} className="px-3 py-3 text-left text-xs font-medium whitespace-nowrap">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y">
          {(boq.items ?? []).map((item: any, i: number) =>
            item.is_heading ? (
              // Section heading row
              <tr key={item.id} className="bg-[hsl(var(--secondary))] text-white">
                <td className="px-3 py-2.5 font-bold text-xs">{item.item_no}</td>
                <td className="px-3 py-2.5 font-bold text-xs uppercase tracking-wide" colSpan={5}>
                  {item.description}
                </td>
                <td />
              </tr>
            ) : (
              // Data row
              <tr key={item.id} className={i % 2 === 0 ? 'bg-white hover:bg-muted/20' : 'bg-blue-50/30 hover:bg-muted/20'}>
                <td className="px-3 py-2 text-muted-foreground font-mono text-xs">{item.item_no}</td>
                <td className="px-3 py-2 max-w-[280px]">{item.description}</td>
                <td className="px-3 py-2 text-center text-muted-foreground text-xs">{item.unit}</td>
                <td className="px-3 py-2 text-right font-medium">{formatNumber(item.quantity, 3)}</td>

                {/* Rate cell — inline edit */}
                <td className="px-3 py-2 text-right">
                  {editingItem === item.id ? (
                    <div className="flex items-center gap-1 justify-end">
                      <Input
                        className="h-7 w-28 text-xs text-right"
                        type="number"
                        min="0"
                        step="0.01"
                        value={editRate}
                        onChange={e => setEditRate(e.target.value)}
                        onKeyDown={e => {
                          if (e.key === 'Enter') handleSaveRate(item.id)
                          if (e.key === 'Escape') setEditingItem(null)
                        }}
                        autoFocus
                      />
                      <Button
                        size="sm"
                        className="h-7 px-2 text-xs"
                        disabled={updateMut.isPending}
                        onClick={() => handleSaveRate(item.id)}
                      >
                        {updateMut.isPending ? <Loader2 className="h-3 w-3 animate-spin" /> : '✓'}
                      </Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        className="h-7 px-2 text-xs"
                        onClick={() => setEditingItem(null)}
                      >✗</Button>
                    </div>
                  ) : (
                    <span className={`cursor-pointer ${item.rate === 0 ? 'text-orange-400 italic text-xs' : 'font-medium'}`}
                      onClick={() => { setEditingItem(item.id); setEditRate(String(item.rate || '')) }}>
                      {item.rate === 0 ? 'click to enter rate' : formatNumber(item.rate)}
                    </span>
                  )}
                </td>

                {/* Amount */}
                <td className="px-3 py-2 text-right font-medium">
                  {item.amount > 0 ? formatNumber(item.amount) : '—'}
                </td>

                {/* Edit button */}
                <td className="px-3 py-2">
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-7 w-7"
                    onClick={() => { setEditingItem(item.id); setEditRate(String(item.rate || '')) }}
                  >
                    <Pencil className="h-3 w-3" />
                  </Button>
                </td>
              </tr>
            )
          )}
        </tbody>

        {/* Totals footer */}
        <tfoot className="border-t-2 border-primary bg-muted/10">
          {[
            [`Sub-Total`,                              boq.subtotal ?? 0],
            [`Overhead (${boq.overhead_pct}%)`,        boq.overhead_amount ?? 0],
            [`Profit (${boq.profit_pct}%)`,            boq.profit_amount ?? 0],
            [`Contingency (${boq.contingency_pct}%)`,  boq.contingency_amount ?? 0],
          ].map(([label, val]) => (
            <tr key={String(label)}>
              <td colSpan={4} />
              <td className="px-3 py-2 text-right text-sm font-medium text-muted-foreground">{label}</td>
              <td className="px-3 py-2 text-right font-semibold">{formatCurrency(Number(val))}</td>
              <td />
            </tr>
          ))}
          <tr className="bg-amber-50 border-t-2 border-amber-300">
            <td colSpan={4} />
            <td className="px-3 py-3 text-right font-bold text-primary text-sm">GRAND TOTAL</td>
            <td className="px-3 py-3 text-right text-xl font-bold text-primary">
              {formatCurrency(boq.grand_total ?? 0)}
            </td>
            <td />
          </tr>
        </tfoot>
      </table>
    </div>
  )
}

// ── Main BOQ Page ─────────────────────────────────────
export default function BOQPage() {
  const qc = useQueryClient()
  const [projectId, setProjectId] = useState('')
  const [selectedBOQId, setSelectedBOQId] = useState('')

  // Projects list
  const { data: projects } = useQuery({
    queryKey: ['all-projects'],
    queryFn: () => api.get('/projects/', { params: { limit: 200 } }).then(r => r.data.data),
  })

  // BOQs for selected project
  const { data: boqs, refetch: refetchBoqs } = useQuery({
    queryKey: ['boqs', projectId],
    queryFn: () => api.get(`/boq/project/${projectId}`).then(r => r.data),
    enabled: !!projectId,
  })

  // Full BOQ detail with items
  const { data: boqDetail, refetch: refetchDetail } = useQuery({
    queryKey: ['boq-detail', selectedBOQId],
    queryFn: () => api.get(`/boq/${selectedBOQId}`).then(r => r.data),
    enabled: !!selectedBOQId,
  })

  // Create new BOQ
  const createMut = useMutation({
    mutationFn: () => api.post('/boq/', {
      project_id: projectId,
      title: 'Bill of Quantities',
      overhead_pct: 10,
      profit_pct: 10,
      contingency_pct: 5,
    }),
    onSuccess: ({ data }) => {
      refetchBoqs()
      setSelectedBOQId(data.id)
      toast.success('BOQ created!')
    },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Failed to create BOQ'),
  })

  // Auto-generate BOQ items from estimates
  const autoGenMut = useMutation({
    mutationFn: (boqId: string) => api.post(`/boq/${boqId}/auto-generate`),
    onSuccess: () => {
      refetchDetail()
      toast.success('BOQ items generated from estimates!')
    },
    onError: (e: any) => toast.error(
      e.response?.data?.detail ?? 'Auto-generate failed. Run Estimation first.'
    ),
  })

  // Approve BOQ
  const approveMut = useMutation({
    mutationFn: (boqId: string) => api.post(`/boq/${boqId}/approve`),
    onSuccess: () => { refetchDetail(); toast.success('BOQ approved!') },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Failed to approve'),
  })

  const handleProjectChange = (id: string) => {
    setProjectId(id)
    setSelectedBOQId('')
  }

  const handleBOQChange = (id: string) => {
    setSelectedBOQId(id)
  }

  return (
    <div className="space-y-5">
      {/* ── Selectors ─────────────────────────────── */}
      <Card>
        <CardContent className="p-4 flex flex-wrap gap-4 items-end">
          {/* Project */}
          <div className="space-y-1.5 min-w-[220px]">
            <Label>Project *</Label>
            <Select value={projectId} onValueChange={handleProjectChange}>
              <SelectTrigger><SelectValue placeholder="Select project..." /></SelectTrigger>
              <SelectContent>
                {(projects ?? []).map((p: any) => (
                  <SelectItem key={p.id} value={p.id}>{p.project_name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {/* BOQ */}
          {projectId && (
            <div className="space-y-1.5 min-w-[240px]">
              <Label>BOQ</Label>
              <Select value={selectedBOQId} onValueChange={handleBOQChange}>
                <SelectTrigger><SelectValue placeholder="Select BOQ..." /></SelectTrigger>
                <SelectContent>
                  {(boqs ?? []).map((b: any) => (
                    <SelectItem key={b.id} value={b.id}>
                      {b.boq_number} — {b.title}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          )}

          {/* New BOQ button */}
          {projectId && (
            <Button
              variant="outline"
              onClick={() => createMut.mutate()}
              disabled={createMut.isPending}
            >
              {createMut.isPending
                ? <Loader2 className="h-4 w-4 animate-spin mr-2" />
                : <Plus className="h-4 w-4 mr-2" />}
              New BOQ
            </Button>
          )}
        </CardContent>
      </Card>

      {/* ── BOQ Detail ────────────────────────────── */}
      {selectedBOQId && boqDetail && (
        <>
          {/* Header + action buttons */}
          <Card>
            <CardHeader>
              <div className="flex items-start justify-between flex-wrap gap-3">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <FileText className="h-5 w-5" />
                    {boqDetail.boq_number} — {boqDetail.title}
                  </CardTitle>
                  <div className="flex items-center gap-2 mt-2">
                    <Badge variant={boqDetail.status === 'approved' ? 'success' : 'outline'}>
                      {capitalize(boqDetail.status)}
                    </Badge>
                    <span className="text-xs text-muted-foreground">Revision {boqDetail.revision}</span>
                    <span className="text-xs text-muted-foreground">{boqDetail.currency}</span>
                  </div>
                </div>

                <div className="flex gap-2 flex-wrap">
                  {/* Auto-generate from estimates */}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => autoGenMut.mutate(boqDetail.id)}
                    disabled={autoGenMut.isPending}
                    title="Populate items from saved quantity estimates"
                  >
                    {autoGenMut.isPending
                      ? <Loader2 className="h-4 w-4 animate-spin mr-2" />
                      : <Wand2 className="h-4 w-4 mr-2" />}
                    Auto-Generate from Estimates
                  </Button>

                  {/* Approve */}
                  {boqDetail.status !== 'approved' && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => approveMut.mutate(boqDetail.id)}
                      disabled={approveMut.isPending}
                    >
                      <CheckCircle2 className="h-4 w-4 mr-2" />
                      Approve
                    </Button>
                  )}

                  {/* Export */}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.open(`/api/v1/reports/boq/${boqDetail.id}/pdf`)}
                  >
                    <Download className="h-4 w-4 mr-2" /> PDF
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.open(`/api/v1/reports/boq/${boqDetail.id}/excel`)}
                  >
                    <Download className="h-4 w-4 mr-2" /> Excel
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => window.open(`/api/v1/reports/boq/${boqDetail.id}/csv`)}
                  >
                    <Download className="h-4 w-4 mr-2" /> CSV
                  </Button>
                </div>
              </div>

              {/* Cost summary strip */}
              {(boqDetail.grand_total ?? 0) > 0 && (
                <div className="mt-4 grid grid-cols-2 sm:grid-cols-4 gap-3">
                  {[
                    { label: 'Sub-Total',   value: boqDetail.subtotal },
                    { label: 'Overhead',    value: boqDetail.overhead_amount },
                    { label: 'Profit',      value: boqDetail.profit_amount },
                    { label: 'Grand Total', value: boqDetail.grand_total },
                  ].map(({ label, value }) => (
                    <div key={label} className={`rounded-lg p-3 ${label === 'Grand Total' ? 'bg-amber-50 border border-amber-200' : 'bg-muted/40'}`}>
                      <p className="text-xs text-muted-foreground">{label}</p>
                      <p className={`text-base font-bold mt-0.5 ${label === 'Grand Total' ? 'text-amber-700' : ''}`}>
                        {formatCurrency(value ?? 0)}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardHeader>
          </Card>

          {/* BOQ Table */}
          {(boqDetail.items ?? []).length === 0 ? (
            <Card>
              <CardContent className="py-16 text-center">
                <FileText className="h-12 w-12 text-muted-foreground/30 mx-auto mb-3" />
                <p className="font-medium text-muted-foreground">No items in this BOQ yet.</p>
                <p className="text-sm text-muted-foreground/70 mt-1">
                  Click <strong>Auto-Generate from Estimates</strong> to populate items,<br />
                  or make sure you've run Estimation first.
                </p>
                <Button
                  className="mt-4"
                  onClick={() => autoGenMut.mutate(boqDetail.id)}
                  disabled={autoGenMut.isPending}
                >
                  {autoGenMut.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : <Wand2 className="h-4 w-4 mr-2" />}
                  Auto-Generate from Estimates
                </Button>
              </CardContent>
            </Card>
          ) : (
            <Card>
              <CardContent className="p-0">
                <BOQTable boq={boqDetail} onRefresh={refetchDetail} />
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Empty state when no project selected */}
      {!projectId && (
        <Card>
          <CardContent className="py-16 text-center">
            <FileText className="h-14 w-14 text-muted-foreground/20 mx-auto mb-4" />
            <p className="font-medium text-muted-foreground">Select a project to view or create a BOQ</p>
            <p className="text-sm text-muted-foreground/60 mt-1">
              Make sure you have run Estimation before generating BOQ items.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
