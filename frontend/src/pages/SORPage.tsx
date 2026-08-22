import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Search, Plus, Edit2, Trash2, BookOpen, Loader2, X, Check } from 'lucide-react'
import api from '@/lib/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/hooks/useToast'
import { formatCurrency } from '@/lib/utils'

const CATEGORIES = [
  'earthwork','pcc','rcc','reinforcement','formwork',
  'masonry','plaster','flooring','waterproofing',
  'painting','doors_windows','plumbing','electrical','road','other'
]

const CAT_COLORS: Record<string, string> = {
  earthwork:'bg-amber-100 text-amber-800', pcc:'bg-stone-100 text-stone-800',
  rcc:'bg-blue-100 text-blue-800', reinforcement:'bg-zinc-100 text-zinc-800',
  formwork:'bg-orange-100 text-orange-800', masonry:'bg-red-100 text-red-800',
  plaster:'bg-pink-100 text-pink-800', flooring:'bg-purple-100 text-purple-800',
  waterproofing:'bg-cyan-100 text-cyan-800', painting:'bg-green-100 text-green-800',
  doors_windows:'bg-teal-100 text-teal-800', plumbing:'bg-indigo-100 text-indigo-800',
  electrical:'bg-yellow-100 text-yellow-800', road:'bg-gray-100 text-gray-800',
  other:'bg-slate-100 text-slate-800',
}

const UNITS = ['m3','m2','m','kg','no','point','ltr','bag','ton','rft']

interface SORItem {
  id: string; item_code: string; description: string; category: string
  unit: string; basic_rate: number; material_rate: number; labour_rate: number
  equipment_rate: number; formula_note?: string; mix_design?: string
  is_active: boolean; is_system: boolean; notes?: string
}

const emptyForm = {
  item_code:'', description:'', category:'other', unit:'m3',
  basic_rate:0, material_rate:0, labour_rate:0, equipment_rate:0,
  formula_note:'', mix_design:'', notes:'', rate_source:'custom'
}

