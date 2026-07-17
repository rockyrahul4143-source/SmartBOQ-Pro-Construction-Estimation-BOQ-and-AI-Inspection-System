import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { Plus, Pencil, History, TrendingUp, Search, Loader2 } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { formatDate, capitalize, formatNumber } from '@/lib/utils'
import { toast } from '@/hooks/useToast'

const CATEGORIES = ['cement','aggregate','sand','steel','brick','block','paint','tile','waterproofing','wood','glass','electrical','plumbing','other']
const UNITS = ['kg','ton','bag','m3','m2','lm','no','ltr','gal']

const matSchema = z.object({
  name: z.string().min(2),
  category: z.string(),
  unit: z.string(),
  current_rate: z.coerce.number().min(0),
  supplier_name: z.string().optional(),
  supplier_contact: z.string().optional(),
  description: z.string().optional(),
})
type MatForm = z.infer<typeof matSchema>

const rateSchema = z.object({
  new_rate: z.coerce.number().min(1),
  notes: z.string().optional(),
})
type RateForm = z.infer<typeof rateSchema>

function MaterialModal({ open, onClose, existing }: { open: boolean; onClose: () => void; existing?: any }) {
  const qc = useQueryClient()
  const { register, handleSubmit, setValue, reset, formState: { errors, isSubmitting } } = useForm<MatForm>({
    resolver: zodResolver(matSchema),
    defaultValues: existing ?? { category: 'cement', unit: 'bag' },
  })
  const mut = useMutation({
    mutationFn: (d: MatForm) => existing ? api.put(`/materials/${existing.id}`, d) : api.post('/materials/', d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['materials'] }); toast.success(existing ? 'Updated' : 'Created'); onClose(); reset() },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Error'),
  })
  if (!open) return null
  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <Card className="w-full max-w-lg">
        <CardHeader><CardTitle>{existing ? 'Edit Material' : 'Add Material'}</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(d => mut.mutate(d))} className="space-y-3">
            <div className="grid grid-cols-2 gap-3">
              <div className="col-span-2 space-y-1">
                <Label>Name *</Label>
                <Input {...register('name')} placeholder="Ordinary Portland Cement" />
                {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
              </div>
              <div className="space-y-1">
                <Label>Category *</Label>
                <Select defaultValue={existing?.category ?? 'cement'} onValueChange={v => setValue('category', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{CATEGORIES.map(c => <SelectItem key={c} value={c}>{capitalize(c)}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="space-y-1">
                <Label>Unit *</Label>
                <Select defaultValue={existing?.unit ?? 'bag'} onValueChange={v => setValue('unit', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{UNITS.map(u => <SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
                </Select>
              </div>
              <div className="col-span-2 space-y-1">
                <Label>Current Rate (PKR) *</Label>
                <Input type="number" step="0.01" {...register('current_rate')} placeholder="1200" />
              </div>
              <div className="space-y-1">
                <Label>Supplier</Label>
                <Input {...register('supplier_name')} placeholder="Maple Traders" />
              </div>
              <div className="space-y-1">
                <Label>Supplier Contact</Label>
                <Input {...register('supplier_contact')} placeholder="+92-300-1234567" />
              </div>
            </div>
            <div className="flex gap-2 justify-end pt-2">
              <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="h-4 w-4 animate-spin mr-2" />}
                {existing ? 'Save' : 'Add Material'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

function RateUpdateModal({ open, onClose, material }: { open: boolean; onClose: () => void; material: any }) {
  const qc = useQueryClient()
  const { register, handleSubmit, reset, formState: { isSubmitting } } = useForm<RateForm>({ resolver: zodResolver(rateSchema) })
  const mut = useMutation({
    mutationFn: (d: RateForm) => api.patch(`/materials/${material?.id}/rate`, d),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['materials'] }); toast.success('Rate updated'); onClose(); reset() },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Error'),
  })
  if (!open || !material) return null
  return (
    <div className="fixed inset-0 z-50 bg-black/50 flex items-center justify-center p-4">
      <Card className="w-full max-w-sm">
        <CardHeader><CardTitle>Update Rate — {material.name}</CardTitle></CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit(d => mut.mutate(d))} className="space-y-3">
            <p className="text-sm text-muted-foreground">Current rate: <strong>PKR {formatNumber(material.current_rate)}</strong> per {material.unit}</p>
            <div className="space-y-1">
              <Label>New Rate (PKR)</Label>
              <Input type="number" step="0.01" {...register('new_rate')} placeholder="e.g. 1350" />
            </div>
            <div className="space-y-1">
              <Label>Notes</Label>
              <Input {...register('notes')} placeholder="Market price increase Q2 2024" />
            </div>
            <div className="flex gap-2 justify-end">
              <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="h-4 w-4 animate-spin mr-2" />}Update Rate
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}

export default function MaterialsPage() {
  const [search, setSearch] = useState('')
  const [catFilter, setCatFilter] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<any>(null)
  const [ratingMat, setRatingMat] = useState<any>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['materials', search, catFilter],
    queryFn: () => api.get('/materials/', { params: { search: search || undefined, category: catFilter || undefined, limit: 200 } }).then(r => r.data),
  })

  const materials = data?.data ?? []

  return (
    <div className="space-y-5">
      <div className="flex flex-col sm:flex-row gap-3 items-start sm:items-center justify-between">
        <div className="flex gap-3 flex-1 max-w-xl">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input className="pl-9" placeholder="Search materials..." value={search} onChange={e => setSearch(e.target.value)} />
          </div>
          <Select value={catFilter} onValueChange={setCatFilter}>
            <SelectTrigger className="w-40"><SelectValue placeholder="All Categories" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="">All Categories</SelectItem>
              {CATEGORIES.map(c => <SelectItem key={c} value={c}>{capitalize(c)}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={() => { setEditing(null); setShowForm(true) }}>
          <Plus className="h-4 w-4 mr-2" /> Add Material
        </Button>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16"><Loader2 className="h-8 w-8 animate-spin text-primary" /></div>
      ) : (
        <div className="rounded-lg border overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-muted/50">
              <tr>
                {['Code','Name','Category','Unit','Current Rate (PKR)','Supplier','Last Updated','Actions'].map(h => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-medium text-muted-foreground">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y">
              {materials.map((m: any) => (
                <tr key={m.id} className="hover:bg-muted/30">
                  <td className="px-4 py-3 font-mono text-xs text-muted-foreground">{m.material_code}</td>
                  <td className="px-4 py-3 font-medium">{m.name}</td>
                  <td className="px-4 py-3"><Badge variant="outline">{capitalize(m.category)}</Badge></td>
                  <td className="px-4 py-3 text-muted-foreground">{m.unit}</td>
                  <td className="px-4 py-3 font-bold text-primary">{formatNumber(m.current_rate)}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{m.supplier_name ?? '—'}</td>
                  <td className="px-4 py-3 text-xs text-muted-foreground">{formatDate(m.last_updated)}</td>
                  <td className="px-4 py-3">
                    <div className="flex gap-1">
                      <Button variant="ghost" size="icon" onClick={() => { setEditing(m); setShowForm(true) }}><Pencil className="h-4 w-4" /></Button>
                      <Button variant="ghost" size="icon" title="Update Rate" onClick={() => setRatingMat(m)}><TrendingUp className="h-4 w-4" /></Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-4 py-2 text-xs text-muted-foreground border-t bg-muted/20">
            {materials.length} materials · Total: {data?.total ?? 0}
          </div>
        </div>
      )}

      <MaterialModal open={showForm} onClose={() => setShowForm(false)} existing={editing} />
      <RateUpdateModal open={!!ratingMat} onClose={() => setRatingMat(null)} material={ratingMat} />
    </div>
  )
}