export default function SORPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [category, setCategory] = useState('all')
  const [showForm, setShowForm] = useState(false)
  const [editing, setEditing] = useState<SORItem|null>(null)
  const [form, setForm] = useState({ ...emptyForm })

  const { data, isLoading } = useQuery({
    queryKey: ['sor', search, category],
    queryFn: () => api.get('/sor/', {
      params: {
        search: search || undefined,
        category: category !== 'all' ? category : undefined,
        limit: 500
      }
    }).then(r => r.data),
  })

  const saveMut = useMutation({
    mutationFn: (d: typeof emptyForm) =>
      editing ? api.put(`/sor/${editing.id}`, d) : api.post('/sor/', d),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['sor'] })
      toast.success(editing ? 'Item updated' : 'Item created')
      setShowForm(false); setEditing(null); setForm({ ...emptyForm })
    },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Error saving item'),
  })

  const delMut = useMutation({
    mutationFn: (id: string) => api.delete(`/sor/${id}`),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['sor'] }); toast.success('Item deleted') },
    onError: (e: any) => toast.error(e.response?.data?.detail ?? 'Cannot delete system item'),
  })

  const openEdit = (item: SORItem) => {
    setEditing(item)
    setForm({
      item_code: item.item_code, description: item.description,
      category: item.category, unit: item.unit,
      basic_rate: item.basic_rate, material_rate: item.material_rate ?? 0,
      labour_rate: item.labour_rate ?? 0, equipment_rate: item.equipment_rate ?? 0,
      formula_note: item.formula_note ?? '', mix_design: item.mix_design ?? '',
      notes: item.notes ?? '', rate_source: 'custom',
    })
    setShowForm(true)
  }

  const items: SORItem[] = data?.data ?? []

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-xl font-bold flex items-center gap-2"><BookOpen className="h-5 w-5"/>Item Master / SOR</h1>
          <p className="text-sm text-muted-foreground">Schedule of Rates — {data?.total ?? 0} items</p>
        </div>
        <Button onClick={() => { setEditing(null); setForm({...emptyForm}); setShowForm(true) }}>
          <Plus className="h-4 w-4 mr-1"/>Add Item
        </Button>
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        <div className="relative flex-1 min-w-48">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground"/>
          <Input className="pl-9" placeholder="Search code, description, tags..." value={search} onChange={e=>setSearch(e.target.value)}/>
        </div>
        <Select value={category} onValueChange={setCategory}>
          <SelectTrigger className="w-48"><SelectValue placeholder="All categories"/></SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All Categories</SelectItem>
            {CATEGORIES.map(c=><SelectItem key={c} value={c}>{c.replace(/_/g,' ').replace(/\b\w/g,l=>l.toUpperCase())}</SelectItem>)}
          </SelectContent>
        </Select>
      </div>

      {/* Table */}
      <Card>
        <CardContent className="p-0">
          {isLoading ? (
            <div className="flex items-center justify-center py-16"><Loader2 className="h-6 w-6 animate-spin"/></div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="bg-muted/50 border-b">
                  <tr>
                    {['Code','Description','Category','Unit','Basic Rate','Formula','Actions'].map(h=>(
                      <th key={h} className="px-3 py-2.5 text-left text-xs font-medium text-muted-foreground whitespace-nowrap">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y">
                  {items.map(item=>(
                    <tr key={item.id} className="hover:bg-muted/20">
                      <td className="px-3 py-2">
                        <span className="font-mono text-xs bg-muted px-1.5 py-0.5 rounded">{item.item_code}</span>
                        {item.is_system && <span className="ml-1 text-xs text-muted-foreground">[sys]</span>}
                      </td>
                      <td className="px-3 py-2 max-w-xs">
                        <p className="font-medium text-sm leading-tight">{item.description}</p>
                        {item.mix_design && <p className="text-xs text-blue-600 mt-0.5">Mix: {item.mix_design}</p>}
                      </td>
                      <td className="px-3 py-2">
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${CAT_COLORS[item.category] ?? 'bg-gray-100'}`}>
                          {item.category.replace(/_/g,' ')}
                        </span>
                      </td>
                      <td className="px-3 py-2 font-medium">{item.unit}</td>
                      <td className="px-3 py-2 font-bold text-green-700">{formatCurrency(item.basic_rate)}</td>
                      <td className="px-3 py-2 max-w-xs">
                        <p className="text-xs text-muted-foreground line-clamp-2">{item.formula_note ?? '—'}</p>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex gap-1">
                          <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={()=>openEdit(item)}><Edit2 className="h-3 w-3"/></Button>
                          {!item.is_system && (
                            <Button size="sm" variant="ghost" className="h-7 w-7 p-0 text-destructive hover:text-destructive"
                              onClick={()=>{ if(confirm('Delete this item?')) delMut.mutate(item.id) }}>
                              <Trash2 className="h-3 w-3"/>
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                  {items.length === 0 && (
                    <tr><td colSpan={7} className="text-center py-12 text-muted-foreground">No items found. Add your first SOR item.</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Add/Edit Form Dialog */}
      {showForm && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <Card className="w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <CardHeader className="flex flex-row items-center justify-between pb-3">
              <CardTitle className="text-base">{editing ? 'Edit SOR Item' : 'Add SOR Item'}</CardTitle>
              <Button size="sm" variant="ghost" className="h-7 w-7 p-0" onClick={()=>{setShowForm(false);setEditing(null)}}><X className="h-4 w-4"/></Button>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1"><Label>Item Code *</Label>
                  <Input value={form.item_code} onChange={e=>setForm(f=>({...f,item_code:e.target.value}))} placeholder="RCC-001"/>
                </div>
                <div className="space-y-1"><Label>Unit *</Label>
                  <Select value={form.unit} onValueChange={v=>setForm(f=>({...f,unit:v}))}>
                    <SelectTrigger><SelectValue/></SelectTrigger>
                    <SelectContent>{UNITS.map(u=><SelectItem key={u} value={u}>{u}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
              </div>
              <div className="space-y-1"><Label>Description *</Label>
                <Input value={form.description} onChange={e=>setForm(f=>({...f,description:e.target.value}))} placeholder="RCC M20 in columns"/>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1"><Label>Category</Label>
                  <Select value={form.category} onValueChange={v=>setForm(f=>({...f,category:v}))}>
                    <SelectTrigger><SelectValue/></SelectTrigger>
                    <SelectContent>{CATEGORIES.map(c=><SelectItem key={c} value={c}>{c.replace(/_/g,' ')}</SelectItem>)}</SelectContent>
                  </Select>
                </div>
                <div className="space-y-1"><Label>Mix Design</Label>
                  <Input value={form.mix_design} onChange={e=>setForm(f=>({...f,mix_design:e.target.value}))} placeholder="M20 / 1:4 / etc."/>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1"><Label>Basic Rate (INR) *</Label>
                  <Input type="number" value={form.basic_rate} onChange={e=>setForm(f=>({...f,basic_rate:+e.target.value}))}/>
                </div>
                <div className="space-y-1"><Label>Material Rate (INR)</Label>
                  <Input type="number" value={form.material_rate} onChange={e=>setForm(f=>({...f,material_rate:+e.target.value}))}/>
                </div>
                <div className="space-y-1"><Label>Labour Rate (INR)</Label>
                  <Input type="number" value={form.labour_rate} onChange={e=>setForm(f=>({...f,labour_rate:+e.target.value}))}/>
                </div>
                <div className="space-y-1"><Label>Equipment Rate (INR)</Label>
                  <Input type="number" value={form.equipment_rate} onChange={e=>setForm(f=>({...f,equipment_rate:+e.target.value}))}/>
                </div>
              </div>
              <div className="space-y-1"><Label>Formula Note</Label>
                <Input value={form.formula_note} onChange={e=>setForm(f=>({...f,formula_note:e.target.value}))} placeholder="L × W × D × Nos = Volume m³"/>
              </div>
              <div className="space-y-1"><Label>Notes</Label>
                <Input value={form.notes} onChange={e=>setForm(f=>({...f,notes:e.target.value}))}/>
              </div>
              <div className="flex gap-2 justify-end pt-2">
                <Button variant="outline" onClick={()=>{setShowForm(false);setEditing(null)}}>Cancel</Button>
                <Button disabled={saveMut.isPending || !form.item_code || !form.description}
                  onClick={()=>saveMut.mutate(form)}>
                  {saveMut.isPending ? <Loader2 className="h-4 w-4 animate-spin mr-1"/> : <Check className="h-4 w-4 mr-1"/>}
                  {editing ? 'Update' : 'Create'}
                </Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  )
}
